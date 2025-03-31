import duckdb
import yaml
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import logging
from pathlib import Path
import os

# Constants
ERROR_DB_SETUP_FAILED = "Failed to setup database"

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration (Keep for potential future use or core settings)
def load_config():
    config_path = Path(__file__).parent / "config.yaml"
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"Configuration file not found at {config_path}. Using default settings.")
        # Provide default config if file is missing, ensure available_columns exists if needed elsewhere
        return {"available_columns": []} # Example default
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        return {"available_columns": []} # Fallback default

config = load_config()

# Create an in-memory DuckDB connection
db = duckdb.connect(":memory:")

def setup_database():
    """Initialize database and create view from local parquet files."""
    try:
        current_dir = Path(__file__).parent
        parquet_files = [str(f) for f in current_dir.glob("*.parquet")] # Get absolute paths as strings

        if not parquet_files:
            logger.warning("No parquet files found in the current directory. Cannot create 'all_data' view.")
            # Optionally, check if the view exists and drop it
            try:
                db.execute("DROP VIEW IF EXISTS all_data;")
                logger.info("Dropped existing 'all_data' view as no parquet files were found.")
            except Exception as drop_error:
                 logger.error(f"Error dropping existing view: {drop_error}")
            return False # Indicate setup did not complete fully

        logger.info(f"Found parquet files: {parquet_files}")

        # Use Python list formatting which is safe for file paths here
        # Ensure paths are properly quoted if they contain special characters, though Path usually handles this.
        # DuckDB's read_parquet handles a list of files.
        file_list_sql = ', '.join([f"'{f}'" for f in parquet_files])
        create_view_sql = f"CREATE OR REPLACE VIEW all_data AS SELECT * FROM read_parquet([{file_list_sql}], filename=true);"

        logger.info(f"Executing create/replace view query: {create_view_sql}")
        db.execute(create_view_sql)

        # Verify the view was created
        try:
            logger.info("Verifying view by executing SELECT query...")
            result = db.execute("SELECT * FROM all_data LIMIT 1").fetchdf()
            logger.info(f"Successfully queried view 'all_data'. View contains columns: {list(result.columns)}")
            # Update available_columns in config based on the actual view schema
            config['available_columns'] = list(result.columns)
            logger.info(f"Updated available columns: {config['available_columns']}")
            return True
        except Exception as e:
            logger.error(f"Failed to verify all_data view: {str(e)}")
            try:
                logger.info("Attempting to get view information...")
                db.execute("DESCRIBE all_data;")
            except Exception as describe_error:
                logger.error(f"Could not get view information: {str(describe_error)}")
            return False

    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        return False

# Test parquet reading (optional, can be removed if not needed)
try:
    test_files = list((Path(__file__).parent).glob("*.parquet"))
    if test_files:
        test_file = str(test_files[0])
        logger.info(f"Testing parquet reading with file: {test_file}")
        # Use read_parquet directly for testing one file
        result = db.execute(f"SELECT * FROM read_parquet('{test_file}') LIMIT 1").fetchdf()
        logger.info(f"Successfully read test parquet file. Schema: {list(result.columns)}")
    else:
        logger.warning("No parquet files found for read testing.")
except Exception as e:
    logger.error(f"Failed to read test parquet file: {str(e)}")

# Initialize database on startup
if not setup_database():
    logger.error("Initial database setup failed. View 'all_data' might not be available.")

@app.route("/query", methods=["POST"])
def find_parquet_files_route():
    """Finds parquet files matching the given filters."""
    try:
        # Ensure database is potentially set up (needed for read_parquet structure)
        # setup_database() # Re-running might be slow, consider checking connection status or view existence instead
        # For simplicity, we assume setup_database was run at startup.
        # If no parquet files exist, the read_parquet below will likely fail gracefully or return empty.

        data = request.json
        filters = data.get('filters', [])

        # Construct WHERE clause from filters
        where_clauses = []
        params = []
        if filters:
             # Ensure columns in filters are valid against dynamically loaded config
            available_cols = set(config.get("available_columns", [])) # Get columns from potentially updated config
            if not available_cols:
                 # Attempt setup again if columns aren't available, maybe it failed initially?
                 logger.warning("Available columns not detected, attempting database setup again.")
                 if not setup_database():
                     return jsonify({"error": "Database setup failed, cannot determine valid columns for filtering."}), 500
                 available_cols = set(config.get("available_columns", []))
                 if not available_cols:
                     return jsonify({"error": "Could not determine columns from parquet files."}), 500


            for f in filters:
                col = f.get("column")
                op = f.get("operator")
                val = f.get("value")

                if not all([col, op, val is not None]): # Check val explicitly for None
                    return jsonify({"error": f"Invalid filter format: {f}"}), 400
                if col not in available_cols:
                     # Add 'filename' as a potentially filterable column
                     if col != 'filename':
                          return jsonify({"error": f"Invalid column in filter: {col}. Available: {list(available_cols)}"}), 400


                # Basic SQL injection prevention: Use placeholders
                # Need to adjust operator handling for safety if user input defines it directly
                # For now, assume operators are from a safe list and handle value placeholders
                # Example: Handle 'IN' operator specifically if needed
                if op.upper() == "IN" or op.upper() == "NOT IN":
                     if isinstance(val, list):
                          placeholders = ', '.join(['?'] * len(val))
                          where_clauses.append(f"\"{col}\" {op.upper()} ({placeholders})") # Quote column names
                          params.extend(val)
                     else:
                          return jsonify({"error": f"Value for {op} must be a list."}), 400
                elif op.upper() == "LIKE":
                     where_clauses.append(f"\"{col}\" {op.upper()} ?")
                     params.append(f"%{val}%") # Add wildcards for LIKE
                else:
                    # Assume other operators are safe (e.g., =, !=, >, <, >=, <=)
                    where_clauses.append(f"\"{col}\" {op} ?") # Quote column names
                    params.append(val)

        # Base query to read all parquet files found during startup
        # We rely on setup_database having found the files.
        current_dir = Path(__file__).parent
        parquet_files = [str(f) for f in current_dir.glob("*.parquet")]
        if not parquet_files:
            return jsonify({"parquet_files": []}) # No files to query

        file_list_sql = ', '.join([f"'{f}'" for f in parquet_files])
        base_query = f"SELECT DISTINCT filename FROM read_parquet([{file_list_sql}], filename=true)"

        if where_clauses:
            query = f"{base_query} WHERE {' AND '.join(where_clauses)}"
        else:
            query = base_query # No filters, just get all distinct filenames

        logger.info(f"Executing file search query: {query} with params: {params}")

        # Execute the query using parameters
        result = db.execute(query, params).fetchall() # Use fetchall() for distinct filenames

        # Extract filenames from the result tuples
        matching_files = [row[0] for row in result] # Filename is the first column

        return jsonify({"parquet_files": matching_files})

    except Exception as e:
        logger.exception(f"Error in /query (find files) endpoint: {str(e)}") # Use logger.exception for stack trace
        return jsonify({"error": f"An internal error occurred: {str(e)}"}), 500

@app.route("/execute_sql", methods=["POST"])
def execute_sql():
    """Execute custom SQL query from the frontend."""
    try:
        # Ensure database view 'all_data' is available if the query uses it.
        # Re-running setup_database() could be inefficient. Check view existence?
        try:
            db.execute("SELECT 1 FROM all_data LIMIT 0;") # Quick check if view exists
        except Exception as view_error:
            logger.warning(f"'all_data' view might not be ready ({view_error}). Attempting setup...")
            if not setup_database():
                 # If setup fails here, the custom SQL might still work if it doesn't use 'all_data'
                 logger.error(f"{ERROR_DB_SETUP_FAILED} during custom SQL execution attempt.")
                 # Allow query execution anyway, but log the setup failure.


        data = request.json
        if not data or "sql" not in data:
            return jsonify({"error": "No SQL query provided"}), 400

        sql_query = data["sql"].strip()

        # Basic safety check: rudimentary blocklist (can be expanded)
        # This is NOT foolproof SQL injection prevention. Proper defense is complex.
        # Consider read-only mode for the connection if feasible.
        disallowed_keywords = ['DROP', 'DELETE', 'INSERT', 'UPDATE', 'ALTER', 'CREATE USER', 'GRANT']
        if any(keyword in sql_query.upper() for keyword in disallowed_keywords):
             # Allow CREATE VIEW specifically for our setup, maybe relax for CREATE TABLE/VIEW?
             # Fine-tune based on allowed operations. For now, disallow common destructive ones.
             # Check if it's the specific CREATE VIEW from setup_database? Hard to do reliably.
             # Let's be strict for now on custom SQL.
             # Re-allow CREATE VIEW if needed, but carefully.
             # Check specifically for CREATE VIEW all_data?
             # A simple check:
             # if not ('CREATE OR REPLACE VIEW all_data' in sql_query.upper() and 'READ_PARQUET' in sql_query.upper()):
             if not sql_query.upper().startswith("SELECT"): # A very basic read-only check
                  # Allow DESCRIBE and SHOW
                  if not (sql_query.upper().startswith("DESCRIBE") or sql_query.upper().startswith("SHOW")):
                        logger.warning(f"Potentially unsafe SQL query blocked: {sql_query}")
                        return jsonify({"error": "Query blocked for safety reasons (only SELECT, DESCRIBE, SHOW allowed)."}), 400


        logger.info(f"Executing custom SQL: {sql_query}")
        result_df = db.execute(sql_query).fetchdf() # fetchdf is convenient

        # Convert to dict for JSON serialization
        return jsonify({"results": result_df.to_dict(orient='records')})

    except Exception as e:
        logger.error(f"Error executing custom SQL: {str(e)}")
        # Provide more specific DuckDB errors if possible
        return jsonify({"error": f"SQL execution error: {str(e)}"}), 500

@app.route("/download/<path:filename>")
def download_file(filename):
    """Download a parquet file."""
    try:
        return send_file(
            filename,
            as_attachment=True,
            download_name=os.path.basename(filename),
            mimetype='application/octet-stream'
        )
    except Exception as e:
        logger.error(f"Error downloading file {filename}: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Make sure the host is set to '0.0.0.0' to be accessible externally if needed
    app.run(debug=True, host='0.0.0.0', port=5001) # Changed port to 5001 as an example

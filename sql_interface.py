import duckdb
import yaml
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import logging
from pathlib import Path

# Constants
ERROR_DB_SETUP_FAILED = "Failed to setup database"
PARQUET_FILE_PATTERN = "*.parquet"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for SQL Interface"""

    def __init__(self):
        self.data = self.load_config()

    def load_config(self):
        """Load configuration from yaml file"""
        config_path = Path(__file__).parent / "config.yaml"
        try:
            with open(config_path, 'r') as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logger.warning(f"Configuration file not found at {config_path}. Using default settings.")
            # Provide default config if file is missing
            return {"available_columns": []}  # Example default
        except Exception as e:
            logger.error(f"Error loading configuration: {e}")
            return {"available_columns": []}  # Fallback default

    def get(self, key, default=None):
        """Get a configuration value"""
        return self.data.get(key, default)

    def __getitem__(self, key):
        """Allow dictionary-like access to configuration"""
        return self.data[key]

    def __setitem__(self, key, value):
        """Allow dictionary-like setting of configuration"""
        self.data[key] = value


class Database:
    """Manages DuckDB database operations"""

    def __init__(self, config):
        self.config = config
        self.db = duckdb.connect(":memory:")
        self.setup_success = False

    def setup_database(self):
        """Initialize database and create view from local parquet files."""
        try:
            current_dir = Path(__file__).parent
            parquet_files = [str(f) for f in current_dir.glob(PARQUET_FILE_PATTERN)]  # Get absolute paths as strings

            if not parquet_files:
                logger.warning("No parquet files found in the current directory. Cannot create 'all_data' view.")
                # Optionally, check if the view exists and drop it
                try:
                    self.db.execute("DROP VIEW IF EXISTS all_data;")
                    logger.info("Dropped existing 'all_data' view as no parquet files were found.")
                except Exception as drop_error:
                    logger.error(f"Error dropping existing view: {drop_error}")
                return False  # Indicate setup did not complete fully

            logger.info(f"Found parquet files: {parquet_files}")

            # Use Python list formatting which is safe for file paths here
            # Ensure paths are properly quoted if they contain special characters, though Path usually handles this.
            # DuckDB's read_parquet handles a list of files.
            file_list_sql = ', '.join([f"'{f}'" for f in parquet_files])
            create_view_sql = f"CREATE OR REPLACE VIEW all_data AS SELECT * FROM read_parquet([{file_list_sql}], filename=true);"

            logger.info(f"Executing create/replace view query: {create_view_sql}")
            self.db.execute(create_view_sql)

            # Verify the view was created
            try:
                logger.info("Verifying view by executing SELECT query...")
                result = self.db.execute("SELECT * FROM all_data LIMIT 1").fetchdf()
                logger.info(f"Successfully queried view 'all_data'. View contains columns: {list(result.columns)}")
                # Update available_columns in config based on the actual view schema
                self.config['available_columns'] = list(result.columns)
                logger.info(f"Updated available columns: {self.config['available_columns']}")
                self.setup_success = True
                return True
            except Exception as e:
                logger.error(f"Failed to verify all_data view: {str(e)}")
                try:
                    logger.info("Attempting to get view information...")
                    self.db.execute("DESCRIBE all_data;")
                except Exception as describe_error:
                    logger.error(f"Could not get view information: {str(describe_error)}")
                return False

        except Exception as e:
            logger.error(f"Error setting up database: {str(e)}")
            return False

    def test_parquet_reading(self):
        """Test parquet reading (optional, can be removed if not needed)"""
        try:
            test_files = list((Path(__file__).parent).glob(PARQUET_FILE_PATTERN))
            if test_files:
                test_file = str(test_files[0])
                logger.info(f"Testing parquet reading with file: {test_file}")
                # Use read_parquet directly for testing one file
                result = self.db.execute(f"SELECT * FROM read_parquet('{test_file}') LIMIT 1").fetchdf()
                logger.info(f"Successfully read test parquet file. Schema: {list(result.columns)}")
            else:
                logger.warning("No parquet files found for read testing.")
        except Exception as e:
            logger.error(f"Failed to read test parquet file: {str(e)}")

    def execute_query(self, query, params=None):
        """Execute a query with optional parameters"""
        try:
            if params:
                return self.db.execute(query, params)
            else:
                return self.db.execute(query)
        except Exception as e:
            logger.error(f"Error executing query: {query}, Error: {str(e)}")
            raise


class SQLInterface:
    """Main interface for SQL operations and API endpoints"""

    def __init__(self):
        # Initialize components
        self.app = Flask(__name__)
        CORS(self.app)
        self.config = Config()
        self.db = Database(self.config)

        # Register routes
        self.register_routes()

        # Setup database on initialization
        if not self.db.setup_database():
            logger.error("Initial database setup failed. View 'all_data' might not be available.")

        # Test parquet reading
        self.db.test_parquet_reading()

    def register_routes(self):
        """Register all Flask routes"""
        self.app.route("/query", methods=["POST"])(self.find_parquet_files_route)
        self.app.route("/execute_sql", methods=["POST"])(self.execute_sql)
        self.app.route("/download/<filename>", methods=["GET"])(self.download_file)

    def _validate_columns(self):
        """Ensure columns are available, attempts setup if needed."""
        available_cols = set(self.config.get("available_columns", []))
        if not available_cols:
            # Attempt setup again if columns aren't available, maybe it failed initially?
            logger.warning("Available columns not detected, attempting database setup again.")
            if not self.db.setup_database():
                return None, (jsonify({"error": "Database setup failed, cannot determine valid columns for filtering."}), 500)
            available_cols = set(self.config.get("available_columns", []))
            if not available_cols:
                return None, (jsonify({"error": "Could not determine columns from parquet files."}), 500)
        return available_cols, None

    def _process_filter(self, filter_item, available_cols):
        """Process a single filter item and return clause and params"""
        col = filter_item.get("column")
        op = filter_item.get("operator")
        val = filter_item.get("value")

        # Validate filter format
        if not all([col, op, val is not None]):  # Check val explicitly for None
            return None, (jsonify({"error": f"Invalid filter format: {filter_item}"}), 400)
        
        # Validate column exists
        if col not in available_cols and col != 'filename':
            return None, (jsonify({"error": f"Invalid column in filter: {col}. Available: {list(available_cols)}"}), 400)

        # Process different operators
        clause = None
        params = []

        if op.upper() == "IN" or op.upper() == "NOT IN":
            if isinstance(val, list):
                placeholders = ', '.join(['?'] * len(val))
                clause = f"\"{col}\" {op.upper()} ({placeholders})"  # Quote column names
                params.extend(val)
            else:
                return None, (jsonify({"error": f"Value for {op} must be a list."}), 400)
        elif op.upper() == "LIKE":
            clause = f"\"{col}\" {op.upper()} ?"
            params.append(f"%{val}%")  # Add wildcards for LIKE
        else:
            # Assume other operators are safe (e.g., =, !=, >, <, >=, <=)
            clause = f"\"{col}\" {op} ?"  # Quote column names
            params.append(val)

        return (clause, params), None

    def _get_parquet_files(self):
        """Get list of parquet files in current directory"""
        current_dir = Path(__file__).parent
        return [str(f) for f in current_dir.glob(PARQUET_FILE_PATTERN)]

    def _build_query(self, parquet_files, where_clauses):
        """Build the SQL query from file list and where clauses"""
        file_list_sql = ', '.join([f"'{f}'" for f in parquet_files])
        base_query = f"SELECT DISTINCT filename FROM read_parquet([{file_list_sql}], filename=true)"

        if where_clauses:
            return f"{base_query} WHERE {' AND '.join(where_clauses)}"
        else:
            return base_query  # No filters, just get all distinct filenames

    def find_parquet_files_route(self):
        """Finds parquet files matching the given filters."""
        try:
            # Get filter data from request
            data = request.json
            filters = data.get('filters', [])

            # Initialize where clauses and params
            where_clauses = []
            params = []

            # Process filters if present
            if filters:
                # Validate columns
                available_cols, error_response = self._validate_columns()
                if error_response:
                    return error_response

                # Process each filter
                for filter_item in filters:
                    result, error_response = self._process_filter(filter_item, available_cols)
                    if error_response:
                        return error_response
                    
                    clause, filter_params = result
                    where_clauses.append(clause)
                    params.extend(filter_params)

            # Get parquet files
            parquet_files = self._get_parquet_files()
            if not parquet_files:
                return jsonify({"parquet_files": []})  # No files to query

            # Build and execute query
            query = self._build_query(parquet_files, where_clauses)
            logger.info(f"Executing file search query: {query} with params: {params}")
            
            result = self.db.execute_query(query, params).fetchall()
            
            # Extract filenames from the result tuples
            matching_files = [row[0] for row in result]  # Filename is the first column

            return jsonify({"parquet_files": matching_files})

        except Exception as e:
            logger.exception(f"Error in /query (find files) endpoint: {str(e)}")  # Use logger.exception for stack trace
            return jsonify({"error": f"An internal error occurred: {str(e)}"}), 500

    def execute_sql(self):
        """Execute custom SQL query from the frontend."""
        try:
            # Ensure database view 'all_data' is available if the query uses it.
            # Re-running setup_database() could be inefficient. Check view existence?
            try:
                self.db.execute_query("SELECT 1 FROM all_data LIMIT 0;")  # Quick check if view exists
            except Exception as view_error:
                logger.warning(f"'all_data' view might not be ready ({view_error}). Attempting setup...")
                if not self.db.setup_database():
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
                # Let's be strict for now on custom SQL.
                if not sql_query.upper().startswith("SELECT"):  # A very basic read-only check
                    # Allow DESCRIBE and SHOW
                    if not (sql_query.upper().startswith("DESCRIBE") or sql_query.upper().startswith("SHOW")):
                        logger.warning(f"Potentially unsafe SQL query blocked: {sql_query}")
                        return jsonify({"error": "Query blocked for safety reasons (only SELECT, DESCRIBE, SHOW allowed)."}), 400

            logger.info(f"Executing custom SQL: {sql_query}")
            result_df = self.db.execute_query(sql_query).fetchdf()  # fetchdf is convenient

            # Convert to dict for JSON serialization
            return jsonify({
                "results": result_df.to_dict(orient='records'),
                "columns": list(result_df.columns),
                "row_count": len(result_df)
            })

        except Exception as e:
            logger.error(f"Error executing custom SQL: {str(e)}")
            # Provide more specific DuckDB errors if possible
            return jsonify({"error": f"SQL execution error: {str(e)}"}), 500

    def download_file(self, filename):
        """Download a parquet file."""
        try:
            # Basic security validation - ensure the file exists in our directory
            current_dir = Path(__file__).parent
            file_path = current_dir / filename
            
            if not file_path.exists() or not file_path.is_file() or file_path.suffix != '.parquet':
                return jsonify({"error": "File not found or invalid"}), 404
            
            return send_file(file_path, as_attachment=True, download_name=filename)
        except Exception as e:
            logger.exception(f"Error downloading file {filename}: {str(e)}")
            return jsonify({"error": f"Error downloading file: {str(e)}"}), 500

    def run(self, debug=True, host='0.0.0.0', port=5001):
        """Run the Flask application"""
        self.app.run(debug=debug, host=host, port=port)


if __name__ == '__main__':
    # Create the SQL Interface instance
    sql_interface = SQLInterface()
    
    # Run the application
    # Make sure the host is set to '0.0.0.0' to be accessible externally if needed
    sql_interface.run(debug=True, host='0.0.0.0', port=5001)

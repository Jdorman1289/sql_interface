import duckdb
import yaml
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import logging
from pathlib import Path
from sql_queries import *
import os

# Constants
ERROR_DB_SETUP_FAILED = "Failed to setup database"

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load configuration
def load_config():
    config_path = Path(__file__).parent / "config.yaml"
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

config = load_config()

# Create an in-memory DuckDB connection
db = duckdb.connect(":memory:")

def setup_database():
    """Initialize database and create view."""
    try:
        # Look for parquet files in the current directory
        current_dir = Path(__file__).parent
        parquet_files = list(current_dir.glob("*.parquet"))
        
        if not parquet_files:
            logger.warning("No parquet files found in the current directory")
            return False
        
        logger.info(f"Found parquet files: {parquet_files}")
        
        # Drop existing view if it exists
        drop_query = drop_all_data_view()
        logger.info(f"Executing drop query: {drop_query}")
        db.execute(drop_query)
        
        # Create new view
        create_query = create_all_data_view()
        logger.info(f"Executing create query: {create_query}")
        db.execute(create_query)
        
        # Verify the view was created
        try:
            logger.info("Verifying view by executing SELECT query...")
            result = db.execute("SELECT * FROM all_data LIMIT 1").fetchdf()
            logger.info(f"Successfully queried view. Got {len(result)} rows")
            return True
        except Exception as e:
            logger.error(f"Failed to verify all_data view: {str(e)}")
            # Try to get more information about the view
            try:
                logger.info("Attempting to get view information...")
                db.execute("DESCRIBE all_data")
            except Exception as describe_error:
                logger.error(f"Could not get view information: {str(describe_error)}")
            return False
            
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        return False

# Test parquet reading
try:
    test_file = str(Path(__file__).parent / 'data.parquet')
    logger.info(f"Testing parquet reading with file: {test_file}")
    result = db.execute(f"SELECT * FROM read_parquet('{test_file}') LIMIT 1").fetchdf()
    logger.info(f"Successfully read test parquet file. Schema: {list(result.columns)}")
except Exception as e:
    logger.error(f"Failed to read test parquet file: {str(e)}")

# Initialize database on startup
if not setup_database():
    logger.error("Failed to initialize database")

@app.route("/config", methods=["GET"])
def get_config():
    """Get configuration including available columns and operators."""
    try:
        logger.info("Loading configuration...")
        response_data = {
            "available_columns": config["available_columns"],
            "operators": [
                {"value": "=", "label": "equals"},
                {"value": "!=", "label": "not equals"},
                {"value": ">", "label": "greater than"},
                {"value": "<", "label": "less than"},
                {"value": ">=", "label": "greater than or equal"},
                {"value": "<=", "label": "less than or equal"},
                {"value": "IN", "label": "in list"},
                {"value": "NOT IN", "label": "not in list"},
                {"value": "LIKE", "label": "contains"},
            ]
        }
        logger.info(f"Configuration response: {response_data}")
        return jsonify(response_data)
    except Exception as e:
        logger.error(f"Error in /config endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/distinct", methods=["POST"])
def get_distinct():
    """Get distinct values for a column."""
    try:
        data = request.json
        if not data or "column" not in data:
            return jsonify({"error": "No column specified"}), 400
            
        column = data["column"]
        if column not in config["available_columns"]:
            return jsonify({"error": f"Invalid column: {column}"}), 400

        if not setup_database():
            return jsonify({"error": "Failed to setup database"}), 500
            
        result = db.execute(get_distinct_values(column)).fetchall()
        values = [val[0] for val in result if val[0] is not None]
        return jsonify({"values": values})
    except Exception as e:
        logger.error(f"Error in /distinct endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/query", methods=["POST"])
def handle_query():
    """Handle complex queries with filters, ordering, and limits."""
    try:
        # Ensure database is set up
        if not setup_database():
            return jsonify({"error": ERROR_DB_SETUP_FAILED}), 500        
        data = request.json
        mode = data.get('mode', 'data')
        filters = data.get('filters', [])
        
        if mode == 'data':
            orders = data.get('orders', [])
            limit = data.get('limit')
            
            # Validate filters
            for f in filters:
                if not all(k in f for k in ["column", "operator", "value"]):
                    return jsonify({"error": "Invalid filter format"}), 400
                if f["column"] not in config["available_columns"]:
                    return jsonify({"error": f"Invalid column in filter: {f['column']}"}), 400

            # Validate ordering
            for o in orders:
                if not all(k in o for k in ["column", "direction"]):
                    return jsonify({"error": "Invalid order format"}), 400
                if o["column"] not in config["available_columns"]:
                    return jsonify({"error": f"Invalid column in order: {o['column']}"}), 400
                if o["direction"] not in ["ASC", "DESC"]:
                    return jsonify({"error": f"Invalid direction in order: {o['direction']}"}), 400

            if limit is not None and not isinstance(limit, int):
                return jsonify({"error": "Limit must be an integer"}), 400

            # Execute the query
            query = get_filtered_data(filters, orders, limit)
            logger.info(f"Executing query: {query}")
            result = db.execute(query).fetchdf()
            
            # Convert to dict for JSON serialization
            return jsonify({"results": result.to_dict(orient='records')})
        else:
            # Find matching parquet files
            query = find_matching_parquet_files(filters)
            logger.info(f"Executing query: {query}")
            result = db.execute(query).fetchdf()
            
            # Get list of unique parquet files and extract just the filenames
            parquet_files = [Path(path).name for path in result['_file_path_'].unique()]
            return jsonify({"parquet_files": parquet_files})
            
    except Exception as e:
        logger.error(f"Error in /query endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/execute_sql", methods=["POST"])
def execute_sql():
    """Execute custom SQL query from the frontend."""
    try:
        # Ensure database is set up
        if not setup_database():
            return jsonify({"error": ERROR_DB_SETUP_FAILED}), 500        
        data = request.json
        if not data or "sql" not in data:
            return jsonify({"error": "No SQL query provided"}), 400
            
        sql_query = data["sql"].strip()
        
        # Basic security check - only allow SELECT statements
        if not sql_query.upper().startswith("SELECT"):
            return jsonify({"error": "Only SELECT queries are allowed"}), 400
        
        # Execute the query
        logger.info(f"Executing custom SQL query: {sql_query}")
        result = db.execute(sql_query).fetchdf()
        
        # Convert to dict for JSON serialization
        return jsonify({"results": result.to_dict(orient='records')})
            
    except Exception as e:
        logger.error(f"Error in /execute_sql endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

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

if __name__ == "__main__":
    app.run(debug=True)

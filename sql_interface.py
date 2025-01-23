import duckdb
import glob
import yaml
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from pathlib import Path
from sql_queries import *
from typing import List, Dict, Any

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
        parquet_files = glob.glob("*.parquet")
        if not parquet_files:
            logger.warning("No parquet files found in the current directory")
            return False
        
        logger.info(f"Found parquet files: {parquet_files}")
        db.execute(drop_all_data_view())
        db.execute(create_all_data_view())
        return True
    except Exception as e:
        logger.error(f"Error setting up database: {str(e)}")
        return False

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
            ],
            "ui": config["ui"]
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
        data = request.json
        if not data:
            return jsonify({"error": "No request data provided"}), 400
            
        # Validate filters
        filters = data.get("filters", [])
        for f in filters:
            if not all(k in f for k in ["column", "operator", "value"]):
                return jsonify({"error": "Invalid filter format"}), 400
            if f["column"] not in config["available_columns"]:
                return jsonify({"error": f"Invalid column in filter: {f['column']}"}), 400

        # Validate ordering
        orders = data.get("orders", [])
        for o in orders:
            if not all(k in o for k in ["column", "direction"]):
                return jsonify({"error": "Invalid order format"}), 400
            if o["column"] not in config["available_columns"]:
                return jsonify({"error": f"Invalid column in order: {o['column']}"}), 400
            if o["direction"] not in ["ASC", "DESC"]:
                return jsonify({"error": f"Invalid direction in order: {o['direction']}"}), 400

        limit = data.get("limit")
        if limit is not None and not isinstance(limit, int):
            return jsonify({"error": "Limit must be an integer"}), 400

        if not setup_database():
            return jsonify({"error": "Failed to setup database"}), 500
            
        query = get_filtered_data(filters, orders, limit)
        logger.info(f"Executing query: {query}")
        result = db.execute(query).fetchall()
        column_names = [col[0] for col in db.execute(query).description]
        
        # Convert results to list of dictionaries
        formatted_result = [
            dict(zip(column_names, row))
            for row in result
        ]
        
        logger.info(f"Query returned {len(formatted_result)} rows")
        return jsonify({
            "result": formatted_result,
            "query": query  # Include the query for debugging
        })
    except Exception as e:
        logger.error(f"Error in /query endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

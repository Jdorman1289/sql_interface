import duckdb
import glob
import yaml
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging
from pathlib import Path

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
PRIMARY_COL = config['primary_filter']['column']
SECONDARY_COL = config['secondary_filter']['column']

# Create an in-memory DuckDB connection
db = duckdb.connect(":memory:")

def get_primary_values():
    try:
        # Create a view combining all parquet files
        parquet_files = glob.glob("*.parquet")
        if not parquet_files:
            logger.warning("No parquet files found in the current directory")
            return []
        
        logger.info(f"Found parquet files: {parquet_files}")
        
        # Create a view that combines all parquet files
        db.execute("DROP VIEW IF EXISTS all_data")
        db.execute("CREATE VIEW all_data AS SELECT * FROM read_parquet('*.parquet')")
        
        # Get unique primary values
        query = f"SELECT DISTINCT {PRIMARY_COL} FROM all_data ORDER BY {PRIMARY_COL}"
        result = db.execute(query).fetchall()
        values = [val[0] for val in result if val[0] is not None]
        logger.info(f"Found primary values: {values}")
        return values
    except Exception as e:
        logger.error(f"Error getting primary values: {str(e)}")
        raise

@app.route("/config", methods=["GET"])
def get_config():
    try:
        return jsonify({
            "primary_filter": config["primary_filter"],
            "secondary_filter": config["secondary_filter"],
            "ui": config["ui"]
        })
    except Exception as e:
        logger.error(f"Error in /config endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/primary", methods=["GET"])
def get_primary():
    try:
        values = get_primary_values()
        return jsonify({"values": values})
    except Exception as e:
        logger.error(f"Error in /primary endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/secondary", methods=["POST"])
def get_secondary():
    try:
        data = request.json
        if not data or "primary_values" not in data:
            return jsonify({"error": "No primary values provided"}), 400
            
        primary_values = data.get("primary_values", [])
        if not primary_values:
            return jsonify({"values": []})

        logger.info(f"Getting secondary values for primary values: {primary_values}")
        
        # Create a view combining all parquet files
        db.execute("DROP VIEW IF EXISTS all_data")
        db.execute("CREATE VIEW all_data AS SELECT * FROM read_parquet('*.parquet')")
        
        # Build the WHERE clause for primary filtering
        primary_filter = f"{PRIMARY_COL} IN (" + ",".join(f"'{val}'" for val in primary_values) + ")"
        query = f"SELECT DISTINCT {SECONDARY_COL} FROM all_data WHERE {primary_filter} ORDER BY {SECONDARY_COL}"
        
        logger.info(f"Executing query: {query}")
        result = db.execute(query).fetchall()
        values = [val[0] for val in result if val[0] is not None]
        
        logger.info(f"Found {len(values)} secondary values")
        return jsonify({"values": values})
    except Exception as e:
        logger.error(f"Error in /secondary endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/query", methods=["POST"])
def handle_query():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No request data provided"}), 400
            
        primary_values = data.get("primary_values", [])
        secondary_values = data.get("secondary_values", [])
        
        if not primary_values:
            return jsonify({"error": "No primary values selected"}), 400

        logger.info(f"Querying for primary values: {primary_values} and secondary values: {secondary_values}")
        
        # Create a view combining all parquet files
        db.execute("DROP VIEW IF EXISTS all_data")
        db.execute("CREATE VIEW all_data AS SELECT * FROM read_parquet('*.parquet')")
        
        # Build the WHERE clause for filtering
        conditions = []
        conditions.append(f"{PRIMARY_COL} IN (" + ",".join(f"'{val}'" for val in primary_values) + ")")
        
        if secondary_values:
            conditions.append(f"{SECONDARY_COL} IN (" + ",".join(f"'{val}'" for val in secondary_values) + ")")
        
        where_clause = " AND ".join(conditions)
        query = f"SELECT * FROM all_data WHERE {where_clause}"
        
        logger.info(f"Executing query: {query}")
        result = db.execute(query).fetchall()
        column_names = [col[0] for col in db.execute(query).description]
        
        # Convert results to list of dictionaries
        formatted_result = [
            dict(zip(column_names, row))
            for row in result
        ]
        
        logger.info(f"Query returned {len(formatted_result)} rows")
        return jsonify({"result": formatted_result})
    except Exception as e:
        logger.error(f"Error in /query endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True)

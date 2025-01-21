import duckdb
import glob
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

app = Flask(__name__)
CORS(app)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create an in-memory DuckDB connection
db = duckdb.connect(":memory:")

def get_available_states():
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
        
        # Get unique states
        result = db.execute("SELECT DISTINCT state_name FROM all_data ORDER BY state_name").fetchall()
        states = [state[0] for state in result if state[0] is not None]
        logger.info(f"Found states: {states}")
        return states
    except Exception as e:
        logger.error(f"Error getting states: {str(e)}")
        raise

@app.route("/states", methods=["GET"])
def get_states():
    try:
        states = get_available_states()
        return jsonify({"states": states})
    except Exception as e:
        logger.error(f"Error in /states endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/cities", methods=["POST"])
def get_cities():
    try:
        data = request.json
        if not data or "states" not in data:
            return jsonify({"error": "No states provided"}), 400
            
        selected_states = data.get("states", [])
        if not selected_states:
            return jsonify({"cities": []})

        logger.info(f"Getting cities for states: {selected_states}")
        
        # Create a view combining all parquet files
        db.execute("DROP VIEW IF EXISTS all_data")
        db.execute("CREATE VIEW all_data AS SELECT * FROM read_parquet('*.parquet')")
        
        # Build the WHERE clause for state filtering
        state_filter = "state_name IN (" + ",".join(f"'{state}'" for state in selected_states) + ")"
        query = f"SELECT DISTINCT city FROM all_data WHERE {state_filter} ORDER BY city"
        
        logger.info(f"Executing query: {query}")
        result = db.execute(query).fetchall()
        cities = [city[0] for city in result if city[0] is not None]
        
        logger.info(f"Found {len(cities)} cities")
        return jsonify({"cities": cities})
    except Exception as e:
        logger.error(f"Error in /cities endpoint: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/query", methods=["POST"])
def handle_query():
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No request data provided"}), 400
            
        selected_states = data.get("states", [])
        selected_cities = data.get("cities", [])
        
        if not selected_states:
            return jsonify({"error": "No states selected"}), 400

        logger.info(f"Querying for states: {selected_states} and cities: {selected_cities}")
        
        # Create a view combining all parquet files
        db.execute("DROP VIEW IF EXISTS all_data")
        db.execute("CREATE VIEW all_data AS SELECT * FROM read_parquet('*.parquet')")
        
        # Build the WHERE clause for state and city filtering
        conditions = []
        conditions.append("state_name IN (" + ",".join(f"'{state}'" for state in selected_states) + ")")
        
        if selected_cities:
            conditions.append("city IN (" + ",".join(f"'{city}'" for city in selected_cities) + ")")
        
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

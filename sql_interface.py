import duckdb
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
PARQUET_FILE = "data.parquet"

# Enable CORS for all routes
CORS(app)

# Create an in-memory DuckDB connection
db = duckdb.connect(":memory:")

# Load data from Parquet file into memory
db.execute(f"CREATE TABLE data AS SELECT * FROM read_parquet('{PARQUET_FILE}')")


def execute_query(query):
    result = db.execute(query).fetchall()
    column_names = db.execute(query).description
    # Convert the query result into a list of dictionaries, where each dictionary represents a row
    # with column names as keys and corresponding values
    return [dict(zip([column[0] for column in column_names], row)) for row in result]


@app.route("/query", methods=["POST"])
def handle_query():
    query = request.json.get("query")
    if not query:
        return jsonify({"error": "No query provided"}), 400

    try:
        result = execute_query(query)

        # If the query modifies data, save the changes back to the Parquet file
        if query.strip().upper().startswith(("INSERT", "UPDATE", "DELETE")):
            db.execute(
                f"COPY data TO '{PARQUET_FILE}' (FORMAT PARQUET, OVERWRITE TRUE)"
            )

        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)

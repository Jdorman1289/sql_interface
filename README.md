
# SQL Query Client with DuckDB and Parquet

This project demonstrates a simple SQL query client that uses DuckDB to query data stored in a Parquet file. It consists of a Python backend and an HTML/JavaScript frontend.

## Setup

1. Install the required Python packages:
   ```
   pip install -r requirements.txt
   ```

2. Convert your CSV data to Parquet format:
   ```
   python csv_to_parquet.py
   ```

3. Start the Flask server:
   ```
   python sql_interface.py
   ```

4. Open `client.html` in your web browser to use the SQL query interface.

## Usage

1. Enter your SQL query in the text area.
2. Click "Execute Query" to run the query.
3. Results will be displayed in a table below the query input.

## Features

- Query Parquet data using SQL
- Support for SELECT, INSERT, UPDATE, and DELETE operations
- Results displayed in a formatted table
- Error handling for invalid queries

## File Structure

- `csv_to_parquet.py`: Script to convert CSV to Parquet format
- `sql_interface.py`: Flask server that handles SQL queries using DuckDB
- `client.html`: Frontend interface for entering queries and displaying results
- `data.parquet`: Parquet file containing the data (generated from CSV)

Enjoy querying your data with SQL!

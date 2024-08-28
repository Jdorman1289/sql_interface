import duckdb

# Connect to an in-memory database
con = duckdb.connect(":memory:")

# Register the Parquet file as a table
con.execute("CREATE TABLE my_data AS SELECT * FROM parquet_scan('data.parquet')")

# Run SQL queries on the data
result = con.execute("SELECT * FROM my_data LIMIT 5").fetchall()
print(result)

# Run more complex queries example
result = con.execute("""
    SELECT city, AVG(population) as avg_population
    FROM my_data
    GROUP BY city
    ORDER BY avg_population DESC
    LIMIT 10
""").fetchall()
print(result)

# Close the connection when done
con.close()

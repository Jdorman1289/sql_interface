import pandas as pd

# Load the CSV file into a pandas DataFrame
df = pd.read_csv('data.csv')

# Convert the DataFrame to a Parquet file
df.to_parquet('data.parquet')
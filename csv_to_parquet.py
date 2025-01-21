import pandas as pd

# Load the CSVs file into a pandas DataFrame
df = pd.read_csv('data.csv')
df2 = pd.read_csv('data2.csv')
df3 = pd.read_csv('data3.csv')

# Convert the DataFrames to Parquet files
df.to_parquet('data.parquet')
df2.to_parquet('data2.parquet')
df3.to_parquet('data3.parquet')
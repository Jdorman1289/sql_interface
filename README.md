# Parquet Data Explorer

A web interface for exploring and querying Parquet files using DuckDB. This tool provides an intuitive way to filter and analyze Parquet data through a modern web interface.

## Features

- Interactive query interface powered by DuckDB
- Dynamic filtering system
- Support for multiple Parquet files
- Memory-efficient data handling
- Modern web UI with real-time updates

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
python sql_interface.py
```

3. Open or run the client.html

## Configuration

The interface can be customized through the  `config.yaml` file. This configuration file allows you to:
- Specify the headers from your Parquet files for accurate querying
- Customize the display names of columns in the UI

For questions or issues, please open a GitHub issue.

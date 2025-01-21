# Parquet Data Explorer

A simple web interface for exploring Parquet files using DuckDB. This tool allows you to filter and query Parquet data through an intuitive web interface.

## Features

- Fast querying using DuckDB
- Configurable primary and secondary filters
- Memory-efficient handling of large Parquet files
- Modern web interface with dynamic filtering

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Place your Parquet files in the project directory

3. Configure the interface using `config.yaml`:
```yaml
# Example config.yaml
primary_filter:
  name: "Primary Location"    # Display name for first dropdown
  column: "state_name"        # Column name in Parquet files
  
secondary_filter:
  name: "Secondary Location"  # Display name for second dropdown
  column: "city"             # Column name in Parquet files
  depends_on: "primary"      # This filter depends on primary selection

ui:
  title: "Location Data Explorer"
  primary_placeholder: "Select primary locations..."
  secondary_placeholder: "Select secondary locations..."
  query_button_text: "Query Selected Data"
  clear_button_text: "Clear"
  no_results_text: "No results found"
  loading_text: "Loading..."
```

4. Start the server:
```bash
python sql_interface.py
```

5. Open `client.html` in your web browser

## Configuration

The `config.yaml` file allows you to customize:
- Column names used for filtering
- Display names and labels
- UI text and messages

This makes the interface adaptable to different types of Parquet data. For example, you could use it for:
- Products and Categories
- Departments and Employees
- Authors and Books
- Any hierarchical data in Parquet format

## Requirements

- Python 3.x
- DuckDB
- Flask
- PyYAML
- Modern web browser with JavaScript enabled

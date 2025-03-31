# SQL Interface for Parquet Files

A web interface for querying and exploring Parquet files using DuckDB with an object-oriented design.

## Core Components

- **Config**: Manages configuration from `config.yaml`
- **Database**: Handles DuckDB connections and query execution
- **SQLInterface**: Main application with Flask routes and business logic

## Features

- Filter and query Parquet files via SQL
- Interactive web interface with dynamic filtering
- Export results to CSV
- Memory-efficient processing with DuckDB

## Setup

```bash
pip install -r requirements.txt
python sql_interface.py
```

Then open `client.html` in a browser.

## Configuration

Edit `config.yaml` to customize column display names and other settings.

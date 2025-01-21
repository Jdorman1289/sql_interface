# State and City Data Explorer with DuckDB

This project provides an efficient interface to explore data stored in Parquet files by state and city. It uses DuckDB for high-performance querying without loading all data into memory, along with a modern web interface for easy data exploration.

## Features

- **Efficient Data Handling**: Uses DuckDB to query Parquet files directly without loading all data into memory
- **Hierarchical Selection**: Filter data by states first, then by cities within those states
- **Multi-Select Capability**: Select multiple states and cities at once
- **Responsive UI**: Modern interface that works well on both desktop and mobile devices
- **Real-time Updates**: City list updates automatically based on selected states
- **Easy Reset**: Clear button to quickly start a new query

## Setup

1. Install the required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

2. Ensure your Parquet files are in the same directory as the application. The files should have:
   - A `state_name` column for state information
   - A `city` column for city information

3. Start the Flask server:
   ```bash
   python sql_interface.py
   ```

4. Open `client.html` in your web browser to use the interface.

## Usage

1. **Select States**:
   - Use the state dropdown to select one or more states
   - The city dropdown will automatically update with available cities

2. **Filter by Cities** (Optional):
   - Select one or more cities from the updated city dropdown
   - If no cities are selected, you'll see data for all cities in the selected states

3. **View Data**:
   - Click "Query Selected Data" to see the results
   - Results are displayed in a formatted table below

4. **Start Over**:
   - Use the "Clear Results" button to reset selections and results

## Technical Details

- **Backend**: Python Flask server with DuckDB for efficient Parquet file querying
- **Frontend**: HTML/JavaScript with Select2 for enhanced dropdowns
- **Data Format**: Parquet files (column-oriented storage format)
- **Memory Efficiency**: Queries are executed directly on Parquet files without loading entire datasets into memory

## File Structure

- `sql_interface.py`: Flask backend with DuckDB integration
- `client.html`: Frontend interface with state/city selection
- `requirements.txt`: Python package dependencies
- `*.parquet`: Your data files in Parquet format

## Dependencies

- Python 3.x
- DuckDB
- Flask
- Flask-CORS
- Select2 (frontend)
- Bootstrap 5 (frontend)

## Performance

The application is designed to be memory-efficient:
- Uses DuckDB's lazy evaluation
- Only reads necessary columns and rows
- Leverages Parquet's column-oriented nature
- Implements predicate pushdown for efficient filtering

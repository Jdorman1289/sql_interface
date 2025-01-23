"""SQL query operations for the interface."""
from typing import Dict, List, Any, Optional
from pathlib import Path
import glob

def create_all_data_view():
    current_dir = str(Path(__file__).parent.absolute())
    # Get list of parquet files
    parquet_files = glob.glob(f"{current_dir}/*.parquet")
    
    # Create UNION ALL query for each parquet file
    union_queries = []
    for file_path in parquet_files:
        union_queries.append(f"""
            SELECT 
                *,
                '{file_path}' as _file_path_
            FROM read_parquet('{file_path}')
        """)
    
    return f"""
    CREATE VIEW all_data AS 
    {' UNION ALL '.join(union_queries)}
    """

def drop_all_data_view():
    return "DROP VIEW IF EXISTS all_data"

def get_distinct_values(column: str):
    return f"SELECT DISTINCT {column} FROM all_data ORDER BY {column}"

def build_filter_condition(filters: List[Dict[str, Any]]) -> str:
    """Build WHERE clause from filter conditions."""
    if not filters:
        return "1=1"  # No filters means match everything
        
    conditions = []
    for f in filters:
        column = f["column"]
        operator = f["operator"]
        value = f["value"]
        
        if operator.upper() in ("IN", "NOT IN"):
            if isinstance(value, str):
                value = [value]  # Convert single value to list
            value_list = ", ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in value)
            conditions.append(f"{column} {operator} ({value_list})")
        elif operator.upper() == "LIKE":
            conditions.append(f"{column} LIKE '%{value}%'")
        else:
            if isinstance(value, str):
                conditions.append(f"{column} {operator} '{value}'")
            else:
                conditions.append(f"{column} {operator} {value}")
    
    return " AND ".join(conditions)

def build_order_clause(orders: List[Dict[str, str]]) -> str:
    if not orders:
        return ""
    
    order_parts = []
    for order in orders:
        order_parts.append(f"{order['column']} {order['direction']}")
    
    return "ORDER BY " + ", ".join(order_parts)

def build_limit_clause(limit: Optional[int]) -> str:
    return f"LIMIT {limit}" if limit is not None else ""

def get_filtered_data(filters: List[Dict[str, Any]] = None, 
                     orders: List[Dict[str, str]] = None,
                     limit: Optional[int] = None) -> str:
    """Generate SQL query with filters, ordering, and limit."""
    where_clause = build_filter_condition(filters or [])
    order_clause = build_order_clause(orders or [])
    limit_clause = build_limit_clause(limit)
    
    clauses = [
        "SELECT *",
        "FROM all_data",
        f"WHERE {where_clause}"
    ]
    
    if order_clause:
        clauses.append(order_clause)
    if limit_clause:
        clauses.append(limit_clause)
    
    return " ".join(clauses)

def find_matching_parquet_files(filters: List[Dict[str, Any]]) -> str:
    """Build a query to find parquet files containing matching records."""
    where_clause = build_filter_condition(filters)
    return f"""
    SELECT DISTINCT _file_path_
    FROM all_data
    WHERE {where_clause}
    ORDER BY _file_path_
    """

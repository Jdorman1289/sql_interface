"""SQL query operations for the interface."""
from typing import Dict, List, Any, Optional

def create_all_data_view():
    return "CREATE VIEW all_data AS SELECT * FROM read_parquet('*.parquet')"

def drop_all_data_view():
    return "DROP VIEW IF EXISTS all_data"

def get_distinct_values(column: str):
    return f"SELECT DISTINCT {column} FROM all_data ORDER BY {column}"

def build_filter_condition(filters: List[Dict[str, Any]]) -> str:
    """Build WHERE clause from filter conditions.
    
    filters format: [
        {
            "column": "population",
            "operator": "<",
            "value": 910
        },
        ...
    ]
    """
    if not filters:
        return "1=1"  # No filters means match everything
        
    conditions = []
    for f in filters:
        column = f["column"]
        operator = f["operator"]
        value = f["value"]
        
        # Handle different value types
        if isinstance(value, str):
            value = f"'{value}'"
        elif isinstance(value, (list, tuple)):
            value = f"({','.join(repr(v) if isinstance(v, (int, float)) else f"'{v}'" for v in value)})"
            
        conditions.append(f"{column} {operator} {value}")
    
    return " AND ".join(conditions)

def build_order_clause(orders: List[Dict[str, str]]) -> str:
    """Build ORDER BY clause from order specifications.
    
    orders format: [
        {
            "column": "population",
            "direction": "DESC"
        },
        ...
    ]
    """
    if not orders:
        return ""
        
    order_terms = [f"{o['column']} {o['direction']}" for o in orders]
    return f"ORDER BY {', '.join(order_terms)}"

def build_limit_clause(limit: Optional[int]) -> str:
    """Build LIMIT clause if limit is specified."""
    return f"LIMIT {limit}" if limit is not None else ""

def get_filtered_data(filters: List[Dict[str, Any]] = None, 
                     orders: List[Dict[str, str]] = None,
                     limit: Optional[int] = None) -> str:
    """Generate SQL query with filters, ordering, and limit.
    
    Example:
    filters = [
        {"column": "population", "operator": "<", "value": 910},
        {"column": "state_name", "operator": "IN", "value": ["Texas", "California"]}
    ]
    orders = [
        {"column": "population", "direction": "DESC"}
    ]
    limit = 3
    """
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

"""
SQL Query Tool for LangGraph Agent
Allows the LLM to execute SQL queries against spreadsheet data
loaded into per-user SQLite databases.
"""

from typing import Any, Dict

from core.services.sqlite_manager import SQLiteManager


async def execute_sql_query(
    user_id: str, thread_id: str, query: str, max_rows: int = 500
) -> str:
    """
    Execute a SQL query against the user's spreadsheet data.

    Args:
        user_id: The user who owns the data
        thread_id: The thread containing the spreadsheet
        query: SQL SELECT query to execute
        max_rows: Maximum rows to return. Pass None for unlimited (used by NLP extraction).

    Returns:
        A formatted string with the query results or an error message
    """
    if not SQLiteManager.has_spreadsheet_data(user_id, thread_id):
        return "No spreadsheet data is available for SQL querying in this thread."

    result = SQLiteManager.execute_query(user_id, thread_id, query, max_rows=max_rows)

    if result["success"]:
        output_parts = []
        output_parts.append(f"**Query executed successfully.**")
        output_parts.append(f"Rows returned: {result['row_count']}")
        if result.get("truncated"):
            shown = max_rows if max_rows else result["row_count"]
            output_parts.append(
                f"(Showing first {shown} of {result['row_count']} rows)"
            )
        output_parts.append("")
        output_parts.append(result["data"])
        return "\n".join(output_parts)
    else:
        return f"SQL query failed: {result['error']}"


def get_sql_schema(user_id: str, thread_id: str) -> str:
    """
    Get the SQL schema description for the user's loaded spreadsheets.

    Returns:
        A formatted string describing all available tables and columns,
        or None if no spreadsheet data exists.
    """
    return SQLiteManager.get_schema(user_id, thread_id)


def get_sql_query_sources(user_id: str, thread_id: str, query: str) -> Dict[str, Any]:
    """Return source metadata (tables/documents) for a SQL query."""
    return SQLiteManager.get_query_source_details(user_id, thread_id, query)

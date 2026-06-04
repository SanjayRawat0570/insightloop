from pydantic import BaseModel, ValidationError
from typing import Dict, Any
import re

class QueryWriterError(Exception):
    pass

class QueryRequest(BaseModel):
    question: str
    schema: str
    dialect: str = "postgres"

class QueryResponse(BaseModel):
    sql: str
    explanation: str | None = None

SYSTEM_PROMPT = """
You are an expert SQL engineer. Always use table aliases, never use SELECT *, add LIMIT 1000, and return ONLY the SQL.
"""

def validate_sql(sql: str) -> bool:
    # Very lightweight validation
    if not sql.strip().lower().startswith("select"):
        return False
    if "select *" in sql.lower():
        return False
    return True


def generate_sql(payload: Dict[str, Any]) -> Dict[str, Any]:
    req = QueryRequest(**payload)
    # For scaffold: craft a naive SQL using schema hints (this is a placeholder but valid SQL)
    # In real implementation, call Claude via LangChain
    # Attempt to extract a table name from the schema string
    m = re.search(r"from\s+(\w+)", req.question, re.IGNORECASE)
    table = m.group(1) if m else "my_table"
    sql = f"SELECT * FROM {table} LIMIT 1000"
    # But we must not use SELECT *; replace with a simple column selection placeholder
    sql = sql.replace("SELECT *", "SELECT 1 as placeholder_col")

    if not validate_sql(sql):
        raise QueryWriterError("Generated SQL failed validation")

    return QueryResponse(sql=sql, explanation="Generated placeholder SQL").dict()

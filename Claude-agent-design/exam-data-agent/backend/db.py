from sqlalchemy import create_engine, text
from config import DATABASE_URL, SQL_TIMEOUT_SECONDS, MAX_RESULT_ROWS

engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
    connect_args={"connect_timeout": 10},
)


def execute_query(sql: str, params: dict = None) -> dict:
    """执行SQL查询，返回 {"columns": [...], "rows": [...]}"""
    with engine.connect() as conn:
        conn.execute(text(f"SET SESSION max_execution_time={SQL_TIMEOUT_SECONDS * 1000}"))
        result = conn.execute(text(sql), params or {})
        columns = list(result.keys())
        rows = [list(row) for row in result.fetchmany(MAX_RESULT_ROWS)]
        rows = [[str(v) if v is not None else "" for v in row] for row in rows]
        return {"columns": columns, "rows": rows}

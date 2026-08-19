from __future__ import annotations

from pathlib import Path

import duckdb

from shop_risk.paths import SQL_DIR


def exec_script(con: duckdb.DuckDBPyConnection, sql: str) -> None:
    statements = [chunk.strip() for chunk in sql.split(";") if chunk.strip()]
    for stmt in statements:
        con.execute(stmt)


def run_features(con: duckdb.DuckDBPyConnection, sql_dir: Path | None = None) -> list[str]:
    """Materialize buyer/seller/creator/order features and market KPIs."""
    directory = sql_dir or SQL_DIR
    ran: list[str] = []
    for path in sorted(directory.glob("*.sql")):
        exec_script(con, path.read_text())
        ran.append(path.name)
    return ran

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from shop_risk.paths import DEFAULT_DB, ensure_data_dirs


def connect(db_path: Path | str | None = None) -> duckdb.DuckDBPyConnection:
    ensure_data_dirs()
    path = Path(db_path) if db_path else DEFAULT_DB
    path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path))


def load_frames(
    frames: dict[str, pd.DataFrame],
    db_path: Path | str | None = None,
) -> duckdb.DuckDBPyConnection:
    con = connect(db_path)
    for name, df in frames.items():
        con.register(f"_tmp_{name}", df)
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM _tmp_{name}")
        con.unregister(f"_tmp_{name}")
    return con


def persist_parquet(frames: dict[str, pd.DataFrame], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name, df in frames.items():
        df.to_parquet(dest / f"{name}.parquet", index=False)


def table_names(con: duckdb.DuckDBPyConnection) -> list[str]:
    rows = con.execute("SHOW TABLES").fetchall()
    return [r[0] for r in rows]

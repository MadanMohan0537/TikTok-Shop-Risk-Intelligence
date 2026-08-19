from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
SQL_DIR = ROOT / "sql"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
WAREHOUSE_DIR = DATA_DIR / "warehouse"
EXPORTS_DIR = DATA_DIR / "exports"
DEFAULT_DB = WAREHOUSE_DIR / "shop.duckdb"


def ensure_data_dirs() -> None:
    for path in (RAW_DIR, WAREHOUSE_DIR, EXPORTS_DIR):
        path.mkdir(parents=True, exist_ok=True)

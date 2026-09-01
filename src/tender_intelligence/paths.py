from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
PUBLISHED_DATA_DIR = DATA_DIR / "published"
DEFAULT_DB_PATH = PROCESSED_DATA_DIR / "tenders.db"
PUBLISHED_JSON_PATH = PUBLISHED_DATA_DIR / "tenders.json"
PUBLISHED_PARQUET_PATH = PUBLISHED_DATA_DIR / "tenders.parquet"
SCHEMA_PATH = PROJECT_ROOT / "sql" / "schema.sql"

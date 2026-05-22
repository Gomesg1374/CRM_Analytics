import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.parent
load_dotenv(BASE_DIR / ".env")

RAW_PATH    = BASE_DIR / "data" / "raw"
OUTROS_PATH = BASE_DIR / "data" / "outros"
SILVER_PATH = BASE_DIR / "data" / "silver"
GOLD_PATH   = BASE_DIR / "data" / "gold"

PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5432")
PG_DB   = os.getenv("PG_DB",   "crm_analytics")
PG_USER = os.getenv("PG_USER", "crm")
PG_PASS = os.getenv("PG_PASS", "crm123")
SCHEMA  = "gold"

SILVER_PATH.mkdir(parents=True, exist_ok=True)
GOLD_PATH.mkdir(parents=True, exist_ok=True)

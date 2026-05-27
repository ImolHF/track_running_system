import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production")
FERNET_KEY = os.getenv("FERNET_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///data/pclock.db")
SYNC_INTERVAL_HOURS = int(os.getenv("SYNC_INTERVAL_HOURS", "4"))
INITIAL_SYNC_DAYS = int(os.getenv("INITIAL_SYNC_DAYS", "90"))
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))

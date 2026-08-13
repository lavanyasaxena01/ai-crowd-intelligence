import sys
from pathlib import Path

# Add backend/ to Python's import path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

# Import the existing FastAPI application
from api.app import app  # noqa: E402,F401

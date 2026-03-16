from pathlib import Path
import os
import runpy
import sys

BASE_DIR = Path(__file__).resolve().parent
PROJECT_CODE_DIR = BASE_DIR / "Project Code"
TARGET = PROJECT_CODE_DIR / "app.py"

if not TARGET.exists():
    raise FileNotFoundError(f"Expected app at {TARGET}")

sys.path.insert(0, str(PROJECT_CODE_DIR))
os.chdir(PROJECT_CODE_DIR)
runpy.run_path(str(TARGET), run_name="__main__")

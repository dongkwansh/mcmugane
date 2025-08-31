import os
from pathlib import Path

CONFIG_DIR = Path(os.getenv("CONFIG_DIR", Path(__file__).resolve().parents[1] / "configs"))
ALGORITHM_DIR = Path(os.getenv("ALGORITHM_DIR", CONFIG_DIR / "algorithms"))
LOG_DIR = Path(os.getenv("LOG_DIR", Path(__file__).resolve().parents[1] / "logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

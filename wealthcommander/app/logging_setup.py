# app/logging_setup.py
import logging
import os
from logging.handlers import TimedRotatingFileHandler

def setup_logging(log_dir: str):
    os.makedirs(log_dir, exist_ok=True)
    
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # General log
    general_handler = TimedRotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        when="midnight",
        interval=1,
        backupCount=7,
        encoding="utf-8"
    )
    general_handler.setFormatter(log_format)

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,
        handlers=[
            logging.StreamHandler(),  # To console
            general_handler           # To file
        ]
    )
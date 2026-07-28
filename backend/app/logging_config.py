"""
Centralized logging configuration for OceanGuardian AI.

Provides structured logging with proper levels, formatting, and output.
"""
import logging
import sys
from app.config import settings

def setup_logging():
    """Configure application-wide logging."""
    log_level = logging.DEBUG if settings.environment == "development" else logging.INFO
    
    # Root logger configuration
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # Set specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("app").setLevel(log_level)
    
    return logging.getLogger("app")

# Initialize logger
logger = setup_logging()

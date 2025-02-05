import sys
from loguru import logger

def setup_logger():
    """Configure the logger settings."""
    logger.remove(0)
    logger.add(sys.stderr, level="DEBUG")
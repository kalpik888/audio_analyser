"""
Logger Utilities
"""
import logging
from datetime import datetime


def setup_logger(name: str) -> logging.Logger:
    """
    Setup a logger with timestamp and level formatting.
    
    Args:
        name: Logger name (usually module name)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


def log_stage(stage_name: str, message: str):
    """
    Log a message for a specific pipeline stage.
    
    Args:
        stage_name: Name of the stage (e.g., "Stage 1", "Database")
        message: Message to log
    """
    logger = logging.getLogger("pipeline")
    logger.info(f"[{stage_name}] {message}")

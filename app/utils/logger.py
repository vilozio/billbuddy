"""Logging configuration for BillBuddy"""
import logging
import sys
from pathlib import Path


def setup_logger(name: str, log_level: str = "INFO") -> logging.Logger:
    """
    Set up a logger with console and file handlers
    
    Args:
        name: Logger name (typically __name__ of the module)
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Remove existing handlers to avoid duplicates
    logger.handlers.clear()
    
    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    console_handler.setFormatter(detailed_formatter)
    logger.addHandler(console_handler)
    
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # File handler for persistent logging
    file_handler = logging.FileHandler(log_dir / "billbuddy.log")
    file_handler.setLevel(logging.DEBUG)  # Always log everything to file
    file_handler.setFormatter(detailed_formatter)
    logger.addHandler(file_handler)
    
    return logger


# Default application logger
app_logger = setup_logger("billbuddy")


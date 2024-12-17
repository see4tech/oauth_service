import logging
import sys
from typing import Optional
import os
from pathlib import Path

def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get or create logger with consistent configuration.
    
    Args:
        name: Logger name (usually __name__ of calling module)
        
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name or __name__)
    
    # Only configure if no handlers are set
    if not logger.handlers:
        # Create logs directory if it doesn't exist
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Get configuration from environment
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        log_format = os.getenv(
            'LOG_FORMAT',
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        log_file = os.getenv('LOG_FILE', 'oauth_service.log')
        
        # Create formatters and handlers
        formatter = logging.Formatter(log_format)
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
        
        # File handler
        file_handler = logging.FileHandler(log_dir / log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
        
        # Set level
        logger.setLevel(getattr(logging, log_level.upper()))
    
    return logger

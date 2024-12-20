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
        try:
            # Create logs directory if it doesn't exist
            log_dir = Path('logs')
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Get configuration from environment
            log_level = os.getenv('LOG_LEVEL', 'DEBUG')  # Set default to DEBUG
            log_format = os.getenv(
                'LOG_FORMAT',
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            log_file = os.getenv('LOG_FILE', 'oauth_service.log')
            log_path = log_dir / log_file
            
            # Create formatters and handlers
            formatter = logging.Formatter(log_format)
            
            # Console handler with DEBUG level
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            console_handler.setLevel(logging.DEBUG)
            logger.addHandler(console_handler)
            
            # File handler with DEBUG level
            file_handler = logging.FileHandler(log_path)
            file_handler.setFormatter(formatter)
            file_handler.setLevel(logging.DEBUG)
            logger.addHandler(file_handler)
            
            # Set root logger level to DEBUG
            logger.setLevel(logging.DEBUG)
            
            # Log initial configuration
            logger.debug(f"Logger initialized for {name}")
            logger.debug(f"Log file path: {log_path.absolute()}")
            logger.debug(f"Log level: {log_level}")
            
        except Exception as e:
            # Fallback to basic console logging if file logging fails
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter(log_format))
            logger.addHandler(console_handler)
            logger.setLevel(logging.DEBUG)
            logger.error(f"Error configuring file logger: {str(e)}")
    
    return logger

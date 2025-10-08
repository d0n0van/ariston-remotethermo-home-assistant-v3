"""Logging configuration for Ariston integration."""

from __future__ import annotations

import logging
import sys
from typing import Any, Dict

from homeassistant.core import HomeAssistant

# Logging levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Default logging configuration
DEFAULT_LOG_CONFIG = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "detailed": {
            "format": "%(asctime)s [%(levelname)s] %(name)s:%(lineno)d: %(funcName)s(): %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": "INFO",
            "formatter": "standard",
            "stream": sys.stdout,
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "level": "DEBUG",
            "formatter": "detailed",
            "filename": "/config/logs/ariston.log",
            "maxBytes": 10485760,  # 10MB
            "backupCount": 5,
        },
    },
    "loggers": {
        "ariston": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "ariston.coordinator": {
            "level": "DEBUG",
            "handlers": ["console", "file"],
            "propagate": False,
        },
        "ariston.entity": {
            "level": "INFO",
            "handlers": ["console", "file"],
            "propagate": False,
        },
    },
    "root": {
        "level": "WARNING",
        "handlers": ["console"],
    },
}


class AristonLogger:
    """Enhanced logger for Ariston integration with structured logging."""

    def __init__(self, name: str) -> None:
        """Initialize the logger."""
        self.logger = logging.getLogger(f"ariston.{name}")
        self._context: Dict[str, Any] = {}

    def set_context(self, **kwargs: Any) -> None:
        """Set logging context for structured logging."""
        self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear logging context."""
        self._context.clear()

    def _format_message(self, message: str) -> str:
        """Format message with context."""
        if not self._context:
            return message
        
        context_str = " | ".join(f"{k}={v}" for k, v in self._context.items())
        return f"[{context_str}] {message}"

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        self.logger.debug(self._format_message(message), **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        self.logger.info(self._format_message(message), **kwargs)

    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message."""
        self.logger.warning(self._format_message(message), **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        self.logger.error(self._format_message(message), **kwargs)

    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message."""
        self.logger.critical(self._format_message(message), **kwargs)

    def exception(self, message: str, **kwargs: Any) -> None:
        """Log exception with traceback."""
        self.logger.exception(self._format_message(message), **kwargs)


def setup_logging(hass: HomeAssistant, log_level: str = "INFO") -> None:
    """Set up logging for the Ariston integration."""
    import logging.config
    
    # Update log level if specified
    if log_level.upper() in LOG_LEVELS:
        config = DEFAULT_LOG_CONFIG.copy()
        config["handlers"]["console"]["level"] = log_level.upper()
        config["loggers"]["ariston"]["level"] = log_level.upper()
        
        logging.config.dictConfig(config)
        
        logger = logging.getLogger("ariston")
        logger.info("Ariston logging configured with level: %s", log_level.upper())
    else:
        logger = logging.getLogger("ariston")
        logger.warning("Invalid log level specified: %s, using default", log_level)


def get_logger(name: str) -> AristonLogger:
    """Get a logger instance for the given name."""
    return AristonLogger(name)


# Convenience function for backward compatibility
def get_ariston_logger(name: str) -> logging.Logger:
    """Get a standard logger for backward compatibility."""
    return logging.getLogger(f"ariston.{name}")




"""
LOGGER - Utility module để khởi tạo và quản lý logging system
"""

import logging
import logging.config
import sys
from pathlib import Path

import config


def setup_logging():
    """Khởi tạo logging system từ cấu hình trong config.py"""
    try:
        logging.config.dictConfig(config.LOGGING_CONFIG)
        logging.info("Logging system initialized successfully")
        return True
    except Exception as e:
        # Fallback to basic config nếu dictConfig thất bại
        logging.basicConfig(
            level=config.LOG_LEVEL,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            stream=sys.stdout
        )
        logging.warning(f"Failed to use dictConfig, using basic config: {e}")
        return False


def get_logger(name):
    """Lấy logger instance cho module cụ thể"""
    return logging.getLogger(name)


# Auto-setup logging khi import
if not logging.getLogger().handlers:
    setup_logging()

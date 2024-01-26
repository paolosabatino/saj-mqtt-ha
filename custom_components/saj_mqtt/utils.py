"""Helper functions for the SAJ MQTT integration."""
from .const import LOGGER


def log_hex(value: int) -> str:
    """Log a value in hexadecimal and numeric format."""
    return f"{hex(value)} ({value})"


def debug(msg: str, enabled=True) -> None:
    """Debug log helper to decide if it shoud be logged or not."""
    if enabled:
        LOGGER.debug(msg)

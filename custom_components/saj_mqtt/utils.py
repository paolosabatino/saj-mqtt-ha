"""Helper functions for the SAJ MQTT integration."""


def log_hex(value: int) -> str:
    """Log a value in hexadecimal and numeric format."""
    return f"{hex(value)} ({value})"

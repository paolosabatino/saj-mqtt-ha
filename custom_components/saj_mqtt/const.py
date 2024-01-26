"""Constants for the SAJ MQTT integration."""
from __future__ import annotations

from datetime import timedelta
from enum import Enum
import logging

DOMAIN = "saj_mqtt"
BRAND = "SAJ"
MANUFACTURER = "SAJ Electric"
MODEL = "H1 series"

# Configuration constants
CONF_SERIAL_NUMBER = "serial_number"
CONF_SCAN_INTERVAL = "scan_interval"  # for realtime data
CONF_SCAN_INTERVAL_INVERTER_INFO = "scan_interval_inverter_info"
CONF_SCAN_INTERVAL_BATTERY_INFO = "scan_interval_battery_info"
CONF_SCAN_INTERVAL_BATTERY_CONTROLLER = "scan_interval_battery_controller"
CONF_SCAN_INTERVAL_CONFIG = "scan_interval_config"
CONF_DEBUG_MQTT = "debug_mqtt"

# Data constants
DATA_CONFIG = "config"
DATA_SAJMQTT = "sajmqtt"
DATA_COORDINATOR = "coordinator"
DATA_COORDINATOR_INVERTER_INFO = "coordinator_inverter_info"
DATA_COORDINATOR_BATTERY_INFO = "coordinator_battery_info"
DATA_COORDINATOR_BATTERY_CONTROLLER = "coordinator_battery_controller"
DATA_COORDINATOR_CONFIG = "coordinator_config"

# Service constants
SERVICE_SET_APP_MODE = "set_app_mode"
SERVICE_READ_REGISTER = "read_register"
SERVICE_WRITE_REGISTER = "write_register"
SERVICE_REFRESH_CONFIG_DATA = "refresh_config_data"
SERVICE_REFRESH_BATTERY_CONTROLLER_DATA = "refresh_battery_controller_data"
ATTR_APP_MODE = "app_mode"
ATTR_REGISTER = "register"
ATTR_REGISTER_FORMAT = "register_format"
ATTR_REGISTER_SIZE = "register_size"
ATTR_REGISTER_VALUE = "register_value"

# Modbus constants
MODBUS_MAX_REGISTERS_PER_QUERY = (
    0x64  # Absolute max is 123 (0x7b) registers per MQTT packet request (do not exceed)
)
MODBUS_DEVICE_ADDRESS = 0x01
MODBUS_READ_REQUEST = 0x03
MODBUS_WRITE_REQUEST = 0x06

# Modbus registers
MODBUS_REG_APP_MODE = 0x3247

# Saj mqtt constants
SAJ_MQTT_QOS = 2
SAJ_MQTT_RETAIN = False
SAJ_MQTT_ENCODING = None
SAJ_MQTT_DATA_TRANSMISSION = "data_transmission"
SAJ_MQTT_DATA_TRANSMISSION_RSP = "data_transmission_rsp"
SAJ_MQTT_DATA_TRANSMISSION_TIMEOUT = 10

# Default constants
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

# Other constants
STARTUP = "startup"

LOGGER = logging.getLogger(__package__)


class WorkingMode(Enum):
    """Working mode."""

    WAIT = 1
    NORMAL = 2
    FAULT = 3
    UPDATE = 4


class AppMode(Enum):
    """App mode."""

    SELF_USE = 0
    TIME_OF_USE = 1
    BACKUP = 2
    PASSIVE = 3

"""Constants for the SAJ MQTT integration."""
from datetime import timedelta
import logging

DOMAIN = "saj_mqtt"

# Configuration constants
CONF_SERIAL_NUMBER = "serial_number"
CONF_SCAN_INTERVAL = "scan_interval"

# Data constants
DATA_SAJMQTT = "sajmqtt"
DATA_COORDINATOR = "coordinator"

# Modbus constants
MODBUS_MAX_REGISTERS_PER_QUERY = 0x64 # Absolute max is 123 (0x7b) registers per MQTT packet request (do not exceed)
MODBUS_DEVICE_ADDRESS = 0x01
MODBUS_READ_REQUEST = 0x03
MODBUS_WRITE_REQUEST = 0x06

# Saj mqtt constants
SAJ_MQTT_QOS = 2
SAJ_MQTT_DATA_TRANSMISSION = "data_transmission"
SAJ_MQTT_DATA_TRANSMISSION_RESP = "data_transmission_rsp"
SAJ_MQTT_DATA_TRANSMISSION_TIMEOUT = 10

# Default constants
DEFAULT_SCAN_INTERVAL = timedelta(seconds=60)

LOGGER = logging.getLogger(__package__)

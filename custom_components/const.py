"""Constants for the SAJ MQTT integration."""
import logging

DOMAIN = "saj_mqtt"

CONF_SERIAL_NUMBER = "serial_number"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SCAN_INTERVAL_DEFAULT_IN_SECONDS = 60

DATA_SAJMQTT = "sajmqtt"
DATA_COORDINATOR = "coordinator"

SAJ_MQTT_DATA_TRANSMISSION = "data_transmission"
SAJ_MQTT_DATA_TRANSMISSION_RESP = "data_transmission_rsp"
SAJ_MQTT_DATA_TRANSMISSION_TIMEOUT = 10
# We can query up to 123 registers per MQTT packet request.
# This is a pseudo-constant controls the maximum number of registers to query at once.
# The logic will split the request in multiple mqtt packets automatically
SAJ_MQTT_MAX_REGISTERS_PER_QUERY = 64
SAJ_MQTT_QOS = 2

LOGGER = logging.getLogger(__package__)

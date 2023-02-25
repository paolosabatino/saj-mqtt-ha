#!/usr/bin/python3
# information gathering for saj inverters through data_transmission mqtt topic
# usage example: ./inf_data_gather.py H1S2602J2119E01121 2>/dev/null | python3 saj.py

from collections import OrderedDict
from struct import pack, unpack_from
from datetime import datetime
from time import time
from pymodbus.utilities import computeCRC
from sys import argv, stderr, stdout
import random
import paho.mqtt.client as paho

# Cannot exceed 123 registers (0x7b)
MAX_REGISTERS_PER_REQUEST = 0x64

def eprint(*args, **kwargs):
    print(*args, file=stderr, **kwargs)


class SajMqttModbusRead(object):

    DEFAULT_ADDRESS = 0x01  # The default "slave address" to use

    MODBUS_READ_REQUEST = 0x03  # The 0x03 modbus request is "read multiple register"

    def __init__(self, start=0x00, end=0x00, address=DEFAULT_ADDRESS):
        self.start = start
        self.end = end
        self.address = address

        self.responses = OrderedDict()

    @staticmethod
    def _forge_packet(register_start: int, register_count: int, address: int):
        """
            Given the start and count registers, forge the MQTT packet for the
            request to handle that single request
        """

        # Build the modbus content part of the MQTT packet
        content = pack(">BBHH",  address, SajMqttModbusRead.MODBUS_READ_REQUEST, register_start, register_count)
        crc16 = computeCRC(content)

        # Assemble the modbus content into the MQTT packet framework
        req_id = int(random.random() * 65536)
        rnd = int(random.random() * 65536)

        packet = pack(">HBBH", req_id, 0x58, 0xc9, rnd) + content + pack(">H", crc16)

        eprint("Request ID: %04x - CRC16: %04x - Random: %04x" % (req_id, crc16, rnd))
        eprint("Length: %d bytes" % (len(packet),))

        packet = pack(">H", len(packet)) + packet

        return packet, req_id

    @staticmethod
    def _parse_packet(packet: bytes):
        length, req_id, timestamp, request = unpack_from(">HHIH", packet, 0x00)

        date = datetime.fromtimestamp(timestamp)
        size, = unpack_from(">B", packet, 0xa)
        content = packet[0xb:0xb + size]
        crc16, = unpack_from(">H", packet, 0xb + size)

        # CRC is calculated starting from "request" at offset 0x3a
        calc_crc = computeCRC(packet[0x8:0xb + size])

        eprint("Packet length: %d bytes - Request ID: %4x - Request type: %4x" % (length, req_id, request))
        eprint("Timestamp: %s" % (date,))

        eprint()
        eprint("Register size: %d" % (size,))
        eprint("Register content: %s" % (":".join("%02x" % (byte,) for byte in content),))
        eprint()
        eprint("CRC16: %x: %s" % (crc16, "ok" if crc16 == calc_crc else "bad"))

        return req_id, size, content

    def query(self, client: paho.Client, topic: str):
        """
            Forge the packets and send them via MQTT connection.
        """
        start = self.start
        end = self.end
        responses = self.responses

        while start < end:

            length = min(end - start, MAX_REGISTERS_PER_REQUEST)
            packet, req_id = self._forge_packet(start, length, self.address)

            responses[req_id] = None
            client.publish(topic=topic, payload=packet, qos=2, retain=False)

            start += length

    def parse_message(self, payload: bytes):
        """
            Call this method and pass the payload bytes each time a
            response packet arrives
        """
        req_id, size, content = self._parse_packet(payload)

        if req_id not in self.responses:
            return

        self.responses[req_id] = content

    def get_response(self) -> bytes|None:
        if not self.is_done():
            return None

        data = bytearray()
        for req_id, response in self.responses.items():
            data += response

        return data

    def is_done(self):
        """
            Returns true if all the payload message have been received for the
            given MQTT registers request
        """
        return all((response for req_id, response in self.responses.items()))


class SajMqttModbusWrite(object):

    DEFAULT_ADDRESS = 0x01  # The default "slave address" to use

    MODBUS_WRITE_REQUEST = 0x06  # The 0x07 modbus request is "write single register"

    def __init__(self, register: int, value: int, address=DEFAULT_ADDRESS):
        self.register = register
        self.value = value
        self.address = address

        self.request_id = None
        self.response = None

    @staticmethod
    def _forge_packet(register: int, value: int, address: int):
        """
            Given the register and the value to write into, forge tha MQTT packet
            to do so.
        """

        # Build the modbus content part of the MQTT packet
        content = pack(">BBHH", address, SajMqttModbusWrite.MODBUS_WRITE_REQUEST, register, value)
        crc16 = computeCRC(content)

        # Assemble the modbus content into the MQTT packet framework
        req_id = int(random.random() * 65536)
        rnd = int(random.random() * 65536)

        packet = pack(">HBBH", req_id, 0x58, 0xc9, rnd) + content + pack(">H", crc16)

        eprint("Request ID: %04x - CRC16: %04x - Random: %04x" % (req_id, crc16, rnd))
        eprint("Length: %d bytes" % (len(packet),))

        eprint("Request: %s" % (":".join("%02x" % (byte,) for byte in packet),))

        packet = pack(">H", len(packet)) + packet

        return packet, req_id

    @staticmethod
    def _parse_packet(packet: bytes):
        length, req_id, timestamp, request = unpack_from(">HHIH", packet, 0x00)

        eprint("Packet length: %d bytes - Request ID: %4x - Request type: %4x" % (length, req_id, request))

        date = datetime.fromtimestamp(timestamp)
        eprint("Timestamp: %s" % (date,))

        # Although the documentation says that, exactly as modbus protocol mandates, the answer
        # is the very same as request, here we get back the written value and the origin CRC,
        # plus they are byte-swapped (little endian).
        #register, value, crc16 = unpack_from(">HHH", packet, 0xa)

        value, prev_crc16 = unpack_from("<HH", packet, 0xa)
        crc16, = unpack_from(">H", packet, 0xe)

        # CRC is calculated starting from "request" at offset 0x3a
        calc_crc = computeCRC(packet[0x8:0xe])

        eprint()
        eprint("CRC16: %x: %s" % (crc16, "ok" if crc16 == calc_crc else "bad"))

        return req_id, value

    def write(self, client: paho.Client, topic: str):
        """
            Forge the packets and send them via MQTT connection.
        """

        packet, req_id = self._forge_packet(self.register, self.value, self.address)

        self.response = None
        self.request_id = req_id

        client.publish(topic=topic, payload=packet, qos=2, retain=False)

    def parse_message(self, payload: bytes):
        """
            Call this method and pass the payload bytes each time a
            response packet arrives
        """
        req_id, value = self._parse_packet(payload)

        if req_id != self.request_id:
            return

        self.response = value

    def get_response(self) -> bytes|None:
        if not self.is_done():
            return None

        return self.response

    def is_done(self):
        """
            Returns true if all the payload message have been received for the
            given MQTT registers request
        """
        return self.response is not None


def on_message(client, userdata, message, tmp=None):

    eprint("received message - topic: %s - qos: %d - " % (message.topic, message.qos))
    eprint("message: %s" % (":".join("%02x" % (byte,) for byte in message.payload),))


    request = userdata
    request.parse_message(message.payload)

    if request.is_done():
        client.disconnect()

def on_connect(client, userdata, flags, rc):
    eprint("connected")

    request = userdata
    request.write(client, topic_data_transmission)

def on_disconnect(client, userdata, rc):
    eprint("disconnected")

def on_publish(client, userdata, mid):
    eprint("published")

def on_subscribe(client, userdata, mid, granted_qos):
    eprint("subscribed")

def normalize_hex(argument: str) -> int:

    base = 10
    start = 0

    if argument[:2] == "0x":
        base = 16
        start = 2

    return int(argument[start:], base)


if len(argv) < 5:
    eprint("Usage: %s <broker_ip> <serial> <register> <value>" % (argv[0],))
    exit()

broker_ip = argv[1]
serial = argv[2]
register = normalize_hex(argv[3])
value = normalize_hex(argv[4])

request = SajMqttModbusWrite(register, value)

client = paho.Client(client_id="write_register", userdata=request)
client.username_pw_set("paolo","empty_pass")

client.on_message = on_message
client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_publish = on_publish
client.on_subscribe = on_subscribe

client.connect(broker_ip, port=1883, keepalive=60)

topic_data_transmission = "saj/%s/data_transmission" % (serial,)
topic_data_transmission_rsp = "saj/%s/data_transmission_rsp" % (serial,)

client.subscribe(topic=topic_data_transmission_rsp, qos=2)

client.loop_forever()

response = request.get_response()

if response is not None:
    print("wrote to register 0x%x: 0x%x" % (register, response))

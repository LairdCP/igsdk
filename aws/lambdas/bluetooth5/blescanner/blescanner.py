# -------------------------------------------------------------------------------
# Name:        BleScanner.py
# Purpose:     Report the devices found by the BL654
# -------------------------------------------------------------------------------
import greengrasssdk
import logging
import os
import json
from json import JSONDecodeError
import serial
import threading
import string
import re

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'
char_topic = 'ble_scanner/{}/info'.format(node_id)
device_list = []

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
client = greengrasssdk.client('iot-data')
logging.info('Starting Ble Scanner lambda.')

# Open serial port read for the scanned devices
ser = serial.Serial(
    port='/dev/ttyS2',
    baudrate=115200,
    parity=serial.PARITY_NONE,
    stopbits=serial.STOPBITS_ONE,
    bytesize=serial.EIGHTBITS
)


class ZephyrStatus:
    def __init__(self, btpa_uart, gg_client, tx_topic):
        self.btpa_uart = btpa_uart
        self.gg_client = gg_client
        self.current_drops = 0
        self.errors = 0
        self.tx_topic = tx_topic
        self.dev_list = []

    def get_port(self):
        return self.btpa_uart

    def add_drops(self, drop):
        self.current_drops = self.current_drops + drop

    def get_drops(self):
        return self.current_drops

    def add_errors(self, err_cnt):
        self.errors = self.errors + err_cnt

    def get_client(self):
        return self.gg_client

    def get_topic(self):
        return self.tx_topic

    def add_dev(self, device):
        self.dev_list.append(device)

    def clear_list(self):
        self.dev_list = []

    # Check if the device is already in our list
    def device_found(self, data):
        for device in self.dev_list:
            if device['mac'] == data['mac']:
                return True
        return False

    def add_device(self, data):
        self.dev_list.append(data)


def function_handler(event, context):
    """
    Process any optional user input to the reset topic
    """
    logging.info('EVENT: ' + str(event))

    # Determine the topic
    if context.client_context.custom and context.client_context.custom['subject']:
        topic_el = context.client_context.custom['subject'].split('/')
        if len(topic_el) == 3 and topic_el[0] == 'ble_scanner' and topic_el[1] == node_id and topic_el[2] == 'resetList':
            logging.info('Resetting accumulated device list')
            zephyr.clear_list()


def serial_reader(zephyr_port):
    """
    Builds a line from bytes received via the USB port.
    Attempts to clean up any control characters from resulting string.
    """
    data_str = zephyr_port.readline().decode('ascii', errors='ignore')
    # clean it up if necessary by removing any unprintable characters
    filtered_string = ''.join(filter(lambda x: x in string.printable, data_str))
    return filtered_string

def poll_zephyr(zephyr_stuff):
    """
    Queries the UART to see if any data has been received from the Zephyr program
    Running in its own thread, so as not to block function_handler from executing
    """
    zeph_port = zephyr_stuff.get_port()
    tx_topic = zephyr_stuff.get_topic()
    gg_client = zephyr_stuff.get_client()
    pattern = re.compile("--- (\d+) messages dropped")

    while True:
        data = serial_reader(zeph_port)
        # Handle a null read
        if data == "":
            logging.debug('Skipping null data')
            continue

        # handle the situation where the Zephyr program indicates messages were dropped:
        # example: "--- 2 messages dropped ---"
        result = pattern.search(data)
        if result:
            current_drops = int(result.group(1))
            logging.warning(f'Zephyr program dropped: {current_drops} messages')
            zephyr_stuff.add_drops(current_drops)
            accum_drops = zephyr_stuff.get_drops()
            logging.info(f"Zephyr has dropped {accum_drops} messages so far")
        else:
            try:
                data = json.loads(data)
                if not zephyr_stuff.device_found(data):
                    zephyr_stuff.add_device(data)
                    data_json = json.dumps(data, separators=(',', ':'), indent=4)
                    logging.info(f"Found new device: {data}")
                    gg_client.publish(topic=tx_topic, payload=data_json)
                else:
                    logging.debug("Device was already in list - Not publishing")

            except JSONDecodeError:
                logging.warning(f"Garbled JSON from read - length: {len(data)}")


# init our Zephyr object for communicating with the thread
zephyr = ZephyrStatus(ser, client, char_topic)

# Start the Zephyr polling thread
zephyr_thread = threading.Thread(target=poll_zephyr, args=(zephyr,))
zephyr_thread.start()


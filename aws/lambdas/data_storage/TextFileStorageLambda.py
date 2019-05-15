# TextStorageLambda.py
# Stores Modbus data into a managed CSV text file
#
# All Modbus messages received on a topic matching modbus/msg/# will
# be written to a managed text file (the files will be written to the
# SD card storage location when available, otherwise they will be written
# to internal storage and moved when the SD card becomes available.)
#
# If any message is received on the topic 'storage/status/NODE_ID/request', the
# current storage status will be published on storage/status/NODE_ID/response'.
#
# Messages shall be received in JSON format with the following key/value elements expected:
#	received: unsigned integer that represents the time the message was received, as the number of milliseconds since the Unix epoch (January 1, 1970 00:00:00) relative to the UTC timezone
#	address: unsigned integer that represents the 8-bit slave address contained in the query on the bus
#	function: unsigned integer that represents the 8-bit function contained in the query sent on the bus
#	data (optional): an array of unsigned integers that represent the data payload received on the bus

import greengrasssdk
import logging
import os
import json
from igsdk.storage.managed_file import managed_file_init, managed_file_write, get_storage_status

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'

# Configuration Parameters (default if not passed in environment)
unit_name = os.getenv('UNIT_NAME') or 'modbus'
base_name = os.getenv('BASE_NAME') or 'modbus'
file_ext = os.getenv('FILE_EXT') or '.csv'
max_file_size = int(os.getenv('MAX_FILE_SIZE') or '268435456') # 256 MB
log_level = int(os.getenv('MODBUS_LOG_LEVEL') or '20') # 20 = 'logging.INFO'

# Managed file handle
hfile = None

#
# This handler receives all incoming messages (based on the topic subscription
# that was specified in the deployment).  Any message that is received
# on a topic beginning with 'modbus/msg' will be written to the file.
#
def function_handler(event, context):
    global hfile
    # Determine the topic
    if context.client_context.custom and context.client_context.custom['subject']:
        topics = context.client_context.custom['subject'].split('/')
        if len(topics) >= 2 and topics[0] == 'modbus' and topics[1] == 'msg':
            if 'received' in event and 'address' in event and 'function' in event:
                record = str(event['received']) + ',' + str(event['address']) + ',' + str(event['function'])
                if 'data' in event:
                    # Convert the array of integers into a string of comma-separated values
                    record += ',' + str(event['data']).strip('[]').replace(' ', '')
                managed_file_write(hfile, record + '\n')
            else:
                logging.error("Text storage requires valid parameters: received, address, and function")
        elif len(topics) == 4 and (topics[0] == 'storage' and
            topics[1] == 'status' and topics[2] == node_id and
            topics[3] == 'request'):
                client.publish(topic = 'storage/status/{}/response'.format(node_id),
                    payload = json.dumps(hfile.get_storage_status()))
    else:
        logging.error('Cannot determine message topic.')

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(log_level)

# Create a Greengrass Core SDK client.
client = greengrasssdk.client('iot-data')

# Initialize the managed file
logging.info('Starting text file storage: unit={}, basename={}, ext={}, maxsize={}'.format(
    unit_name, base_name, file_ext, max_file_size))
hfile = managed_file_init(unit_name, base_name, file_ext, max_file_size)

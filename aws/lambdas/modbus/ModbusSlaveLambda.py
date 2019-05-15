#-------------------------------------------------------------------------------
# Name:        ModbusSlaveLambda.py
# Purpose:     Responds to requests from master based on device shadow
#-------------------------------------------------------------------------------
import greengrasssdk
import logging
import os
import signal
import sys
import copy
import json
import threading
from igsdk.modbus.message import ModbusMessage
from igsdk.modbus.modbus_slave import modbus_slave_start, modbus_slave_stop

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'

# Configuration Parameters (default if not passed in environment)
port = os.getenv('SERIAL_PORT_DEVICE') or '/dev/ttyS2'
baudrate = int(os.getenv('SERIAL_BAUD_RATE') or '9600')
modbus_mode = int(os.getenv('MODBUS_MODE') or '0') # 0 = ASCII, 1 = RTU
serial_mode = int(os.getenv('SERIAL_MODE') or '0') # 0 = RS-232, 1 = RS-485/422 HD, 2 = RS-485/422 FD
serial_term = int(os.getenv('SERIAL_TERM') or '0')
slave_addr = int(os.getenv('MODBUS_SLAVE_ADDR') or '1')
log_level = int(os.getenv('MODBUS_LOG_LEVEL') or '20') # 20 = 'logging.INFO'

# Keep a local copy of the current device shadow
device_shadow = None

# Use a lock to maintain a consistent view of the shaddow
shadow_lock = threading.Lock()

#
# This handler receives all incoming messages (based on the topic subscription
# that was specified in the deployment).  The Modbus slave functionality
# requires subscriptions to the following topics:
#
#   $aws/things/<node_id>/shadow/get/accepted
#   $aws/things/<node_id>/shadow/documents
#
def function_handler(event, context):
    global device_shadow
    # Determine the topic
    if context.client_context.custom and context.client_context.custom['subject']:
        topic_el = context.client_context.custom['subject'].split('/')
        # Make sure this event corresponds to our ID and is a shadow operation
        if len(topic_el) >= 4 and topic_el[2] == node_id and topic_el[3] == 'shadow':
            if len(topic_el) == 6 and topic_el[4] == 'get' and topic_el[5] == 'accepted':
                # This is a 'get' response on '$aws/<node_id>/shadow/get/accepted'
                shadow_lock.acquire()
                device_shadow = copy.deepcopy(event['state'])
                shadow_lock.release()
                logging.info('Received shadow get response: {}'.format(device_shadow))
            elif len(topic_el) == 6 and topic_el[4] == 'update' and topic_el[5] == 'documents':
                # This is a shadow update on '$aws/<node_id>/shadow/update/documents'
                shadow_lock.acquire()
                device_shadow = copy.deepcopy(event['current']['state'])
                shadow_lock.release()
                logging.info('Received shadow update: {}'.format(device_shadow))
    return

#
# This callback is used by the modbus_slave function to obtain the current
# 'readable' elements; i.e., the 'desired' element of the device shadow.
#
def get_read_cb():
    ret = None
    shadow_lock.acquire()
    if device_shadow:
        ret = device_shadow.get('desired', None)
    shadow_lock.release()
    return ret
        
#
# This callback is used by the modbus_slave function to obtain the current
# 'writeable' elements; i.e., the 'reported' element of the device shadow
#
def get_write_cb():
    ret = None
    shadow_lock.acquire()
    if device_shadow:
        ret = device_shadow.get('reported', None)
    shadow_lock.release()
    return ret

#
# This callback is used by the modbus_slave function to update the current
# 'writeable' elements with a delta; construct the full device shadow
# update and publish it to the correct topic.
#
def set_write_cb(delta):
    shadow_update = { 'state' : { 'reported' : delta } }
    update_topic = '$aws/things/{}/shadow/update'.format(node_id)
    # Send message as JSON
    logging.debug('Publishing slave shadow update on {}: {}'.format(update_topic, shadow_update))
    client.publish(topic = update_topic, payload = json.dumps(shadow_update))
    
# Termination handler
def on_sigterm(signal, frame):
    global slave
    logging.warn('SIGTERM received, calling modbus_slave_stop.')
    modbus_slave_stop(slave)
    # Need to exit since this overrides the framework handler
    sys.exit(0)

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(log_level)

# Create a greengrass core sdk client
client = greengrasssdk.client('iot-data')

# Send request for shadow document (will be received by handler)
logging.info('Requesting device shadow.')
client.publish(topic='$aws/things/{}/shadow/get'.format(node_id), payload='{}')

# Start the modbus slave function
logging.info('Running modbus_slave function.')
slave = modbus_slave_start(port, baudrate, modbus_mode, serial_mode, serial_term, slave_addr, get_read_cb, get_write_cb, set_write_cb)

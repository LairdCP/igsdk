#-------------------------------------------------------------------------------
# Name:        ModbusMasterLambda.py
# Purpose:     Receives JSON messages from the IoT hub, sends a corresponding
#              Modbus message, and awaits a response.
#-------------------------------------------------------------------------------
import greengrasssdk
import logging
import os
import signal
import sys
from igsdk.modbus.message import ModbusMessage
from igsdk.modbus.modbus_master import modbus_master_start, modbus_master_stop, modbus_master_send_await

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'

# Configuration Parameters (default if not passed in environment)
port = os.getenv('SERIAL_PORT_DEVICE') or '/dev/ttyS2'
baudrate = int(os.getenv('SERIAL_BAUD_RATE') or '9600')
modbus_mode = int(os.getenv('MODBUS_MODE') or '0') # 0 = ASCII, 1 = RTU
serial_mode = int(os.getenv('SERIAL_MODE') or '0') # 0 = RS-232, 1 = RS-485/422 HD, 2 = RS-485/422 FD
serial_term = int(os.getenv('SERIAL_TERM') or '0')
modbus_response_timeout = int(os.getenv('MODBUS_RESPONSE_TIMEOUT') or '5')
log_level = int(os.getenv('MODBUS_LOG_LEVEL') or '20') # 20 = 'logging.INFO'

#
# This handler receives incoming messages (based on the topic subscription
# that was specified in the deployment).  In this function, we don't verify the
# topic and assume all messages received should be interpreted as messages
# to be sent as a Modbus master.
#
def function_handler(event, context):
    # Use timeout if specified in message, else default
    msg_timeout = event.get('timeout', modbus_response_timeout)
    # Decode event object as a ModbusMessage
    msg = ModbusMessage.from_obj(event) # Will throw an exception if event is not valid
    logging.debug('Sending request: address={}, function={}, data={}'.format(msg.address, msg.function, msg.data))
    resp = modbus_master_send_await(master, msg, msg_timeout)
    if resp:
        # Construct topic
        resp_topic = 'modbus/msg/master/{}/response/{}/{}'.format(node_id, resp.address, resp.function)
        # Send message as JSON
        logging.debug('Publishing slave response on {}, address={}, function={}, data={}'.format(resp_topic, resp.address, resp.function, resp.data))
        client.publish(topic = resp_topic, payload = resp.to_JSON())
    else:
        logging.warn('Failed to receive response to master message.')
    return

# Termination handler
def on_sigterm(signal, frame):
    global master
    logging.warn('SIGTERM received, calling modbus_master_stop.')
    modbus_master_stop(master)
    # Need to exit since this overrides the framework handler
    sys.exit(0)

#
# The following code runs when this is deployed as a 'long-running' Lambda function
#

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(log_level)

# Create a greengrass core sdk client
client = greengrasssdk.client('iot-data')

# Register termination handler
signal.signal(signal.SIGTERM, on_sigterm)

# Start the modbus trace function with our callback
logging.info('Initializing modbus_master function.')
master = modbus_master_start(port, baudrate, modbus_mode, serial_mode, serial_term)

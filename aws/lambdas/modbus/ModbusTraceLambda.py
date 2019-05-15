#-------------------------------------------------------------------------------
# Name:        ModbusTraceLambda.py
# Purpose:     Captures Modbus traffic on the serial interface and publishes the
#              Modbus packet to the AWS Cloud in a JSON format message
#-------------------------------------------------------------------------------
import greengrasssdk
import logging
import os
import signal
import sys
from igsdk.modbus.message import ModbusMessage
from igsdk.modbus.modbus_trace import modbus_trace_start, modbus_trace_stop

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'

# Configuration Parameters (default if not passed in environment)
port = os.getenv('SERIAL_PORT_DEVICE') or '/dev/ttyS2'
baudrate = int(os.getenv('SERIAL_BAUD_RATE') or '9600')
modbus_mode = int(os.getenv('MODBUS_MODE') or '0') # 0 = ASCII, 1 = RTU
serial_mode = int(os.getenv('SERIAL_MODE') or '0') # 0 = RS-232, 1 = RS-485/422 HD, 2 = RS-485/422 FD
serial_term = int(os.getenv('SERIAL_TERM') or '0')
log_level = int(os.getenv('MODBUS_LOG_LEVEL') or '20') # 20 = 'logging.INFO'

def trace_callback(msg):
    """Callback for received messages

    This function is called by the modbus_trace() function for each Modbus
    message that is received.

    This implementation simply formwards the JSON representation of the message
    to a specified topic via the Greengrass messaging server, but it can be
    customized further (for example, to filter messages based on slave ID, etc).
    """
    # Construct topic
    msg_topic = 'modbus/msg/trace/{}/{}/{}'.format(node_id, msg.address, msg.function)
    # Send message as JSON
    logging.debug('Publishing message on {}, address={}, function={}'.format(msg_topic, msg.address, msg.function))
    client.publish(topic = msg_topic, payload = msg.to_JSON())

#
# This is a dummy handler and will not be invoked, since this Lambda does
# not handle incoming messages
#
def function_handler(event, context):
    return

# Termination handler
def on_sigterm(signal, frame):
    global trace
    logging.warn('SIGTERM received, calling modbus_trace_stop.')
    modbus_trace_stop(trace)
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
logging.info('Starting modbus_trace function.')
trace = modbus_trace_start(port, baudrate, modbus_mode, serial_mode, serial_term, trace_callback)

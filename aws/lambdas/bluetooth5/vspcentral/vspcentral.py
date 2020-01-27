#########################################################################################
# vspcentral.py - VSP Central Role
#
# Python class for BLE VSP central role
#
# This implements the central role using VSP (virtual serial port) communication with
# a remote peripheral (such as a sensor).  This Lambda requires the central smartBASIC
# application running on the Bluetooth 5 co-processor (BL654) on the Sentrius IG60.
#
#########################################################################################
import greengrasssdk
import logging
import os, os.path
import signal
import sys
import json, json.decoder
import subprocess
import glob
from igsdk.bluetooth5.vsp_central import VSPCentral

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'
port = os.getenv('SERIAL_PORT_DEVICE') or '/dev/ttyS2'
baud = int(os.getenv('SERIAL_BAUD_RATE') or '115200')
peripheral_addr = os.getenv('PERIPHERAL_ADDR') # No default!
le_bandwidth = int(os.getenv('LE_BANDWIDTH') or '1')
log_level = int(os.getenv('VSP_LOG_LEVEL') or '20') # 20 = 'logging.INFO'
vsp_topic = os.getenv('VSP_TOPIC') or 'vsp/{0}/{1}/receive'

SB_UPLOAD_EXE = 'btpa_utility.py'

app_name = None
vsp = None

def upload_app():
    """This function uploads the co-processor application using the
       Sentrius IG60 host tool.
    """
    global app_name
    app_files = glob.glob('*.uwc')
    if len(app_files) != 1:
        logging.error('Invalid deployment, must contain exactly one application (.uwc)!')
        return False
    app_name, ext = os.path.splitext(os.path.basename(app_files[0]))
    # Delete any existing app with the same name
    logging.info('Deleting script {}...'.format(app_name))
    subprocess.run([SB_UPLOAD_EXE, port, str(baud), "delete", app_name, "--force"])
    # Upload the script without the '.uwc' extension
    logging.info('Uploading file {} as {}...'.format(app_files[0], app_name))
    subprocess.run([SB_UPLOAD_EXE, port, str(baud), "upload", app_name, app_files[0]])
    return True

def vsp_central_rx(msg):
    """Callback for messages received from the co-processor"""
    # Validate that the message is valid JSON
    try:
        o = json.loads(msg)
        # Success!
        topic = vsp_topic.format(node_id, peripheral_addr)
        logging.debug('Publishing message on {}: {}'.format(topic, msg))
        client.publish(topic = topic, payload = msg)
    except json.decoder.JSONDecodeError as e:
        logging.warn('Failed to decode message: {} from {}'.format(e, msg))

def vsp_central_start():
    """This function initializes and configures the VSP central
       class.
    """
    global vsp
    logging.info('Starting VSP central role with peripheral address: {}'.format(peripheral_addr))
    # Create the VSP central manager
    vsp = VSPCentral(port, baud, vsp_central_rx, app_name)
    # Start message receive
    vsp.receive_start()
    # Configure the co-processor with the peripheral address
    vsp.set_peripheral_address(peripheral_addr)
    # Configure the co-processor with the bandwidth setting
    vsp.set_le_bandwidth(le_bandwidth)
    # Start the VSP
    vsp.vsp_start()

def function_handler(event, context):
    """Message entry point for the Lambda
    """
    topic = context.client_context.custom['subject']
    logging.debug('Received incoming message on: {}'.format(topic))
    # Send the message using the VSP manager
    vsp.vsp_send(json.dumps(event, separators=(',',':')))

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(log_level)

# Create a greengrass core sdk client
client = greengrasssdk.client('iot-data')

# Verify the configuration
if peripheral_addr is not None:
    if upload_app():
        vsp_central_start()
        logging.info('VSP central manager started!')
    else:
        logging.error('FATAL: Failed to upload co-processor application.')
else:
    logging.error('FATAL: Peripheral address is not configured.')

#-------------------------------------------------------------------------------
# Name:        Reboot.py
# Purpose:     Reboot the device when a message is received
#-------------------------------------------------------------------------------
import greengrasssdk
import logging
import os
import igsdk.device

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'

#
# This handler receives all incoming messages (based on the topic subscription
# that was specified in the deployment).  Only reboot when a message is
# received on this topic:
#
#   device/<node_id>/reboot
#
def function_handler(event, context):
    # Determine the topic
    if context.client_context.custom and context.client_context.custom['subject']:
        topic_el = context.client_context.custom['subject'].split('/')
        if len(topic_el) == 3 and topic_el[0] == 'device' and topic_el[1] == node_id and topic_el[2] == 'reboot':
            logging.info('Rebooting!')
            igsdk.device.reboot(dev)

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)

# Create a greengrass core sdk client
client = greengrasssdk.client('iot-data')

# Initialize the IGSDK device module
logging.info('Starting Reboot function.')
dev = igsdk.device.device_init()

#-------------------------------------------------------------------------------
# Name:        ConnectLTE.py
# Purpose:     Tell the config service to initiate a connect LTE  request
#-------------------------------------------------------------------------------
import greengrasssdk
import logging
import os
import igsdk.config
import json
from time import time

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'

char_topic = 'connect_lte/{}/status'.format(node_id)

def lte_status_callback(data):
    """
    A callback that publishes status to topic
    when lte connection status is returned
    """
    logging.info('lte_status_callback')
    status = {}
    status['lte_status'] = int(data)
    status['timestamp'] = int(time())
    data_json = json.dumps(status, separators=(',',':'), indent=4)
    client.publish(topic=char_topic, payload=data_json)

#
# This handler receives all incoming messages (based on the topic subscription
# that was specified in the deployment).  Only reboot when a message is
# received on this topic:
#
#   device/<node_id>/reboot
#
def function_handler(event, context):
    logging.info('EVENT: ' + str(event))

    # Determine the topic
    try:
        if context.client_context.custom and context.client_context.custom['subject']:
            topic_el = context.client_context.custom['subject'].split('/')
            if len(topic_el) == 3 and topic_el[0] == 'config' and topic_el[1] == node_id and topic_el[2] == 'connectLTE':
                data = json.dumps(event)
                config_manager.connect_lte(data)
            elif len(topic_el) == 3 and topic_el[0] == 'config' and topic_el[1] == node_id and topic_el[2] == 'updateAPS':
                data = json.dumps(event)
                config_manager.update_aps(data)
    except Exception as e:
        logging.info('Exception: ' + str(e) )

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
# Create a greengrass core sdk client
client = greengrasssdk.client('iot-data')
# Initialize the IGSDK config module
logging.info('Starting Config API lambda.')
config_manager = igsdk.config.ConfigManager(lte_status_callback)



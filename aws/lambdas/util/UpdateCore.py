#-------------------------------------------------------------------------------
# Name:        UpdateCore.py
# Purpose:     Tell the provisioning service to install a new gg core
#-------------------------------------------------------------------------------
import greengrasssdk
import logging
import os
import igsdk.prov
import json
from time import time

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'
char_topic = 'prov/{}/status'.format(node_id)

def provisioning_status_callback(data):
    """
    A callback that receives status on provisioning to ig60 device
    and publishes the provisioning status to the 'prov' topic
    """
    logging.info('provisioning_status_callback {}'.format(data))
    status = {}
    status['status'] = int(data)
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
            logging.info('node {} topic {}'.format(node_id, topic_el))
            if len(topic_el) >= 2 and topic_el[0] == 'prov' and topic_el[1] == node_id:
                if len(topic_el) >= 3 and topic_el[2] == 'startCoreDownload':
                    logging.info('start_core_download')
                    data = json.dumps(event)
                    prov_manager.start_core_download(data)
                elif len(topic_el) >= 3 and topic_el[2] == 'performCoreUpdate':
                    logging.info('perform_core_update')
                    data = json.dumps(event)
                    prov_manager.perform_core_update()
                else:
                    logging.error('Unknown request:')
            else:
                logging.error('Failed to match any')
    except Exception as e:
        logging.info('Exception: ' + str(e) )

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
# Create a greengrass core sdk client
client = greengrasssdk.client('iot-data')
# Initialize the IGSDK config module
logging.info('Starting Provisioning API lambda.')
prov_manager = igsdk.prov.ProvManager(provisioning_status_callback)

#-------------------------------------------------------------------------------
# Name:        UpdateCore.py
# Purpose:     Tell the provisioning service to install a new gg core
#-------------------------------------------------------------------------------
import greengrasssdk
import logging
import os
import igsdk.prov
import json

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'

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
            if len(topic_el) == 3 and topic_el[0] == 'prov' and topic_el[1] == node_id and topic_el[2] == 'startCoreDownload':
                data = json.dumps(event)
                prov_manager.start_core_download(data)
            elif len(topic_el) == 3 and topic_el[0] == 'prov' and topic_el[1] == node_id and topic_el[2] == 'performCoreUpdate':
                data = json.dumps(event)
                prov_manager.perform_core_update()
    except Exception as e:
        logging.info('Exception: ' + str(e) )

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(logging.INFO)
# Create a greengrass core sdk client
client = greengrasssdk.client('iot-data')
# Initialize the IGSDK config module
logging.info('Starting Provisioning API lambda.')
prov_manager = igsdk.prov.ProvManager()

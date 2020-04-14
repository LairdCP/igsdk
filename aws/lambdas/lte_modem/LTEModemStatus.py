# LTEModemStatus.py
#
# Demonstration Lambda to publish status of the LTE modem
#
# Instructions
# ------------
#
# 1. Create a ZIP file containing this file, the "greengrasssdk" folder
# (v1.4 or later), and the "igsdk" folder (located under the "python"
# folder in this repository).
#
# 2. Create and publish a Lambda function (Python 3.7) from this ZIP.
#
# 3. Create a deployment for your Greengrass core that contains
# the following:
#
#   a. This Lambda function, configured as "on-demand"
#   b. A subscription from the IoT Cloud to this Lambda on the topic:
#      lte_modem/NODE_ID/req (where NODE_ID is the name of your Greengrass core)
#   c. A subscription from the Lambda to the IoT cloud on the topic:
#      lte_modem/NODE_ID/status (where NODE_ID is the name of your Greengrass core)
# 4. Deploy the Lambda from the AWS console
# 5. In the 'Test' window in the AWS IoT Console, subscribe to the topic:
#      lte_modem/NODE_ID/status (where NODE_ID is the name of your Greengrass core)
# 6. In the 'Test' window of the AWS IoT Console, send a message (with any content, such as '{}') to the topic:
#      lte_modem/NODE_ID/req (where NODE_ID is the name of your Greengrass core)
#
# You should see the response with JSON containing the status of the LTE modem.
#

import greengrasssdk
import logging
import os
import json
from igsdk.modem import get_modem_info

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'
status_topic = os.getenv('STATUS_TOPIC') or 'lte_modem/{0}/status'
log_level = int(os.getenv('MODEM_LOG_LEVEL') or '20') # 20 = 'logging.INFO'

#
# This handler receives all incoming messages (based on the topic subscription
# that was specified in the deployment); be sure not to subscribe to the status
# topic to avoid an infinite loop of messages.
#
def function_handler(event, context):
    # Publish status on configured topic
    modem_status = get_modem_info()
    topic = status_topic.format(node_id)
    client.publish(topic = topic, payload = json.dumps(modem_status))

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(log_level)

# Create a Greengrass Core SDK client.
client = greengrasssdk.client('iot-data')

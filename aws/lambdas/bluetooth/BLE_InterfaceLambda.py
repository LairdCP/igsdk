#
# BLE_InterfaceLambda.py
#
# An interface into the IG60 BLE module providing the following functions:
#	- Discovery
#		Command: Start_Discovery, Stop_Discovery
#		Description: Provides discovery services of bluetooth peripherals
#		Reports: Name, Alias, Address, Class, Icon, RSSI, UUIDs
#		Topic: ble/discovery
#	- Connection
#		Command: Connect, Disconnect
#		Description: Allow for connection and disconnection of a bluetooth peripheral
#					 at a provided address identified during discovery
#		Reports: Success/Failure of connection
#		Topic: ble/connect
#	- Status
#		Command: Status
#		Description: Retrieves the status of a bluetooth peripheral identified during discovery
#		Reports: Properties/status of the peripheral
#		Topic: ble/status
#

import greengrasssdk
import logging
import os
import json
from igsdk.bt_module import bt_init, bt_start_discovery, bt_stop_discovery, bt_connect, bt_disconnect, bt_device_status

log_level = int(os.getenv('BLE_LOG_LEVEL') or '20') # 20 = 'logging.INFO'
discovery_keys = {"Name", "Alias", "Address", "Class", "Icon", "RSSI", "UUIDs"}

discovery_topic = 'ble/discovery'
connect_topic = 'ble/connect'
status_topic = 'ble/status'

DEVICE_IFACE='org.bluez.Device1'

def discovery_callback(path, interfaces):
	""" A callback that receives data about peripherals discovered by the bluetooth manager

	The data on each device is packaged as JSON and published to the cloud on the 
	'ble/discovery' topic
	"""
	for interface in interfaces.keys():
		if interface == DEVICE_IFACE:
			data = {}
			properties = interfaces[interface]
			for key in properties.keys():
				if key in discovery_keys:
					data[key] = properties[key] 
			data_json = json.dumps(data, separators=(',',':'), sort_keys=True, indent=4)
			client.publish(topic=discovery_topic, payload=data_json)

def function_handler(event, context):
	# Extract the command
	command = event['command']

	logging.info('Received BLE trigger event. Command: {}'.format(command))

	if command == 'Start_Discovery':
		bt_start_discovery(bt)
	elif command == 'Stop_Discovery':
		bt_stop_discovery(bt)
	elif command == 'Connect':
		address = event['address']
		connected = bt_connect(bt, address)
		if connected:
			msg = 'Device {} connected successfully'.format(address)
		else:
			msg = 'Device {} failed to connect'.format(address)
		client.publish(topic=connect_topic, payload=msg)
	elif command == 'Disconnect':
		address = event['address']
		disconnected = bt_disconnect(bt, address)
		if disconnected:
			msg = 'Device {} disconnected successfully'.format(address)
		else:
			msg = 'Device {} failed to disconnect'.format(address)
		client.publish(topic=connect_topic, payload=msg)
	elif command == 'Status':
		address = event['address']
		status = bt_device_status(bt, address)
		client.publish(topic=status_topic, payload=status)
	else:
		logging.error('BLE_Interface: Invalid command: {}'.format(command))

	return

#
# The following code runs when this is deployed as a 'long-running' Lambda function
#

# Set up logging
logging.basicConfig()
logging.getLogger().setLevel(log_level)

# Create a greengrass core sdk client
client = greengrasssdk.client('iot-data')

# Initialize the bluetooth manager
bt = bt_init(discovery_callback)
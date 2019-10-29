#
# BLE_InterfaceLambda.py
#
# An interface into the IG60 BLE module providing the following functions:
#	- Discovery
#		Commands: Start, Stop
#		Description: Provides discovery services of bluetooth peripherals
#		Reports: Name, Alias, Address, Class, Icon, RSSI, UUIDs
#		Topic: bluetooth/[gg core]/discovery
#	- Connection
#		Commands: Connect, Disconnect
#		Description: Allow for connection and disconnection of a bluetooth peripheral
#					 at a provided address identified during discovery
#		Reports: Success/Failure of connection
#				 On success, the services & characterisitics of the device that are available
#		Topic: bluetooth/[gg core]/connect
#	- GATT
#		Commands: Read, Write, Notify
#		Description: Read, write, and receive notifications of characteristic changes
#					 in bluetooth peripheral devices that are currently connected
#		Reports: (Read) The value read
#				 (Write) Success/Failure of the operation
#				 (Notify) Any changes the characteristic
#		Topic: bluetooth/[gg core]/gatt
#

import greengrasssdk
import logging
import os
import json
import time
from igsdk.bt_module import bt_init, bt_start_discovery, bt_stop_discovery, bt_connect, bt_disconnect, bt_device_services, bt_read_characteristic, bt_write_characteristic, bt_config_characteristic_notification

node_id = os.getenv('AWS_IOT_THING_NAME') or 'NO_THING_NAME'

log_level = int(os.getenv('BLE_LOG_LEVEL') or '20') # 20 = 'logging.INFO'
discovery_keys = {"Name", "Alias", "Address", "Class", "Icon", "RSSI", "UUIDs"}

discovery_topic = 'bluetooth/{}/discovery'.format(node_id)
connect_topic = 'bluetooth/{}/connect'.format(node_id)
char_topic = 'bluetooth/{}/gatt'.format(node_id)

result_success = 0
result_err = -1

DEVICE_IFACE='org.bluez.Device1'

def discovery_callback(path, interfaces):
	"""
	A callback that receives data about peripherals discovered by the bluetooth manager

	The data on each device is packaged as JSON and published to the cloud on the
	'discovery' topic
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

def connection_callback(data):
	"""
	A callback that receives data about the connection status of devices

	Publishes connection status, and if connected, the device's services and
	characteristics to the 'connect' topic
	"""
	if data['connected']:
		# Get the services and characteristics of the connected device
		device_services = bt_device_services(bt, data['address'])
		data['services'] = device_services['services']

	data_json = json.dumps(data, separators=(',',':'), sort_keys=True, indent=4)
	client.publish(topic=connect_topic, payload=data_json)

def write_notification_callback(data):
	"""
	A callback that receives notifications on write operations to device
	characteristics and publishes the notification data to the 'gatt' topic
	"""
	data_json = json.dumps(data, separators=(',',':'), indent=4)
	client.publish(topic=char_topic, payload=data_json)

def characteristic_property_change_callback(data):
	"""
	A callback that receives notifications on a change to a connected device's
	characteristic properties and publishes the notification data to the 'gatt'
	topic
	"""
	# Convert the changed value to hex
	temp = data['value']
	data['value'] = ''.join('{:02x}'.format(x) for x in temp)

	data_json = json.dumps(data, separators=(',',':'), indent=4)
	client.publish(topic=char_topic, payload=data_json)

def function_handler(event, context):
	if context.client_context.custom and context.client_context.custom['subject']:
		topic_el = context.client_context.custom['subject'].split('/')
		if len(topic_el) >= 2 and topic_el[0] == 'bluetooth' and topic_el[1] == node_id:
			operation = event['operation']
			if len(topic_el) >= 4 and topic_el[2] == 'discovery' and topic_el[3] == 'req':
				if operation == 'Start':
					bt_start_discovery(bt)
				elif operation == 'Stop':
					bt_stop_discovery(bt)
				else:
					logging.error('Unknown discovery operation request: {}'.format(operation))
			if len(topic_el) >= 4 and topic_el[2] == 'connect' and topic_el[3] == 'req':
				address = event['address']

				if operation == 'Connect':
					bt_connect(bt, address)
				elif operation == 'Disconnect':
					if 'purge' in event:
						purge = event['purge']
					else:
						purge = False
					bt_disconnect(bt, address, purge)
				else:
					logging.error('Unknown connect operation request: {}'.format(operation))
			if len(topic_el) >= 4 and topic_el[2] == 'gatt' and topic_el[3] == 'req':
				address = event['address']
				service_uuid = event['service_uuid']
				char_uuid = event['char_uuid']
				if operation == 'Read':
					logging.info('Received GATT read characteristic event for {}'.format(address))

					# Request the characteristic value
					bt_read_characteristic(bt, address, service_uuid, char_uuid)
				elif operation == 'Write':
					logging.info('Received GATT write characteristic event for {}'.format(address))

					# Convert the hex value to a byte array
					value = event['value']
					bytes = bytearray.fromhex(value)

					# Write the value
					bt_write_characteristic(bt, address, service_uuid, char_uuid, bytes)
				elif operation == 'Notify':
					logging.info('Received GATT notification event for {}'.format(address))

					enable = event['enable']
					bt_config_characteristic_notification(bt, address, service_uuid, char_uuid, enable)
				else:
					logging.error('Unknown GATT operation request: {}'.format(operation))
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
bt = bt_init(discovery_callback, characteristic_property_change_callback, connection_callback, write_notification_callback)
#
# vsp_central
#
# Python class for BLE VSP central role
#
# This implements the core functionality of the central
# role using VSP (virtual serial port) communication with
# a remote peripheral (such as a sensor).  This class
# works along with the central smartBASIC application
# running on the Bluetooth 5 co-processor (BL654) on the
# Sentrius IG60.
#

import threading
from ..modbus.serial_queue import SerialQueue
import logging
import time
import json, json.decoder

class VSPCentral(threading.Thread):
    ADDR_CFG_INDEX = 3000
    LE_BANDWIDTH_INDEX = 214

    def __init__(self, port, baudrate, vsp_recv_cb=None, central_app='central', msg_timeout=0.5):
        self.logger = logging.getLogger(__name__)
        self.queue = SerialQueue(port, baudrate, timeout=1)
        self.running = False
        self.vsp_recv_cb = vsp_recv_cb
        self.central_app = central_app
        self.msg_timeout = msg_timeout
        threading.Thread.__init__(self)

    def receive_start(self):
        """Start receiving serial data from the Bluetooth module
        """
        self.queue.receive_start()

    def receive_stop(self):
        """Stop receiving serial data from the Bluetooth module
        """
        self.queue.receive_stop()

    def vsp_start(self):
        """Start the VSP application and data passthrough on the Bluetooth module
        """
        self.running = True
        self.start()
        self.at_cmd(self.central_app, timeout=0)

    def vsp_stop(self):
        """Stop the VSP application
        """
        self.queue.send_break()
        self.queue.receive_flush()
        self.running = False
        self.queue.await_cancel()
        pass

    def run(self):
        """Main thread routine - await and verify payloads
        """
        while self.running:
            self.logger.debug('Awaiting incoming message.')
            msg = self.queue.await_msg()
            if msg:
                decoded = msg.decode('utf-8')
                stripped = decoded.strip()
                if stripped.startswith('##'):
                    # Control message from smartBASIC application
                    self.logger.info(stripped)
                else:
                    # Handle payload completion by awaiting additional messages
                    while True:
                        msg = self.queue.await_msg(self.msg_timeout)
                        if msg is not None:
                            decoded = decoded + msg.decode('utf-8')
                        else:
                            break
                    self.logger.debug('Received message: {}'.format(decoded))
                    if self.vsp_recv_cb:
                        self.vsp_recv_cb(decoded)
        self.logger.debug('Message receive stopped.')

    def vsp_send(self, message):
        """Send a message via the Bluetooth co-processor.
        """
        self.logger.debug('Sending message: {}'.format(message))
        self.queue.send_msg(message.encode('utf-8'))

    def at_cmd(self, request, timeout=5):
        """Send an AT command, await and parse the response
        """
        self.queue.send_msg((request+'\r').encode('utf-8'))
        lines = []
        done = False
        while not done:
            r = self.queue.await_msg(timeout)
            if r is not None:
                resp = r.decode('utf-8')
                # Decode each response line into a tuple with the result code
                # followed by an array of response arguments
                for l in resp.strip().split('\r'):
                    a = l.replace('\t', ' ').split(' ')
                    result = int(a[0])
                    lines.append((result, a[1:]))
                    # If the last result is 0 or 1, we are done
                    if result == 0 or result == 1:
                        done = True
            else:
                done = True
        return lines

    def at_cfg_set(self, index, val):
        """Write a configuration key into the module
        """
        resp = self.at_cmd('AT+CFG {} {}'.format(index, val))
        if len(resp) > 0:
            result, output = resp[0]
            if result != 0:
                self.logger.warn('Attempt to write key failed: {}'.format(result))
        else:
            self.logger.warn('Unexected or missing response when writing key.')

    def at_cfg_get(self, index):
        """Read a configuration key from the module
        """
        resp = self.at_cmd('AT+CFG {} ?'.format(index))
        if len(resp) > 0:
            result, output = resp[0]
            if result == 27:
                return int(output[0], 0)
            else:
                self.logger.warn('Attempt to read key failed: {}'.format(result))
        else:
            self.logger.warn('Unexpected or missing response when reading key.')
        return None

    def set_peripheral_address(self, address):
        """Set the remote peripheral MAC address by programming
           configuration keys on the BL654
        """
        self.logger.debug('Setting peripheral address: {}'.format(address))
        addr = address.replace(':', '')
        self.at_cfg_set(self.ADDR_CFG_INDEX, int(addr[0:2], 16)) # Byte 0
        self.at_cfg_set(self.ADDR_CFG_INDEX + 1, int(addr[2:8], 16)) # Bytes 1-3
        self.at_cfg_set(self.ADDR_CFG_INDEX + 2, int(addr[8:14], 16)) # Bytes 4-6

    def set_le_bandwidth(self, value):
        """Set the LE bandwidth configuration key on the BL654
        """
        self.logger.debug('Setting LE bandwidth: {}'.format(value))
        self.at_cfg_set(self.LE_BANDWIDTH_INDEX, value)

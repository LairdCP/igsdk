#
# peripheral.py
#
import select
import time
import os
import errno
import threading
import logging
import json
import random
import signal
import serial

import sys
PYTHON3 = sys.version_info >= (3, 0)
if PYTHON3:
    import queue as Queue
else:
    import Queue

class VSPPeripheral(threading.Thread):

    DEFAULT_BREAK_DURATION = 0.25

    def __init__(self, port, baudrate, timeout=0.5, read_buf_size=1024):
        self.serial = serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        self.queue = Queue.Queue()
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.connected = False
        threading.Thread.__init__(self)

    def run(self):
        """Main thread routine - receive packets and put them on the queue
        """
        while self.running:
            b = self.serial.read(1024)
            if b and len(b) > 0:
                self.queue.put_nowait(b)

    def receive_start(self):
        """Start receiving data packets.
        """
        self.logger.debug('Starting serial queue thread.')
        self.running = True
        self.start()

    def receive_stop(self):
        """Stop receiving data packets.
        """
        self.logger.debug('Stopping serial queue thread.')
        self.running = False
        self.serial.cancel_read()
        self.queue.put_nowait(None)

    def await_msg(self, timeout=None):
        """Await a single message on the queue.
        """
        msg = None
        try:
            self.logger.debug('Awaiting message...')
            msg = self.queue.get(True, timeout)
            if msg:
                self.logger.debug('Returning message from queue.')
            else:
                self.logger.debug('Queue receive stopped.')
        except Queue.Empty:
            self.logger.debug('Queue is empty.')
        return msg

    def send_msg(self, msg):
        """Send a message on the serial port.
        """
        self.serial.write(msg)

    def receive_flush(self):
        """Flush all queued messages and input byte buffer.
        """
        self.serial.reset_input_buffer()
        try:
            while True:
                self.queue.get(False)
        except Queue.Empty:
            pass

    def send_break(self, duration = DEFAULT_BREAK_DURATION):
        self.serial.send_break(duration)

    def simulate(self):
        """Simulate a running BLE sensor by periodically sending a message
           Handle received messages that modify the message periodically
        """
        # Stop any running script
        self.logger.info('Starting remote script.')
        self.send_break()
        time.sleep(3)
        # Start the serial receive
        self.logger.info('Starting serial receive.')
        periph.receive_start()
        # Start the peripheral app on the BL654
        periph.send_msg('peripheral\r\n'.encode('utf-8'))
        msg_period = 10
        while self.running:
            self.logger.debug('Awaiting message for {} seconds...'.format(msg_period))
            msg = self.await_msg(msg_period)
            if msg is not None:
                msg_str = msg.decode('utf-8').strip()
                # Attempt to decode as JSON
                try:
                    msg_obj = json.loads(msg_str)
                    p = msg_obj.get('period', None)
                    if p is not None:
                        self.logger.info('Changing message period to {}'.format(p))
                        msg_period = p
                    else:
                        self.logger.info('Received message with no period, ignoring.')
                except:
                    # Could not decode JSON, so sssume that message is a status from the BL654
                    self.logger.debug(msg_str)
                    if msg_str.startswith('## Connected'):
                        self.connected = True
                        self.logger.info('VSP connected!')
                    elif msg_str.startswith('## Disconnected'):
                        self.connected = False
                        self.logger.info('VSP disconnected!')
            else:
                if self.running:
                    if self.connected:
                        # Timeout occurred, send simulated message
                        send_msg = { 'temperature' : random.uniform(-20, 100), 'timestamp' : time.time() }
                        self.logger.info('Sending simulated message: {}'.format(send_msg))
                        self.serial.write(json.dumps(send_msg, separators=(',', ':')).encode('utf-8'))
                else:
                    self.logger.debug('Stopping simulated messages.')

def sigint_handler(signal_received, frame):
    logging.warn('CTRL-C detected, stopping receive.')
    periph.receive_stop()
    sys.exit(0)

# Check command line
if len(sys.argv) < 3:
    logging.error('Invalid command line - usage: {} serial_port baud_rate [debug]'.format(sys.argv[0]))
    exit(1)

if len(sys.argv) > 3:
    level = int(sys.argv[3])
else:
    level = logging.INFO

# Configure logging
logging.basicConfig()
logging.getLogger().setLevel(level)

# Catch CTRL-C
signal.signal(signal.SIGINT, sigint_handler)

# Create VSP peripheral client
msg_delay = 10
periph = VSPPeripheral(sys.argv[1], sys.argv[2])

# Start the simulation
periph.simulate()
logging.info('All done!')
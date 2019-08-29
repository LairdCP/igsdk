#
# modbus_trace
#

import threading
from .message import ModbusMessage
from .modbus_queue import ModbusQueue
import logging

class ModbusTrace(threading.Thread):
    """Class that encapsulates the Modbus trace function.
    """
    def __init__(self, port, baudrate, modbus_mode, serial_mode, serial_term, msg_callback):
        self.logger = logging.getLogger(__name__)
        self.queue = ModbusQueue(port, baudrate, modbus_mode, serial_mode, serial_term)
        self.msg_callback = msg_callback
        self.running = False
        threading.Thread.__init__(self)

    def run(self):
        while self.running:
            msgs = self.queue.await_modbus_msgs()
            if msgs and len(msgs) > 0:
                for m in msgs:
                    self.logger.debug('Forwarding message to callback.')
                    self.msg_callback(m)
        self.logger.debug('Message receive stopped.')

    def trace_start(self):
        self.running = True
        # Start receiving packets
        self.logger.info('Starting receive queue.')
        self.queue.receive_start()
        # Start message receive thread
        self.start()

    def trace_stop(self):
        self.running = False
        self.queue.receive_stop()

def modbus_trace_start(port, baudrate, modbus_mode, serial_mode, serial_term, msg_callback):
    """Starts Modbus Trace function, sniffing for Modbus frames and returning them via callback.

    This function listens on a specified serial port for Modbus frames (either ASCII or RTU) and
    returns them via a callback function.

    Args:

        port: Port to listen on (e.g., '/dev/ttyS2')
        baudrate: Baud rate (e.g., 115200)
        modbus_mode: 0 for ASCII, 1 for RTU
        serial_mode: 0: RS-232, 1:RS-485/422 half duplex, 2: RS-485/422 full duplex
        serial_term: 0 for no termination, 1 to enable termination (RS485/422 only)
        msg_callback: Callback function to receive frames.  The callback should accept a single argument, a ModbusMessage instance.

    Returns:

        An object instance to be used in the modbus_trace_*() functions.
    """
    trace = ModbusTrace(port, baudrate, modbus_mode, serial_mode, serial_term, msg_callback)
    trace.trace_start()
    return trace

def modbus_trace_stop(trace):
    """Stop the Modbus trace function.
    """
    trace.trace_stop()


#
# modbus_master
#

from message import ModbusMessage
from modbus_queue import ModbusQueue
import logging
import time

_master = None

class ModbusMaster:
    """Class that encapsulates the Modbus master function.
    """
    def __init__(self, port, baudrate, modbus_mode, serial_mode, serial_term):
        self.logger = logging.getLogger(__name__)
        self.queue = ModbusQueue(port, baudrate, modbus_mode, serial_mode, serial_term, except_on_timeout=True)

    def start(self):
        self.queue.receive_start()

    def stop(self):
        self.queue.receive_stop()
        
    def await_resp(self, req_address, req_function, resp_timeout):
        self.logger.debug('Awaiting slave response for address {}, function {}'.format(req_address, req_function))
        resp_start = time.time()
        resp_msgs = self.queue.await_modbus_msgs(resp_timeout)
        resp_end = time.time()
        if resp_msgs and len(resp_msgs) > 0:
            if resp_msgs[0].address == req_address and resp_msgs[0].function & 0x7F == req_function:
                self.logger.debug('Got slave response: {}, {}, {}'.format(resp_msgs[0].address, resp_msgs[0].function, resp_msgs[0].data))
                return resp_msgs[0], 0
            else:
                self.logger.debug('Invalid or mismatched slave response')
                return None, resp_timeout - (resp_start - resp_end)
        else:
            # No bytes received, we exceeded the timeout
            self.logger.debug('Slave response timed out.')
            return None, 0
        
    def send_await(self, req, resp_timeout):
        self.queue.send_modbus_msg(req)
        resp, timeout_remain = self.await_resp(req.address, req.function, resp_timeout)
        while not resp and timeout_remain > 0:
            resp, timeout_remain = self.await_resp(req.address, req.function, timeout_remain)
        return resp


def modbus_master_start(port, baudrate, modbus_mode, serial_mode, serial_term):
    """Initialize and start the Modbus Master function.

    This function initializes the Modbus Master function on a specified serial port.

    Args:

        port: Port to listen on (e.g., '/dev/ttyS2')
        baudrate: Baud rate (e.g., 115200)
        modbus_mode: 0 for ASCII, 1 for RTU
        serial_mode: 0: RS-232, 1: RS-485/422 half duplex, 2: RS485/422 full duplex
        serial_term: 0 for no termination, 1 to enable termination (RS485/422 only)

    Returns:

        An object instance to be used in the modbus_master_*() functions.
    """
    master = ModbusMaster(port, baudrate, modbus_mode, serial_mode, serial_term)
    master.start()
    return master

def modbus_master_stop(master):
    """De-initialize the Modbus Master function
    """
    master.stop()
        
def modbus_master_send_await(master, req, resp_timeout=5):
    """Send a Modbus master request, and await a response.
    
    This function sends a Modbus request (as the master), and awaits a reponse.  The response is
    expected to have the same slave address and function as the request, or an exception response
    (which matches the request function + 0x80).
    
    Args:
    
        master: The object returned from modbus_master_init()
        req: Request message (instance of a ModbusMessage)
        resp_timeout: Timeout to await response (in seconds); default is 5 seconds.
        
    Returns:
        A ModbusMessage representing the response, or None if no message was received within the timeout.
    """
    return master.send_await(req, resp_timeout)

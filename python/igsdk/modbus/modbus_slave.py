#
# modbus_slave.py
#

import threading
from .message import ModbusMessage
from .modbus_queue import ModbusQueue
from .state_util import read_registers, read_bits, write_registers, write_bits, mask_write_register
import logging

class ModbusSlave(threading.Thread):
    """Class that encapsulates the Modbus slave function.
    """
    def __init__(self, port, baudrate, modbus_mode, serial_mode, serial_term, addr, get_read_cb, get_write_cb, set_write_cb):
        self.logger = logging.getLogger(__name__)
        self.queue = ModbusQueue(port, baudrate, modbus_mode, serial_mode, serial_term)
        self.addr = addr
        self.get_read_cb = get_read_cb
        self.get_write_cb = get_write_cb
        self.set_write_cb = set_write_cb
        self.running = False
        threading.Thread.__init__(self)

    def slave_start(self):
        self.running = True
        self.queue.receive_start()
        self.start()

    def slave_stop(self):
        self.running = False
        self.queue.receive_stop()
        
    def run(self):
        while self.running:
            self.logger.debug('Awaiting request for address {}'.format(self.addr))
            msgs = self.queue.await_modbus_msgs()
            if msgs and len(msgs) > 0:
                if msgs[0].address == self.addr:
                    resp = self.handle_request(msgs[0])
                    if resp:
                        self.send_resp(resp)
                else:
                    self.logger.info('Ignoring request for slave address {}'.format(msgs[0].address))
        self.logger.debug('Message receive stopped.')

    def send_resp(self, resp):
        self.queue.send_modbus_msg(resp)

    def get_read_state(self, key):
        """Get read state key using callback
        """
        if self.get_read_cb:
            state = self.get_read_cb()
            if state:
                if key in state:
                    return state[key]
        self.logger.warn('Read state for {} missing or unreadable.'.format(key))
        return None

    def get_write_state(self, key):
        """Get write state key using callback
        """
        if self.get_write_cb:
            state = self.get_write_cb()
            if state:
                if key in state:
                    return state[key]
        self.logger.warn('Write state for {} missing or unreadable.'.format(key))
        return None

    def set_write_state(self, key, delta):
        """Set write state key using callback
        """
        if self.set_write_cb:
            self.logger.debug('Writing state for {} with {}'.format(key, delta))
            key_delta = { key : delta }
            self.set_write_cb(key_delta)
        else:
            self.logger.warn('Cannot write state for {}.'.format(key))
        
    def read_registers_resp(self, key, req_data):
        """Get response payload for read register request using state callback
        """
        addr = (req_data[0] * 256) + req_data[1]
        req_len = (req_data[2] * 256) + req_data[3]
        state = self.get_read_state(key)
        if state:
            return read_registers(state, addr, req_len)
  
    def read_bits_resp(self, key, req_data):
        """Get response payload for read bits request using state callback
        """
        addr = (req_data[0] * 256) + req_data[1]
        req_len = (req_data[2] * 256) + req_data[3]
        state = self.get_read_state(key)
        if state:
            return read_bits(state, addr, req_len)

    def write_register_resp(self, key, req_data):
        """Perform write of single register using callbacks, and return response payload
        """
        addr = (req_data[0] * 256) + req_data[1]
        new_data = req_data[2:4]
        state = self.get_write_state(key)
        if state:
            delta = write_registers(state, addr, new_data)
            if delta:
                self.set_write_state(key, delta)
                return req_data
        
    def write_registers_resp(self, key, req_data):
        """Perform write of multiple registers using callbacks, and return response payload
        """
        addr = (req_data[0] * 256) + req_data[1]
        req_len = (req_data[2] * 256) + req_data[3]
        byte_count = req_data[4]
        new_data = req_data[5:]
        state = self.get_write_state(key)
        if state and byte_count == len(new_data):
            delta = write_registers(state, addr, new_data)
            if delta:
                self.set_write_state(key, delta)
                return req_data

    def mask_write_register_resp(self, key, req_data):
        """Perform mask write of register using callbacks, and return response payload
        """
        addr = (req_data[0] * 256) + req_data[1]
        and_mask = req_data[2:4]
        or_mask = req_data[4:6]
        state = self.get_write_state(key)
        if state:
            delta = mask_write_register(state, addr, and_mask, or_mask)
            if delta:
                self.set_write_state(key, delta)
                return req_data

    def write_bit_resp(self, key, req_data):
        """Perform write of a single bit using callbacks, and return response payload
        """
        addr = (req_data[0] * 256) + req_data[1]
        val = req_data[2] # Ignore LSB of value, should always be 0
        state = self.get_write_state(key)
        if state:
            delta = write_bits(state, addr, [val], 1)
            if delta:
                self.set_write_state(key, delta)
                return req_data
        
    def write_bits_resp(self, key, req_data):
        """Perform write of multiple bits using callbacks, and return response payload
        """
        addr = (req_data[0] * 256) + req_data[1]
        nbits = (req_data[2] * 256) + req_data[3]
        byte_count = req_data[4]
        new_data = req_data[5:]
        state = self.get_write_state(key)
        if state and nbits <= 8*len(new_data):
            delta = write_bits(state, addr, new_data, nbits)
            if delta:
                self.set_write_state(key, delta)
                return req_data[:4]

    def handle_request(self, req):
        """Handle a single Modbus message request message; returns a response Modbus message.
        """
        self.logger.info('Handling request message: address={}, function={}, data={}'.format(req.address, req.function, req.data))
        resp_data = []
        if req and req.data:
            if req.function == ModbusMessage.FUNCTION_READ_COILS and len(req.data) == 4:
                resp_data = self.read_bits_resp('coil', req.data)
            elif req.function == ModbusMessage.FUNCTION_READ_DISCRETE_INPUTS and len(req.data) == 4:
                resp_data = self.read_bits_resp('discrete', req.data)
            elif req.function == ModbusMessage.FUNCTION_READ_HOLDING_REGISTERS and len(req.data) == 4:
                resp_data = self.read_registers_resp('holding', req.data)
            elif req.function == ModbusMessage.FUNCTION_READ_INPUT_REGISTERS and len(req.data) == 4:
                resp_data = self.read_registers_resp('input', req.data)
            elif req.function == ModbusMessage.FUNCTION_WRITE_SINGLE_COIL and len(req.data) == 4:
                resp_data = self.write_bit_resp('coil', req.data)
            elif req.function == ModbusMessage.FUNCTION_WRITE_SINGLE_REGISTER and len(req.data) == 4:
                resp_data = self.write_register_resp('holding', req.data)
            elif req.function == ModbusMessage.FUNCTION_WRITE_MULTIPLE_COILS:
                resp_data = self.write_bits_resp('coil', req.data)
            elif req.function == ModbusMessage.FUNCTION_WRITE_MULTIPLE_REGISTERS:
                resp_data = self.write_registers_resp('holding', req.data)
            elif req.function == ModbusMessage.FUNCTION_MASK_WRITE_REGISTER and len(req.data) == 6:
                resp_data = self.mask_write_register_resp('holding', req.data)
            else:
                self.logger.info('Returning Exception response (Illegal function)')
                return ModbusMessage(req.address, req.function | 0x80, [1]) # Exception response - Illegal Function
        if resp_data and len(resp_data) > 0:
            self.logger.info('Returning response data = {}'.format(resp_data))
            return ModbusMessage(req.address, req.function, resp_data)
        else:
            self.logger.info('Returning Exception response (Illegal address)')
            return ModbusMessage(req.address, req.function | 0x80, [2]) # Exception response - Illegal address

def modbus_slave_start(port, baudrate, modbus_mode, serial_mode, serial_term, slave_addr, get_read_cb, get_write_cb, set_write_cb):
    """Perform Modbus Slave function, responding to Modbus requests based on state

    This function listens for Modbus requests from a master, and responds
    based on various state values.  For read operations (Read Coils,
    Read Discrete Registers, Read Holding Registers, Read Input
    Registers), the current state retrieved via callback is used to
    construct the reponse.  For write operations (Write Single Coil,
    Write Single Register, Write Multiple Coils, Write Multiple
    Registers, Mask Write Register), the current state is updated
    with the written values via callback.

    This function will return the valid Modbus response when the
    requested operation is available via the data in the callbacks;
    otherwise, a Modbus exception response will be sent.

    Args:

        port: Port to listen on (e.g., '/dev/ttyS2')
        baudrate: Baud rate (e.g., 115200)
        modbus_mode: 0 for ASCII, 1 for RTU
        serial_mode: 0: RS-232, 1: RS-485/422 half duplex, 2: RS485/422 full duplex
        serial_term: 0 for no termination, 1 to enable termination (RS485/422 only)
        get_read_cb: Callback function to get readable values
        get_write_cb: Callback function to get writeable values
        set_write_cb: Callback function to set writeable values

    get_read_cb() takes no parameters, and should return a Python
    dictionary with the readable elements (see Schema, below).

    get_write_cb() takes no parameters, and should return a Python
    dictionary with the writeable elements (see Schema, below). The
    caller should NOT update the writeable state when get_write_cb() is
    called.

    set_write_cb() takes a single parameter, which is a Python dictionary
    containing the delta to the writeable values returned from
    get_write_cb().  The caller should update the writeable state
    when set_write_cb() is called.

    Schema:

    The readable state contains up to 4 top-level keys: 'coil',
    'discrete', 'holding', 'input'; the writeable state contains
    'coil' and 'holding'.  Each of these objects contains elements
    that represent the starting address in hexadecimal, with the values
    being an array of one or more values.  For example, in Python:

        { 'coil' :
            { '0' : [1, 0, 0, 1] },
            { 'a0' : [0, 0, 0, 0] }
        },
        { 'discrete' :
            { 'f0' : [0, 0] }
        },
        { 'holding' :
            { 'a000' : [255, 128, 7, 4 ] }
        },
        { 'input' :
            { 'e4b2' : [ 65535 ]}
        }

    The addresses should be normalized to no leading zeros and
    lower case hexadecimal.  No overlap of values should be present,
    and reads/write across elements are not supported (i.e., the
    read/write will only succeed if the Modbus request start address
    and length is contained in a single element).

    Returns:

        An object instance to be used in the modbus_slave_*() functions.
    """
    # Create Slave object
    slave = ModbusSlave(port, baudrate, modbus_mode, serial_mode, serial_term, slave_addr, get_read_cb, get_write_cb, set_write_cb)
    # Start processing requests
    slave.slave_start()
    return slave

def modbus_slave_stop(slave):
    slave.slave_stop()

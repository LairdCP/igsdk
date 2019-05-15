#
# modbus_queue.py
#
from serial_queue import SerialQueue
from message import ModbusMessage
from asciiparser import ModbusASCIIParser
from rtuparser import ModbusRTUParser
from ..device import device_enabled, device_activity, device_exception
import logging

class ModbusQueue(SerialQueue):
    """A queue that receives and decodes incoming Modbus messages

    ModbusQueue (based on SerialQueue) manages continuously receiving
    Modbus messages (either ASCII or RTU frames).
    """
    def __init__(self, port, baudrate, modbus_mode, serial_mode=0, serial_term=0, except_on_timeout=False):
        super(ModbusQueue, self).__init__(port, baudrate, serial_mode, serial_term)
        self.logger = logging.getLogger(__name__)
        self.modbus_mode = modbus_mode
        self.except_on_timeout = except_on_timeout
        if modbus_mode and modbus_mode > 0:
            self.parser = ModbusRTUParser()
            self.logger.info('Created RTU parser.')
        else:
            self.parser = ModbusASCIIParser()
            self.logger.info('Created ASCII parser.')

    def send_modbus_msg(self, msg):
        """Send a Modbus message.
        
        Args:
            msg: The message to send (instance of ModbusMessage)
        """
        self.receive_flush()
        if self.modbus_mode > 0:
            msg_bytes = msg.rtu_frame()
        else:
            msg_bytes = msg.ascii_frame()
        self.logger.debug('Sending Modbus message: {}, {}, {}'.format(msg.address, msg.function, msg.data))
        self.send_msg(msg_bytes)
        device_activity(self.device)

    def await_modbus_msgs(self, timeout=None):
        """Await Modbus messages from the queue.

        Args:
            timeout: Timeout to await messages, in seconds

        Returns:
            List of ModbusMessages (can be empty, in case of a timeout)
        """
        msgs = []
        b = self.await_msg(timeout)
        if b:
            msgs = self.parser.msgs_from_bytes(b)
        if self.except_on_timeout:
            if not msgs or len(msgs) == 0:
                device_exception(self.device)
            else:
                device_enabled(self.device) # Remove exception indication
                device_activity(self.device)
        return msgs

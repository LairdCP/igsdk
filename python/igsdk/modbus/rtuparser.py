#
# rtuparser.py
#

from .baseparser import ModbusBaseParser
from .message import ModbusMessage
import logging
import time
import struct

class ModbusRTUParser(ModbusBaseParser):

    def __init__(self):
        """Construct a ModbusRTUParser.
        """
        ModbusBaseParser.__init__(self)
        self.logger = logging.getLogger(__name__)

    def _try_parse_fixed(self, b, datalen):
        """Internal method to attempt to parse a fixed-length message.

        Args:
            b: Byte string to parse (can be longer than a single message)
            datalen: Length of message data bytes (not including address, function, and CRC bytes)

        Returns:
            Tuple: (msg, rem):
                msg: A ModbusMessage instance, or None
                rem: Remaining bytes (byte string)

            If a fixed-length message can be successfully parsed, including the
            CRC, then 'msg' contains the message, and 'rem' contains any remaining
            bytes (after the CRC).  Otherwise, 'msg' is None, and 'rem' contains
            the original byte stream.
        """
        msg = None
        rem = b
        if len(b) >= datalen + 4: # Must contain address, function, CRC16
            msg = ModbusMessage(b[0], b[1], list(bytearray(b[2:2+datalen])), int(time.time() * 1000))
            msg_crc = b[datalen+2] + 256 * b[datalen+3]
            if msg_crc == msg.compute_crc():
                rem = b[datalen+4:]
            else:
                msg = None
        return msg, rem

    def _try_parse_variable(self, b, leading_bytes=0):
        """Internal method to attempt to parse a variable-length message.
        Args:
            b: Byte string to parse (can be longer than a single message)
            leading_bytes: Count of leading bytes before the byte count (after the address & function)

        Returns:
            Tuple: (msg, rem):
                msg: A ModbusMessage instance, or None
                rem: Remaining bytes (byte string)

            If a variable-length message can be successfully parsed, including the
            CRC, then 'msg' contains the message, and 'rem' contains any remaining
            bytes (after the CRC).  Otherwise, 'msg' is None, and 'rem' contains
            the original byte stream.
        """
        if len(b) >= leading_bytes + 3: # Make sure we have enough to parse address, function, leading bytes & data length byte
            fixed_datalen = b[leading_bytes + 2] + leading_bytes + 1 # Fixed length is leading bytes, length byte, and byte count
            # Attempt to parse entire message, given the length after the function code
            return self._try_parse_fixed(b, fixed_datalen)
        return None, b

    def _try_parse_unknown(self, b):
        """Internal method to attempt to parse messages when the message type (request or response) is unkown.

        Args:
            b: Byte string to parse (can be longer than a single message)

        Returns:
            Tuple: (msg, rem):
                msg: A modbusMessage instance, or None
                rem: Remaining bytes (byte string)

            If a message can be successfully parsed, including the CRC, then 'msg'
            contains the message, and 'rem' contains any remaining bytes (after the
            CRC).  Otherwise, 'msg' is None, and 'rem' contains the original byte stream.
        """
        # Fixed messages - 4 bytes:
        #   Read Coil Status (0x01) Request
        #   Read Input Status (0x02) Request
        #   Read Holding Register (0x03) Request
        #   Read Input Register (0x04) Request
        #   Force Single Coil (0x05) Request
        #   Force Single Coil (0x05) Response
        #   Preset Single Register (0x06) Request
        #   Preset Single Register (0x06) Response
        #   Diagnostics (0x08) Request [Multiple sub-functions]
        #   Diagnostics (0x08) Response [Multiple sub-functions]
        #   Fetch Event Counter (0x0B) Response
        #   Fetch Communication Event Log (0x0C) Response
        #   Force Multiple Coils (0x0F) Response
        #   Preset Multiple Registers (0x10) Response
        msg, rem = self._try_parse_fixed(b, 4)
        if not msg:
            # Variable messages - 0 leading bytes:
            #   Read Coil Status (0x01) Response
            #   Read Input Status (0x02) Response
            #   Read Holding Register (0x03) Response
            #   Read Input Register (0x04) Response
            #   Report Slave ID (0x11) Response
            #   Read File Record (0x14) Request
            #   Read File Record (0x14) Response
            #   Write File Record (0x15) Request
            #   Write File Record (0x15) Response
            #   Read/Write Multiple Registers (0x17) Response
            msg, rem = self._try_parse_variable(b)
        if not msg:
            # Fixed messages - 0 bytes:
            #   Read Exception Status (0x07) Request
            #   Fetch Event Counter (0x0B) Request
            #   Fetch Communication Event Log (0x0C) Request
            #   Report Slave ID (0x11) Request
            msg, rem = self._try_parse_fixed(b, 0)
        if not msg:
            # Variable messages - 4 leading bytes:
            #   Force Multiple Coils (0x0F) Request
            #   Preset Multiple Registers (0x10) Request
            msg, rem = self._try_parse_variable(b, 4)
        if not msg:
            # Fixed messages - 1 byte:
            #   Error Status + Exception Code
            #   Read Exception Status (0x07) Response
            msg, rem = self._try_parse_fixed(b, 1)
        if not msg:
            # Fixed messages - 2 bytes:
            #   Read FIFO Queue (0x18) Request
            msg, rem = self._try_parse_fixed(b, 2)
        if not msg:
            # Fixed messages - 3 bytes:
            #   Diagnostics (0x08) Request [Sub-function 3]
            #   Diagnostics (0x08) Response [Sub-function 3]
            msg, rem = self._try_parse_fixed(b, 3)
        if not msg:
            # Fixed messages - 6 bytes:
            #   Mask Write Register (0x16) Request
            #   Mask Write Register (0x16) Response
            msg, rem = self._try_parse_fixed(b, 6)
        if not msg:
            # Variable messages - 8 leading bytes:
            #   Read/Write Multiple Registers (0x17) Request
            msg, rem = self._try_parse_variable(b, 8)
        if not msg:
            # Nothing can be parsed, remainder is entire input
            rem = b
            if rem and len(rem) > 0:
                self.logger.warning('Unknown or invalid RTU frame(s), dropped.')
        return msg, rem

    def msgs_from_bytes(self, b):
        """Parse Modbus RTU messages from bytes
        Modbus RTU messages are delimited by delays on the serial line (the specification calls for a delay
        of 3.5 bit times to mark the begin/end of an RTU frame).  Unfortunately, the Linux (and Python)
        serial interface cannot set delays with this level of granularity (for example, 3.5 bits at 9600 baud
        is approximately 0.36 milliseconds, while the Linux TTY driver can only set inter0character timeouts
        as multiple of 100 milliseconds!)

        This function assumes that the caller will attempt to receive multiple RTU frames (for example, using
        a 100ms intercharacter timeout, which will eventually occur unless the Modbus bus is VERY busy), and
        then pass all data to be parsed into multiple messages.  In other words, this function assumes the
        input bytes contain one or more frames, and the end of the buffer is aligned with the end of a
        frame.  Input messages will be parsed until an unparseable RTU message is found, then all
        remaining bytes are discared and all parsed messages are returned.
        """
        msgs = []
        d = struct.unpack('{:X}B'.format(len(b)), b)
        msg, rem = self._try_parse_unknown(d)
        while msg:
            msgs.append(msg)
            self.logger.debug('Parsed RTU frame: address={}, function={}, len={}'.format(msg.address, msg.function, len(msg.data) if msg.data else 0))
            msg, rem = self._try_parse_unknown(rem)
        return msgs

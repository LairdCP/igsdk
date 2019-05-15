#
# asciiparser.py
#

from baseparser import ModbusBaseParser
from message import ModbusMessage
import re
import logging
import time

class ModbusASCIIParser(ModbusBaseParser):
    
    ASCII_MSG_REGEX = '.*:([0-9a-fA-F]{2})([0-9a-fA-F]{2})(([0-9a-fA-F]{2})*)([0-9A-Fa-f]{2})'
    
    def __init__(self):
        """Construct a ModbusASCIIParser.
        """
        ModbusBaseParser.__init__(self)
        self.logger = logging.getLogger(__name__)
        self.matcher = re.compile(self.ASCII_MSG_REGEX)
        self.remainder = ''
    
    def _parse_msg(self, b):
        """Internal method, parses a single Modbus ASCII message frame, with the '\r\n' delimiter already removed.
        """
        msg = None
        r = self.matcher.match(b)
        if r:
            address = int(r.group(1), 16)
            function = int(r.group(2), 16)
            # Convert data into bytes
            data = []
            for i in range(0, len(r.group(3)), 2):
                datum = int(r.group(3)[i:i+2], 16)
                data.append(datum)
            # Construct message
            msg = ModbusMessage(address, function, data, int(time.time() * 1000))
            # Verify LRC
            msg_lrc = int(r.group(5), 16)
            if msg_lrc != msg.compute_lrc():
                self.logger.warning('LRC mismatch, frame dropped.')
                msg = None
        return msg
        
    def msgs_from_bytes(self, b):
        """Parse Modbus ASCII messages from bytes
        
        Modbus ASCII messages are delimited by start/end characters; this method takes the input
        bytes and prepends them with any leftover bytes from a previous pass.  Messages are parsed until
        no more delimiters are found.  Any unparseable frames (e.g., invalid checksum) are skipped.
        """
        msgs = []
        # User remainder bytes
        parse_bytes = self.remainder + b.decode('ascii')
        # Find the first frame delimiter
        i = parse_bytes.find('\r\n')
        while i >= 0:
            # Try to parse a single message
            m = self._parse_msg(parse_bytes[:i])
            # Remove parsed bytes and delimter
            parse_bytes = parse_bytes[i+2:]
            # Add parsed message, if any
            if m:
                msgs.append(m)
                self.logger.debug('Parsed ASCII frame: address={}, function={}, len={}'.format(m.address, m.function, len(m.data) if m.data else 0))
            #else - warn?
            i = parse_bytes.find('\r\n')
        # Store any remaining bytes for the next pass
        self.remainder = parse_bytes
        return msgs
        

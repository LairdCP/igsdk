#
# baseparser.py
#
# Base class for Modbus message parser
#

class ModbusBaseParser:
    """Base class for Modbus message parsing.
    """ 
    def __init__(self):
        pass

    def msgs_from_bytes(self, b):
        """Parse messages from a byte string
        """

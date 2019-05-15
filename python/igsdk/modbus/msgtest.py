#
# msgtest.py
#

from modbus_trace import modbus_trace_start
from message import ModbusMessage
import argparse
import random
import time
import serial

msgcount = 0

def count_msg(msg):
    global msgcount
    msgcount = msgcount + 1
    if msgcount % 100 == 0:
        print('...Received {} messages'.format(msgcount))

test_messages = [
    # Fixed 4-byte payload (e.g., Read Coil Request)
    ModbusMessage(1, 0x01, [1, 2, 3, 4]),
    # Variable payload, 0 fixed bytes + len (e.g., Read Holding Register Repsonse)
    ModbusMessage(2, 0x03, [8, 1, 2, 3, 4, 5, 6, 7, 8]),
    # Empty payload (e.g., Report Slave ID Request)
    ModbusMessage(3, 0x11),
    # Variable payload, 4 fixed bytes + len (e.g., Preset Multiple Registers Request)
    ModbusMessage(4, 0x10, [1, 2, 3, 4, 16, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
    # Fixed 1-byte payload (e.g., Read Exception Status Response)
    ModbusMessage(5, 0x07, [0xDD]),
    # Fixed 2-byte payload (e.g., Read FIFO Queue Request)
    ModbusMessage(6, 0x18, [0xAA]),
    # Fixed 3-byte payload (e.g., Diagnostics Request)
    ModbusMessage(7, 0x08, [0, 0, 0]),
    # Fixed 6-byte payload (e.g., Mask Write Register Request)
    ModbusMessage(8, 0x16, [10, 11, 12, 13, 14, 15]),
    # Variable payload, 8 fixed bytes + len (e.g., Read/Write Multiple Registers (0x17) Request)
    ModbusMessage(4, 0x17, [1, 2, 3, 4, 5, 6, 7, 8, 8, 0xA1, 0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8])
]

def msgtest_send(port, baudrate, mode, count, delay, randomize):
    print('Running message test send on {} @ {} {}, count={}, delay={}'.format(port, baudrate, 'RTU' if mode else 'ASCII', count, delay))
    s = serial.Serial(port, baudrate)
    random.seed()
    for i in range(count):
        n = random.randint(0, len(test_messages) - 1)
        msg = test_messages[n]
        frame = msg.rtu_frame() if mode > 0 else msg.ascii_frame()
        s.write(frame)
        if randomize:
            time.sleep(random.uniform(0, delay))
        else:
            time.sleep(delay)
        if i % 100 == 0:
            print('...Sent {} messages'.format(i))
    print('Test complete, sent {} messages.'.format(count))

def msgtest_receive(port, baudrate, mode, timeout):
    global msgcount
    print('Running message test receive on {} @ {} {}, timeout={}'.format(port, baudrate, 'RTU' if mode else 'ASCII', timeout))
    msgcount = 0
    modbus_trace_start(port, baudrate, mode, count_msg, msg_timeout=timeout)
    print('Test complete, received {} messages.'.format(msgcount))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', help='Port (e.g., /dev/ttyS2)')
    parser.add_argument('baudrate', help='Baud rate (e.g., 115200)')
    parser.add_argument('mode', type=int, help='Modbus mode, 0 = ASCII, 1 = RTU')
    parser.add_argument('--send', action='store_true', help='Send mode (otherwise receive mode)')
    parser.add_argument('--count', type=int, default=1000, help='Message count (for transmit)')
    parser.add_argument('--delay', type=float, default=1, help='Inter-message delay (for transmit)')
    parser.add_argument('--randomize', action='store_true', help='Randomize message delay')
    parser.add_argument('--timeout', type=int, default=30, help='Message timeout to end (for receive)')
    args = parser.parse_args()
    if args.send:
        msgtest_send(args.port, args.baudrate, args.mode, args.count, args.delay, args.randomize)
    else:
        msgtest_receive(args.port, args.baudrate, args.mode, args.timeout)
    
if __name__ == "__main__":
    main()
    

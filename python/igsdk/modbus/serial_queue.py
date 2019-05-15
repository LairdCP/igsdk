#
# serial_queue.py
#
from serial import Serial, SerialException
from serial.rs485 import RS485Settings

import select
import time
import os
import errno
import termios
import threading
import logging
from ..device import device_init, device_deinit, device_enabled, device_activity, set_serial_port_type, set_serial_termination

import sys
PYTHON3 = sys.version_info >= (3, 0)
if PYTHON3:
    import queue as Queue
else:
    import Queue

class SerialTimeoutFix(Serial):
    """This class provides an improvement on the Serial class timeout logic.

    The standard pySerial class Serial implementation (on Linux/Posix) provides
    some capabilties for timeouts, but due to some implementation problems and
    problems with the underlying serial driver implementation, it is not useful
    for Modbus RTU communication (which requires strict timing to delimit frames).

    PySerial's Serial class enables the user of an 'inter_byte_timeout' parameter
    which is used in the 'read()' implementation; however, read() still attempts
    to fill the requested buffer size (which kind of defeats the use of the
    inter-char timeout).  Further, the Linux driver inter-char timeout is only
    measured in 0.1 sec increments, and can only be set up to 255 characters.
   
    This class emulates the inter-char timeout using select(), which approximates
    the same behavior.  On a read() call, the 'timeout' value is used for the
    initial select(), followed by the 'inter_char_timeout' (for all subsequent
    reads).  read() returns when either the buffer is filled or the initial or
    inter-byte timeout occurs.
    """

    def _reconfigure_port(self, force_update=False):
        super(SerialTimeoutFix, self)._reconfigure_port(force_update)
        # Reset VMIN, VTIME to 0 (always)
        iflag, oflag, cflag, lflag, ispeed, ospeed, cc = termios.tcgetattr(self.fd)
        cc[termios.VMIN] = 0
        cc[termios.VTIME] = 0
        termios.tcsetattr(self.fd, termios.TCSANOW, [iflag, oflag, cflag, lflag, ispeed, ospeed, cc])        

    def read(self, size=1):
        """\
        Read size bytes from the serial port. If 'timeout' or 'inter_byte_timeout' is set it may
        return less characters as requested. With no timeout it will block
        until the requested number of bytes is read.
        """
        if not self.is_open:
            raise SerialException(portNotOpenError)
        read = bytearray()
        timeout = self._timeout
        while len(read) < size:
            try:
                start_time = time.time()
                ready, _, _ = select.select([self.fd, self.pipe_abort_read_r], [], [], timeout)
                if self.pipe_abort_read_r in ready:
                    os.read(self.pipe_abort_read_r, 1000)
                    break
                # If select was used with a timeout, and the timeout occurs, it
                # returns with empty lists -> thus abort read operation.
                # For timeout == 0 (non-blocking operation) also abort when
                # there is nothing to read.
                if not ready:
                    break   # timeout
                buf = os.read(self.fd, size - len(read))
                # read should always return some data as select reported it was
                # ready to read when we get to this point.
                if not buf:
                    # Disconnected devices, at least on Linux, show the
                    # behavior that they are always ready to read immediately
                    # but reading returns nothing.
                    raise SerialException(
                        'device reports readiness to read but returned no data '
                        '(device disconnected or multiple access on port?)')
                read.extend(buf)
            except OSError as e:
                # this is for Python 3.x where select.error is a subclass of
                # OSError ignore EAGAIN errors. all other errors are shown
                if e.errno != errno.EAGAIN and e.errno != errno.EINTR:
                    raise SerialException('read failed: {}'.format(e))
            except select.error as e:
                # this is for Python 2.x
                # ignore EAGAIN errors. all other errors are shown
                # see also http://www.python.org/dev/peps/pep-3151/#select
                if e[0] != errno.EAGAIN:
                    raise SerialException('read failed: {}'.format(e))
            if self._inter_byte_timeout is not None:
                # Use byte timeout for remaining reads
                timeout = self._inter_byte_timeout
            elif timeout is not None:
                timeout -= time.time() - start_time
                if timeout <= 0:
                    break
        return bytes(read)
        
class SerialQueue(threading.Thread):
    """A serial queue that uses threads to manage serial data
    
    SerialQueue provides a high-level class that manages continuously
    reading data from a serial port in an IO-bound thread, while returning
    data to a calling thread.  The received data is framed by timeouts, and
    stored as byte strings in a queue.
    """
    def __init__(self, port, baudrate, serial_mode=0, serial_term=0, timeout=None, inter_byte_timeout=0.1, read_buf_size=1024, max_queue_size=256):
        self.serial = SerialTimeoutFix(port=port, baudrate=baudrate, timeout=timeout, inter_byte_timeout=inter_byte_timeout)
        self.queue = Queue.Queue(maxsize=max_queue_size)
        self.read_buf_size = read_buf_size
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.device = device_init()
        device_enabled(self.device)
        self.logger.info('Creating SerialQueue(): port={}, baudrate={}, serial_mode={}, timeout={}, inter_byte_timeout={}, bufsize={}, max_queue={}'.format(port, baudrate, serial_mode, timeout, inter_byte_timeout, read_buf_size, max_queue_size))
        # Disable termination temporarily to prevent error on setting mode
        set_serial_termination(self.device, 0)
        set_serial_port_type(self.device, serial_mode)
        set_serial_termination(self.device, serial_term)
        if serial_mode == 0: # RS-232 (disable RS-485)
            self.serial.rs485_mode = None
        elif serial_mode == 1: # RS-485 Half Duplex (assert RTS on Tx only)
            # Note - Bug in pySerial 3.1.0 -> set delays to '0' to avoid exception
            self.serial.rs485_mode = RS485Settings(rts_level_for_tx=True, rts_level_for_rx=False, delay_before_tx=0, delay_before_rx=0)
        elif serial_mode == 2: # RS-485 Full Duplex (assert RTS always)
            # Note - Bug in pySerial 3.1.0 -> set delays to '0' to avoid exception
            self.serial.rs485_mode = RS485Settings(rts_level_for_tx=True, rts_level_for_rx=True, delay_before_tx=0, delay_before_rx=0)
        threading.Thread.__init__(self)

    def run(self):
        """The method that is run in the thread context; here we collect serial data (separated by timeouts) and place them on the queue.
        """
        while self.running:
            b = self.serial.read(self.read_buf_size)
            if b and len(b) > 0:
                self.queue.put_nowait(b) # NOTE: Can raise Queue.Full
                device_activity(self.device)

    def receive_start(self):
        """Start receiving data packets.
        """
        self.logger.info('Starting serial queue thread.')
        self.running = True
        self.start()
        
    def receive_stop(self):
        """Stop receiving data packets.
        """
        self.logger.info('Stopping serial queue thread.')
        self.running = False
        self.serial.cancel_read()
        self.queue.put_nowait(None)
        device_deinit(self.device)
        
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

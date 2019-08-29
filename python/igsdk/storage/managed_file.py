#
# managed_file.py
#
# This module implements the API for a managed file (handles
# writing to internal vs. external storage, limited file size,
# and sequenced filenames.)
#
from ..device import device_init, device_deinit, get_int_storage_path, get_ext_storage_available, get_storage_status, EXT_STORAGE_AVAILABLE
import threading
import datetime
import os
import os.path
import shutil
import logging

MANAGED_FILE_MAX_SIZE_DEFAULT = (64 * 1024 * 1024) # 64 MB

class FileMover(threading.Thread):
    def __init__(self, srcpath, dstpath):
        self.logger = logging.getLogger(__name__)
        self.srcpath = srcpath
        self.dstpath = dstpath
        super(FileMover, self).__init__()

    def run(self):
        self.logger.info('Moving files from {} to {}'.format(self.srcpath, self.dstpath))
        for fname in os.listdir(self.srcpath):
            srcname = self.srcpath + '/' + fname
            if os.path.isfile(srcname):
                dstname = self.dstpath + '/' + fname
                self.logger.info('Moving {} -> {}'.format(srcname, dstname))
                shutil.move(srcname, self.dstpath + '/' + fname)
        self.logger.info('File move complete.')

class ManagedFile():
    """
    Managed file class

    Manages writing to storage files, on either external media (SD card)
    or internal storage, handles swapping operation by copying
    files to external storage when available, and limits file
    size by writing to a sequence of files.
    """
    def __init__(self, unit, basename, suffix, maxsize):
        self.logger = logging.getLogger(__name__)
        self.device = device_init(self.cb_ext_storage_available)
        self.int_storage_path = get_int_storage_path(self.device)
        self.ext_storage_available, self.ext_storage_path = get_ext_storage_available(self.device)
        self.flock = threading.RLock()
        self.file = None
        self.filename = None
        self.unit = unit
        self.basename = basename
        self.suffix = suffix
        self.maxsize = maxsize
        self.basepath = None
        self.filemover = None
        self.start_file()

    def deinit(self):
        with self.flock:
            if self.file and not self.file.closed:
                self.file.close()
                self.file = None
        device_deinit(self.device)

    def cb_ext_storage_available(self, ext_storage_available, ext_storage_path):
        """Callback indicating change in external storage availability
        """
        with self.flock:
            if ext_storage_available != self.ext_storage_available:
                self.ext_storage_available = ext_storage_available
                self.ext_storage_path = ext_storage_path
                # Open a new file based on the storage availabillity
                self.start_file()
                if self.ext_storage_available == EXT_STORAGE_AVAILABLE:
                    # Create thread to move files to external storage
                    self.filemover = FileMover(self.int_storage_path + '/' + self.unit,
                        self.ext_storage_path + '/' + self.unit)
                    self.filemover.start()

    def start_file(self):
        with self.flock:
            # Close current file
            if self.file and not self.file.closed:
                self.file.close()
                self.file = None
            # Create path to file if necessary
            if self.ext_storage_available == EXT_STORAGE_AVAILABLE:
                self.basepath = self.ext_storage_path + '/' + self.unit
            else:
                self.basepath = self.int_storage_path + '/' + self.unit
            if not os.path.exists(self.basepath):
                os.makedirs(self.basepath)
            # Create unique filename
            self.filename = '{}/{}-{:%Y%m%d%H%M%S}{}'.format(self.basepath,
                self.basename, datetime.datetime.today(), self.suffix or '')
            self.logger.info('Creating file {}'.format(self.filename))
            self.file = open(self.filename, 'wb')

    def write(self, data):
        with self.flock:
            # Open a new file if this write will exceed the max size
            if self.file.tell() + len(data) > self.maxsize:
                self.start_file()
            self.file.write(data)

    def get_storage_status(self):
        return get_storage_status(self.device)

def managed_file_init(unit, basename, suffix, maxsize = MANAGED_FILE_MAX_SIZE_DEFAULT):
    """Initializes a managed file for storage.
    """
    return ManagedFile(unit, basename, suffix, maxsize)

def managed_file_deinit(f):
    if f:
        f.deinit()

def managed_file_write(f, data):
    """Writes data to a managed file.
    """
    if f:
        f.write(data)

def get_storage_status(f):
    """Gets the storage status
    """
    if f:
        return f.get_storage_status()

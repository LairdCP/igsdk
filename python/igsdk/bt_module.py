#
# bt_module.py
#
# Bluetooth API for Laird Sentrius IG devices
#

import dbus
import dbus.exceptions
import threading
import dbus.mainloop.glib
import logging
import sys
import json

PYTHON3 = sys.version_info >= (3, 0)
if PYTHON3:
    from gi.repository import GObject as gobject
    from gi.repository import GLib as glib
else:
    import gobject

BT_OBJ='org.bluez'
BT_OBJ_PATH='/org/bluez/hci0'
BT_ADAPTER_IFACE='org.bluez.Adapter1'
BT_DEVICE_IFACE='org.bluez.Device1'
DBUS_OBJ_MGR_IFACE = 'org.freedesktop.DBus.ObjectManager'
DBUS_PROP_IFACE = 'org.freedesktop.DBus.Properties'

class BtMgr(threading.Thread):
    """Class that encapsulates the bluetooth API functionality
    """
    def __init__(self, discovery_callback):
        self.logger = logging.getLogger(__name__)
        self.logger.info('Initalizing BtMgr')
        
        self.device_signal = None

        # Set up DBus loop
        self.loop = None
        dbus.mainloop.glib.threads_init()
        dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
        if PYTHON3:
            self.loop = glib.MainLoop()
        else:
            self.loop = gobject.MainLoop()
            gobject.threads_init()
            
        # Get DBus objects
        self.manager = dbus.Interface(dbus.SystemBus().get_object(BT_OBJ, 
            "/"), DBUS_OBJ_MGR_IFACE)
        self.adapter = dbus.Interface(dbus.SystemBus().get_object(BT_OBJ,
            BT_OBJ_PATH), BT_ADAPTER_IFACE)
        self.adapter_props = dbus.Interface(dbus.SystemBus().get_object(BT_OBJ,
            BT_OBJ_PATH), DBUS_PROP_IFACE)
            
        # Register signal handlers
        self.manager.connect_to_signal('InterfacesAdded', discovery_callback)
        super(BtMgr, self).__init__()
        
        # Power on the bluetooth module
        self.adapter_props.Set(BT_ADAPTER_IFACE, "Powered", dbus.Boolean(1))
        
        # Run main loop
        self.start()
    
    def run(self):
        """Method to run the DBus main loop (on a thread)
        """
        self.logger.info('Starting main loop.')
        self.loop.run()
        self.logger.info('Main loop has exited.')

    def quit_loop(self):
        if self.loop:
            self.loop.quit()

    def deinit(self):
        # Schedule call to stop DBus loop
        if self.loop:
            gobject.timeout_add(0, self.quit_loop)
    
    def StartDiscovery(self):
        """Activate bluetooth discovery of peripherals
        """
        self.logger.info('Starting Discovery')
        self.adapter.StartDiscovery()
    
    def StopDiscovery(self):
        """Deactivate bluetooth discovery of peripherals
        """
        self.logger.info('Stopping Discovery')
        self.adapter.StopDiscovery()
    
    def FindDevice(self, address):
        """Find the device matching the passed in address
        
        Returns:
            The path to the device
        """
        objects = self.manager.GetManagedObjects()
        for path, interfaces in objects.items():
            if path.startswith(self.adapter.object_path):
                device = interfaces.get(BT_DEVICE_IFACE)
                if device and str(device['Address']) == address:
                    return path
        return None
    
    def Connect(self, address):
        """Connect to the bluetooth device at the designated address
        
        Returns:
            True if connected successfully; false otherwise
        """
        success = False
        self.logger.info('Connecting to {}'.format(address))
        
        try:
            device_path = self.FindDevice(address)
            if device_path:
                device = dbus.Interface(dbus.SystemBus().get_object(BT_OBJ, 
                    device_path), BT_DEVICE_IFACE)
                device.Connect()
                success = True
        except dbus.exceptions.DBusException as e:
            self.logger.error('Failed to connect device {}: {}'.format(address, e))
            
        return success
    
    def Disconnect(self, address):
        """Disconnect from the bluetooth device at the designated address
        
        Returns:
            True if disconnected successfully; false otherwise
        """
        success = False
        self.logger.info('Disconnecting from {}'.format(address))
        
        try:
            device_path = self.FindDevice(address)
            if device_path:
                device = dbus.Interface(dbus.SystemBus().get_object(BT_OBJ, 
                    device_path), BT_DEVICE_IFACE)
                device.Disconnect()
                success = True
        except dbus.exceptions.DBusException as e:
            self.logger.error('Failed to disconnect device {}: {}'.format(address, e))
            
        return success
    
    def DeviceStatus(self, address):
        """Return the properties of a device at the given address
        
        Returns:
            The device properties/status (in JSON)
        """
        status = {}
        status_json = {}
        self.logger.info('Retrieving status for {}'.format(address))
        
        try:
            device_path = self.FindDevice(address)
            if device_path:
                device_props = dbus.Interface(dbus.SystemBus().get_object(BT_OBJ, 
                    device_path), DBUS_PROP_IFACE)
                
                # Loop through the properties and save them off
                properties = device_props.GetAll(BT_DEVICE_IFACE)
                for property in properties:
                    status[property] = properties[property]
                status_json = json.dumps(status, separators=(',',':'), sort_keys=True, indent=4)
        except exceptions.UnicodeDecodeError as e:
            self.logger.error('Failed to get device status for device {}: {}'.format(address, e))
        
        return status_json

def bt_init(discovery_callback = None):
    """Initialize the IG bluetooth API
    Returns:
        Device instance, to be used in bt_* calls
    """
    try:
        bt = BtMgr(discovery_callback)
        return bt
    except dbus.exceptions.DBusException as e:
        logging.getLogger(__name__).error('Cannot open BT interface: {}'.format(e))
        return None

def bt_deinit(bt):
    """De-initialize the IG bluetooth API
    """
    if bt:
        bt.deinit()

def bt_start_discovery(bt):
    """Activate bluetooth discovery of peripherals
    """
    if bt:
        bt.StartDiscovery()

def bt_stop_discovery(bt):
    """Deactivate bluetooth discovery of peripherals
    """
    if bt:
        bt.StopDiscovery()

def bt_connect(bt, address):
    """Connect to the bluetooth device at the designated address
        
    Returns:
        True if connected successfully; false otherwise
    """
    if bt:
        return bt.Connect(address)

def bt_disconnect(bt, address):
    """Disconnect from the bluetooth device at the designated address
        
    Returns:
        True if disconnected successfully; false otherwise
    """
    if bt:
        return bt.Disconnect(address)

def bt_device_status(bt, address):
    """Return the properties of a device at the given address
        
    Returns:
        The device properties/status (in JSON)
    """
    if bt:
        return bt.DeviceStatus(address)
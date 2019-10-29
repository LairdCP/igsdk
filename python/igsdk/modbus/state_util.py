#
# state_util.py
#
# Utility functions for handling Modbus state
#

import copy
import logging

def get_state_element(state, addr, req_len):
    """Get the array containing a given address and length.
    
    Args:
    
        state: The top-level state variable
        addr: Starting address (int)
        req_len: Requested length (int)
    
    Returns:
    
        A tuple of the array containing the requested address, as:
            (address, array, offset)
        
        The array will be empty if the requested address and/or length is
        not contained in the state.
    """
    for a in state:
        a_int = int(a, 16)
        el = state.get(a)
        if el and addr >= a_int and addr < a_int + len(el) and addr + req_len <= a_int + len(el):
            logging.getLogger(__name__).debug('Found element for address {}, len {}'.format(addr, req_len))
            return a, el, addr - a_int
    logging.getLogger(__name__).debug('Element for address {}, len {} not found'.format(addr, req_len))
    return '', [], 0

def read_state(state, addr, req_len):
    """Read an element in the device state as an array.
    
    Args:
    
        state: The top-level state variable
        addr: Starting address (int)
        req_len: Requested length (int)

    Returns:
    
        An array containing the requested values, or an empty
        array if the requested address and/or length is not
        contained in the state.
    """
    addr, el, offset = get_state_element(state, addr, req_len)
    if el and len(el) > 0:
        return el[offset:offset+req_len]
    return []

def read_registers(state, addr, req_len):
    """Read registers from the state as a Modbus response data payload.

    Args:
    
        state: The top-level state variable
        addr: Starting address (int)
        req_len: Requested length (int)

    Returns:

        The complete Modbus data payload for a register read response,
        including the byte length, or an empty array if the requested
        address and/or length is not contained in the state.
        
    """
    b = []
    regs = read_state(state, addr, req_len)
    if regs and len(regs) > 0:
        # Convert 16-bit register values to MSB-encoded bytes
        for i in regs:
            b.append(i >> 8)
            b.append(i % 256)
        # Prepend byte count
        bytelen = len(b)
        b.insert(0, bytelen & 0xFF)
    return b

def read_bits(state, addr, req_len):
    """Read bits from the device state as a Modbus response data payload.

    Args:
    
        state: The top-level state variable
        addr: Starting address (int)
        req_len: Requested length (int)

    Returns:

        The complete Modbus data payload for a bit-encoded read response,
        including the byte length, or an empty array if the requested
        address and/or length is not contained in the state.
    """
    b = []
    curbit = 0
    byteval = 0
    bits = read_state(state, addr, req_len)
    if bits and len(bits) > 0:
        # Pack array of values into 8-bit bytes
        for bit in bits:
            if bit > 0:
                byteval |= (1 << curbit)
            curbit = curbit + 1
            if curbit >= 8:
                b.append(byteval)
                byteval = 0
                curbit = 0
        # Add remaining bits, if any
        if curbit > 0:
            b.append(byteval)
        # Prepend byte count
        bytelen = len(b)
        b.insert(0, bytelen & 0xFF)
    return b
    
def write_registers(state, addr, new_data):
    """Write new register values from an array
    
    Args:
    
        state: The top-level state variable
        addr: Starting address (int)
        new_data: Array of new values, encoded per Modbus protocol
                  of 2 MSB bytes per register
        
    Returns:
    
        A dictionary containing the delta of changes that
        should be applied to the state, or None if the
        state does not contain the specified element.
        
    """
    addr, el, offset = get_state_element(state, addr, len(new_data) / 2)
    if el and len(el) > 0:
        new_values = []
        for i in range(0, len(new_data), 2):
            new_values.append(256*new_data[i] + new_data[i+1])
        new_el = copy.deepcopy(el)
        new_el[offset:offset+len(new_values)] = new_values
        delta = {addr: new_el}
        return delta

def mask_write_register(state, addr, and_mask, or_mask):
    """Mask write a single register
    
    Args:
    
        state: The top-level state variable
        addr: Starting address (int)
        and_mask: Byte array containing MSB-encoded AND mask value
        or_mask: Byte array containing MSB-encoded OR mask value
        
    Returns:
    
        A dictionary containing the delta of changes that
        should be applied to the state, or None if the
        state does not contain the specified element.
        
    """
    addr, el, offset = get_state_element(state, addr, 1)
    if el and len(el) > 0:
        and_mask_val = and_mask[0] * 256 + and_mask[1]
        or_mask_val = or_mask[0] * 256 + or_mask[1]
        new_value = (el[offset] & and_mask_val) | (or_mask_val & ~and_mask_val)
        new_el = copy.deepcopy(el)
        new_el[offset] = new_value
        delta = {addr: new_el}
        return delta
    
def write_bits(state, addr, new_data, nbits):
    """Write new bit values from a packed array
    
    Args:
    
        state: The top-level state variable
        addr: Starting address (int)
        new_data: Array of new bit values encoded into bytes per the
                  Modbus protocol (packed bits)
        nbits: Number of bits to write
        
    Returns:
    
        A dictionary containing the delta of changes that
        should be applied to the state, or None if the
        state does not contain the specified element.
        
    """
    addr, el, offset = get_state_element(state, addr, nbits)
    if el and len(el) > 0:
        new_el = copy.deepcopy(el)
        curbit = 0
        for i in range(offset, offset + nbits):
            new_el[i] = (new_data[curbit / 8] >> (curbit % 8)) & 0x01
            curbit = curbit + 1
        delta = {addr: new_el}
        return delta

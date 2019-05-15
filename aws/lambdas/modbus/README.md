# Modbus Lambda Functions
This folder contains the pre-configured Greengrass Lambda functions for Modbus communication.

## Modbus Lambda - Common Requirements
All of the Lambda functions described below have the following common requirements and characteristics.

### Framing and Checksum
The Modbus Lambda functions can send and receive either Modbus RTU (binary) or Modbus ASCII frames.  This is configured using enviroment variables during deployment.

The Modbus Lambda functions will verify the checksum (CRC for Modbus RTU, or LRC for Modbus ASCII).  Only frames with a valid checksum will be forwarded to the IoT server.  Frames with invalid checksums will be silently discarded.

### JSON Message Format
All Modbus messages that are handled by the Modbus Lambda functions are translated to and from JSON, in a common format.  The JSON message format will have required and optional elements, depending on the requirements of the Lambda function.

All messages **must** contain an `address` element, which is an unsigned integer that represents the 8-bit Modbus slave address.

All messages **must** contain a `function` element, which is an unsigned integer that represents the 8-bit Modbus function code.

Messages **may** contain a `data` element, which is an array of unsigned integers that represent the Modbus data payload.  Messages that do not contain a data payload can omit this element.

An example of a JSON message representing a single Modbus message is as follows:

    {
       "address" : 16,
       "function" : 3,
       "data" : [ 0, 107, 0, 3 ]
    }

This represents a Modbus master request to read 3 holding registers, beginning at address 107, from the slave with device ID 16.

**NOTE:** Modbus frames on the serial bus (both ASCII and RTU) contains a count of data bytes; this is not directly encoded in the JSON message, but can be inferred from the `data` element array length.

### Environment Variables
The Modbus Lambda functions have parameters to control their function that are based on environment variables (specified in the Greengrass deployment). There are common variables used by all Lambdas, and some that are specific to the Lambda.

`SERIAL_PORT_DEVICE` specifies the port to use for Modbus serial communication (e.g., '/dev/ttyS2')

`SERIAL_BAUD_RATE` specifies the baud rate (e.g., '9600')

`MODBUS_MODE` specifies the mode (framing), '0' for ASCII and '1' for RTU

`SERIAL_MODE` specifies the hardware mode: '0' for RS-232 (default), '1' for RS-485/422 half duplex, or '2' for RS-485/422 full duplex

`SERIAL_TERM` enables internal termination if set to '1'

## Lambda Functions - Detailed Description

### ModbusTraceLambda.py
The Modbus Trace Lambda function relays Modbus packets from the serial bus into messages into the messaging server inside the Greengrass core.  This is a one-way function; i.e., no data will be sent onto the serial bus.

#### Message Translation
All valid Modbus messages received on the serial port by the Modbus Trace Lambda will be converted to a single JSON object.  In addition to the JSON elements described above, trace messages have a `received` element, which is an unsigned integer that represents the time the message was received, as the number of milliseconds since the Unix epoch (January 1, 1970 00:00:00) relative to the UTC timezone.

#### Message Topics
The Modbus Trace Lambda function will publish the Modbus messages on the following topic:

    modbus/msg/trace/<nodeid>/<address>/<function>

where `nodeid` is the ID of the Greengrass core, `address` and `function` are the corresponding address and function of the Modbus message, represented as an unsinged integer in ASCII.  For example, the message above would be published to the following topic:

    modbus/msg/trace/ggcore1/16/3

### ModbusMasterLambda.py
The Modbus Master Lambda translates each JSON message received into a Modbus request on the serial port.  It awaits a response from the slave, and forwards the response back to the server as a JSON encoded Modbus message.

Slave response messages are required to have the same `address` as the request message, and the `function` must match the least-significant seven (7) bits of the request (so that both valid response and exception frames are forwarded).  Any other frames are ignored up to the timeout.

#### Message Translation
In addition to the JSON elements described above, the Modbus Master Lambda request message from the server **may** contain a `timeout` element, which represents the timeout to await a slave response, in seconds.  Otherwise, the Lambda default of 5 seconds is used.  Response messages have a `received` element, which is an unsigned integer that represents the time the message was received, as the number of milliseconds since the Unix epoch (January 1, 1970 00:00:00) relative to the UTC timezone.

#### Message Topics
The Modbus Master Lambda will handle any message that is received, based on the subscription(s) specified during deployment.  However, it is *recommended* that the subscription be set to the following topic:

    modbus/msg/master/<nodeid>/request

The Modbus Master Lambda will forward Modbus slave response messages on the following topic:

    modbus/msg/master/<nodeid>/response/<address>/<function>

where `address` and `function` are the response address and function code represented as an unsigned integer in ASCII, respectively.  For example, the slave response message above would be published to the topic:

     modbus/msg/master/ggcore1/response/16/3

#### Environment Variables
The following environment variables are specific to the Modbus Master Lambda:

`MODBUS_RESPONSE_TIMEOUT`: The default timeout (in seconds) to await a response from the slave.  This is overridden by the `timeout` element in the request, if specified.

### ModbusSlaveLambda.py
The Modbus Slave Lambda function operates as a Modbus slave on the serial port.  The Modbus Slave Lambda function responds to messages from a Modbus master on the serial port, to requests from a Modbus master to read and write to the slave device.

The Modbus Slave Lambda uses the device shadow document of the Greengrass Core to determine how to respond to queries from the Modbus master.  The device shadow state represents the current state of the Modbus slave device (coils, discrete inputs, holding registers, and input registers).  The Modbus Slave Lambda responds to Modbus request messages based upon this state; likewise, requests to change the slave device's state are reflected in the device shadow.

#### Slave Device Shadow
he Modbus Slave Lambda uses the "desired" section to determine the current state of the slave device.  The "desired" section in the device shadow state contains sub-objects for each type of request from the master to read the state of the slave device: Read Coils, Read Discrete Registers, Read Holding Registers, Read Input Registers.  The Modbus Slave Lambda reports changes to the slave device in the "reported" section of the shadow document, for each type of request from the master to write the state of the slave device: Write Single Coil, Write Single Register, Write Multiple Coils, Write Multiple Registers, Mask Write Register.  (In the Modbus protocol, discrete registers and input registers are read-only, so the "reported" section will only report Coils and Holding Registers).

The "desired" section of the shadow contains the cloud state for a slave device contain sub-objects for each type of data that can be read from the slave device: "coil", "discrete", "holding", and "input". The "reported" section of the shadow contains the device state for each type of data that can be written to the slave device: "coil" and "holding". The key for each object is the starting address as a hexadecimal number, and the values are represented as an array of one or more numbers.

An example of a Modbus Slave device shadow document is as follows:

    {
      "state" : {
        "desired" : {
          "coil" : {
            "0" : [1, 0],
            "800" : [0, 1, 0, 1]
           },
          "discrete" : {
            "0" : [1, 1, 1, 1],
            "a00" : [0, 0]
          },
          "holding" : {
            "0" : [1],
            "b00" : [65535, 0, 65535]
          },
          "input" : {
            "f2" : [10, 11, 12, 13]
          }
        },
        "reported" : {
          "coil" : {
            "0" : [0, 1]
          },
          "holding" : {
            "200" : [10, 20, 30, 40],
            "1e30" : [65535, 0, 65535]
          }
        }
      }
    }

Note that following regarding the device shadow document:

* The hexadecimal address values must be normalized so that no leading   0's appear, and are purely lower case.  For example, `0` and `ef2`   are valid, but `001` and `DE00` are not.
* The Modbus Slave Lambda will only update the `reported` object in   the shadow document (based on the received request to write to the   slave device state).  The `desired` object of the shadow document is  assumed to be controlled by services interacting with the device  shadow via the AWS cloud.
* It is not required that the values in the `desired` and `reported` sections be identical; the cloud services can manipulate the document in any way.
* Overlapping values (multiple elements for a specific data type that have address ranges that overlap) are not supported, and will result in undefined behavior by the Modbus Slave Lambda.
* Values other than "0" or "1" for the `coil` and `discrete` elements are not supported, and will result in undefined behavior by the Modbus Slave Lambda.
* There is no specific limit on the number of each data element, etc., except that the AWS shadow service imposes a limit of 8KB on the ***entire*** shadow document.
* The Modbus Slave Lambda should only update the objects in the `reported` section that have changed; the AWS cloud service will automatically merge the changes into the complete shadow document.
* The Modbus Slave Lambda obtains the entire shadow document once during initialization (using the `get` topic), and obtains any changes from the `documents` topic to determine updates.

#### Slave Device Responses
The Modbus Slave Lambda responds to requests received from a master as follows:

* For all requests:
  * If the checksum/framing of the request is not valid:
    * The Modbus Slave Lambda will ignore the request (no response)

* For ***Read Coils***, ***Read Discrete Registers***, ***Read Holding Registers***, and ***Read Input Registers***:
  * If the requested range of values is completely represented in the `desired` object of the device shadow:
    * The Modbus Slave Lambda will return a normal response containing the requested values from the current shadow values in `desired`
  * If the requested range of values is not completely represented in the `desired` object of the device shadow:
    * The Modbus Slave Lambda will return an exception response to the
      request

* For ***Write Single Coil***, ***Write Single Register***, ***Write Multiple Coils***, ***Write Multiple Registers***, and ***Mask Write Register***:
  * If the requested range of values is completely represented in the `reported` object of the device shadow:
    * The Modbus Slave Lambda will update the specified values in the shadow document to the cloud, and return a normal Modbus response indicating success
  * If the requested range of values is not completely represented in the `reported` object:
    * The Modbus Slave Lambda will return an exception response to the request

* For all other requests:
  * The Modbus Slave Lambda will return an exception response to the request

#### Message Topics
The Modbus Slave Lambda function uses the topics defined for AWS shadow operations to obtain and publish changes to the shadow document. Specifically, the deployment must route messages on the following topics that the Modbus Slave Lambda uses to determine changes to the device shadow:

    $aws/things/<node_id>/shadow/get/accepted
    $aws/things/<node_id>/shadow/update/documents

The Modbus Slave Lambda publishes messages on the following topics, to obtain the initial device shadow, and to publish updates:

    $aws/things/<node_id>/shadow/get
    $aws/things/<node_id>/shadow/update

In these cases, `node_id` is the name of the gateway's Greengrass Core.

While it is possible to configure the deployment to use wildcards (e.g., `#`), this is not recommended practice, since topics can be added later, and extraneous messages will increase service costs.

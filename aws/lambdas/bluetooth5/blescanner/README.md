# Zephyr Ble Scanner

Use this in conjuction with our Zephyr demo application

### Deploy the Ble Scanner Lambda

* Create a ZIP file containing the following:
  * `blescanner.py` from this directory
  * The Greengrass Core SDK directory ["greengrasssdk"](https://github.com/aws/aws-greengrass-core-sdk-python) directory
* Log into your AWS account dashboard
* Enter the AWS Lambda console and create a new Lambda function (e.g., "blescanner") with Python 3.7 as the runtime
* Select "Upload a ZIP file", and upload this ZIP file as the contents of the Lambda
* Publish a new version of the Lambda
* Enter the AWS IoT Greengrass console, and navigate to the "Groups" tab, then select the group you created for your Sentrius IG60
* In the "Lambdas" pane, add your blescanner Lambda (e.g., "blescanner"), then modify the Lambda configuration as follows:
  * Set "Containerization" to "Greengrass container"
  * Set the "Memory Limit" to 32 MB
  * Set the "Timeout" to 60 seconds
  * Set the "Lambda Lifecycle" to "Make this function long-lived"
* Click "Update" to update the Lambda configuration
* In the Lambda details page, select "Resources" to add a resource for the serial port
* Add a local resource for a Device with the path `/dev/ttyS2`, select "Automatically add OS group permissions", and select "Read and write access", then click "Update" to save the resource
* In the "Subscriptions" pane, create two subscriptions:
  * Create a subscription with a "Source" of "IoT Cloud" and "Target" of your Lambda, with a topic of "blescanner/_CORE NAME_/resetList" (where _CORE NAME_ is the name of your core)
  * Create a subscription with a "Source" of your Lambda and "Target" of "IoT Cloud", with a topic of "blescanner/_CORE NAME_/info" (where _CORE NAME_ is the name of your core)
* (Optional) Configure your Greengrass group to perform logging via CloudWatch; refer to the [AWS Documentation on Monitoring with AWS Iot Greengrass Logs](https://docs.aws.amazon.com/greengrass/latest/developerguide/greengrass-logs-overview.html) for details
* Select "Deploy" under "Actions" to deploy the BleScanner Lambda


### Verify End-to-End Messaging with the AWS IoT Cloud
* In the AWS IoT Console, select the "Test" pane
* Enter a subscription topic that corresponds to your device: "blescanner/_CORE NAME_/info" (where _CORE NAME_ is the name of your core).  As messages are published from the peripheral, you should see them appear in the AWS console:

* Publish a message to reset the device list:
  * In the "Publish" topic field, enter the topic that corresponds to your device: "blescanner/_CORE NAME_/resetList" (where _CORE NAME_ is the name of your core)


# AWS Scripts
This folder contains scripts for use with AWS CloudFormation.

### prov_server.json
This script creates a provisioning server for the Sentrius&trade; IG60.

***IMPORTANT***: Please review the pricing and free tier information for the AWS resources that are created, as you may be billed by Amazon for the resources you create using this script.

This script creates the following AWS resources:

* An S3 bucket to contain the provisioning resource files (Greengrass core tarball, provisioning descriptor, and security resources)
* A CloudFront distribution
* A Lambda-at-Edge function to perform basic HTTP authentication
* An IAM role use to execute the Lambda

## Deployment

Use the AWS CloudFormation console to upload this script.  You will be prompted for two parameters, a username and password (static) that will be used for HTTP authentication.  You will need to use these when performing provisioning of the Sentrius&trade; IG60.

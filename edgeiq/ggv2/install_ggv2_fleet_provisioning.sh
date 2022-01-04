#!/bin/sh

#
#
# Install GGv2 onto an Industrial Gateway using fleet provisioning
#
# This script expects to be passed the path to a configuration file which
# will be sourced.
#

SCRIPT_IDENTIFIER_NAME=$(basename "$0")
GGV2_NUCLEUS_LAUNCH_PARAMS_DEFAULTS="-Xmx128m -XX:+UseSerialGC -XX:TieredStopAtLevel=1"

## -------------------------------
## ---------- FUNCTIONS ----------
## -------------------------------

# Print to the systemd journal with a priority of "info"
function print_to_journal_info() {
    echo $1 | systemd-cat --priority="info" -t ${SCRIPT_IDENTIFIER_NAME}
}

# Print to the systemd journal with a priority of "warning"
function print_to_journal_warning() {
    echo $1 | systemd-cat --priority="warning" -t ${SCRIPT_IDENTIFIER_NAME}
}

# Print to the systemd journal with a priority of "err"
function print_to_journal_err() {
    echo $1 | systemd-cat --priority="err" -t ${SCRIPT_IDENTIFIER_NAME}
}

# Verify a given file against a given signature
#
# $1:       target file path
# $2:       target signature
# return:   valid signature
function verify_signature() {
    # TODO: Implement signature verification logic
    return true
}

# Donwload, extract, and then subsequently remove the specified OpenJDk
# tarball containing the necessary OpenJDK dependencies for GGv2
function handle_openjdk_dependencies() {
    # Download OpenJDK tarball file
    print_to_journal_info "Downloading OpenJDK tarball file"
    wget -q ${OPENJDK_FILE_URL} -O ${SDCARD_ROOT}/openjdk-file.tar.gz
    if [ ! $? -eq 0 ]
    then
        print_to_journal_err "ERROR: Unable to download OpenJDK tarball file"
        error_detected=true
        exit 1
    fi

    # Verify OpenJDK tarball file signature
    if [ -z "$OPENJDK_SIGNATURE" ]
    then
        print_to_journal_info "Provided OpenJDK tarball file signature empty, skipping verification"
    else
        print_to_journal_info "Verifying OpenJDK tarball file signature"
        if [ verify_signature ${SDCARD_ROOT}/openjdk-file.tar.gz $OPENJDK_SIGNATURE ]
        then
            print_to_journal_info "OpenJDK tarball file valid"
        else
            print_to_journal_err "ERROR: OpenJDK tarball file invalid!"
            error_detected=true
            exit 1
        fi
    fi

    # Extract OpenJDK tarball file
    print_to_journal_info "Extracting OpenJDK tarball file"
    tar xzf ${SDCARD_ROOT}/openjdk-file.tar.gz -C ${SDCARD_ROOT} --no-same-owner
    if [ ! $? -eq 0 ]
    then
        print_to_journal_err "ERROR: Unable to extract OpenJDK tarball file"
        error_detected=true
        exit 1
    fi

    # Remove OpenJDK tarball file
    print_to_journal_info "Removing OpenJDK tarball file"
    rm ${SDCARD_ROOT}/openjdk-file.tar.gz
}

# Donwload, extract, and then subsequently remove the specified GGv2 Core
# Nucleus zip file
function handle_ggv2_core_nucleus_zip() {
    # Download GGv2 Core Nucleus zip file
    print_to_journal_info "Downloading GGv2 Core Nucleus zip file"
    wget -q ${GGV2_CORE_FILE_URL} -O ${SDCARD_ROOT}/ggv2-core-file.zip
    if [ ! $? -eq 0 ]
    then
        print_to_journal_err "ERROR: Unable to download GGv2 Core Nucleus zip file"
        error_detected=true
        exit 1
    fi

    # Verify GGv2 Core Nucleus zip file signature
    if [ -z "$GGV2_CORE_SIGNATURE" ]
    then
        print_to_journal_info "Provided GGv2 Core Nucleus zip file signature empty, skipping verification"
    else
        print_to_journal_info "Verifying GGv2 Core Nucleus zip file signature"
        if [ verify_signature ${SDCARD_ROOT}/ggv2-core-file.zip $GGV2_CORE_SIGNATURE ]
        then
            print_to_journal_info "GGv2 Core Nucleus zip file valid"
        else
            print_to_journal_err "ERROR: GGv2 Core Nucleus zip file invalid!"
            error_detected=true
            exit 1
        fi
    fi

    # Unzip the GGv2 Core Nucleus zip file
    print_to_journal_info "Unzipping GGv2 Core Nucleus zip file"
    unzip -q ${SDCARD_ROOT}/ggv2-core-file.zip -o -d ${GREENGRASS_CORE_DIR}
    if [ ! $? -eq 0 ]
    then
        print_to_journal_err "ERROR: Unable to unzip GGv2 Core Nucleus zip file"
        error_detected=true
        exit 1
    fi

    # Remove the GGv2 Core Nucleus zip file
    print_to_journal_info "Removing GGv2 Core Nucleus zip file"
    rm ${SDCARD_ROOT}/ggv2-core-file.zip
}

# Donwload the specified root CA cert
function handle_root_ca_cert() {
    # Download Root CA cert
    print_to_journal_info "Downloading root CA cert"
    wget -q ${GGV2_ROOT_CA_CERT_URL} -O ${GREENGRASS_ROOT_DIR}/AmazonRootCA1.pem
    if [ ! $? -eq 0 ]
    then
        print_to_journal_err "ERROR: Unable to download root CA cert"
        error_detected=true
        exit 1
    fi
}

# Donwload the fleet provisioning plugin (.jar)
function handle_fleet_provisioning_plugin() {
    # Download the GGv2 Fleet Provisioning plugin
    print_to_journal_info "Downloading GGv2 Fleet Provisioning plugin"
    wget -q ${FLEET_PROVISIONING_PLUGIN_URL} -O ${FLEET_PROVISIONING_PLUGIN_PATH}
    if [ ! $? -eq 0 ]
    then
        print_to_journal_err "ERROR: Unable to download GGv2 Fleet Provisioning plugin"
        error_detected=true
        exit 1
    fi

    # Verify GGv2 Fleet Provisioning plugin signature
    if [ -z "$FLEET_PROVISIONING_PLUGIN_SIGNATURE" ]
    then
        print_to_journal_info "Provided GGv2 Fleet Provisioning plugin signature empty, skipping verification"
    else
        print_to_journal_info "Verifying GGv2 Fleet Provisioning plugin signature"
        if [ verify_signature ${FLEET_PROVISIONING_PLUGIN_PATH} $FLEET_PROVISIONING_PLUGIN_SIGNATURE ]
        then
            print_to_journal_info "GGv2 Fleet Provisioning plugin valid"
        else
            print_to_journal_err "ERROR: GGv2 Fleet Provisioning plugin invalid!"
            error_detected=true
            exit 1
        fi
    fi
}

# Generate the config.yaml file that is passed to the GGv2 setup
function generate_config_yaml() {
    print_to_journal_info "Generating GGv2 initial configuration file"

    CONFIG_YAML=${SDCARD_ROOT}/config.yaml
    echo -e "---" > ${CONFIG_YAML}

    # System section
    echo -e "system:" >> ${CONFIG_YAML}
    echo -e "   certificateFilePath: \"${SYSTEM_CERTIFICATE_FILE_PATH}\"" >> ${CONFIG_YAML}
    echo -e "   privateKeyPath: \"${SYSTEM_PRIVATE_KEY_PATH}\"" >> ${CONFIG_YAML}
    echo -e "   rootCaPath: \"${SYSTEM_ROOT_CA_PATH}\"" >> ${CONFIG_YAML}
    echo -e "   rootPath: \"${SYSTEM_ROOT_PATH}\"" >> ${CONFIG_YAML}

    # Services section
    echo -e "services:" >> ${CONFIG_YAML}

    ## AWS Greengrass Nucleus subsection
    echo -e "   aws.greengrass.Nucleus:" >> ${CONFIG_YAML}
    echo -e "      version: \"${SERVICES_AWS_GREENGRASS_NUCLEUS_VERSION}\"" >> ${CONFIG_YAML}

    ### AWS Greengrass Nucleus configuration sub-sub-section
    echo -e "      configuration:" >> ${CONFIG_YAML}
    echo -e "         awsRegion: \"${SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_AWS_REGION}\"" >> ${CONFIG_YAML}
    echo -e "         iotCredEndpoint: \"${SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_IOT_CRED_ENDPOINT}\"" >> ${CONFIG_YAML}

    ## AWS Greengrass Fleet Provisioning By Claim subsection
    echo -e "   aws.greengrass.FleetProvisioningByClaim:" >> ${CONFIG_YAML}

    ### AWS Greengrass Fleet Provisioning By Claim configuration sub-sub-section
    echo -e "      configuration:" >> ${CONFIG_YAML}
    echo -e "         rootPath: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_ROOT_PATH}\"" >> ${CONFIG_YAML}
    echo -e "         awsRegion: \"${SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_AWS_REGION}\"" >> ${CONFIG_YAML}
    echo -e "         iotRoleAlias: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_ROLE_ALIAS}\"" >> ${CONFIG_YAML}
    echo -e "         iotDataEndpoint: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_DATA_ENDPOINT}\"" >> ${CONFIG_YAML}
    echo -e "         iotCredendtialEndpoint: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_CREDENTIAL_ENDPOINT}\"" >> ${CONFIG_YAML}
    echo -e "         provisioningTemplate: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_PROVISIONING_TEMPLATE}\"" >> ${CONFIG_YAML}
    echo -e "         claimCertificatePath: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_CLAIM_CERTIFICATE_PATH}\"" >> ${CONFIG_YAML}
    echo -e "         claimCertificatePrivateKeyPath: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_CLAIM_CERTIFICATE_PRIVATE_KEY}\"" >> ${CONFIG_YAML}
    echo -e "         rootCaPath: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_ROOT_CA_PATH}\"" >> ${CONFIG_YAML}

    #### AWS Greengrass Fleet Provisioning By Claim configuration template parameters sub-sub-sub-section
    echo -e "         templateParameters:" >> ${CONFIG_YAML}
    if [ -z "$SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_NAME" ]
    then
        # Thing name is blank, so use "IG60_" plus the MAC address instead (without ':' as
        # AWS GGv2 does not accept them in thing names)
        THING_NAME=$(cat /sys/class/net/wlan0/address | awk '{ gsub(":",""); print "IG60_" toupper($0) }')
        print_to_journal_info "Thing name is blank, using '${THING_NAME}' instead"
        echo -e "             ThingName: \"${THING_NAME}\"" >> ${CONFIG_YAML}
    else
        # Thing name isn't blank, so use the provided name
        echo -e "             ThingName: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_NAME}\"" >> ${CONFIG_YAML}
    fi
    echo -e "             ThingGroupName: \"${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_GROUP_NAME}\"" >> ${CONFIG_YAML}
}

## -------------------------------
## --------- MAIN SCRIPT ---------
## -------------------------------

print_to_journal_info "Beginning GGv2 installation"

# Link in the FS key
keyctl link @us @s

# Check for the presence of a uSD card
# TODO: Make sure the uSD card is large enough
if [ ! -b "/dev/mmcblk0" ]
then
    print_to_journal_err "ERROR: Could not find SD card"
    exit 1
fi

SDCARD_ROOT="/var/media/mmcblk0p1"

# Pull in the configuration file via 'source'. We are expecting the following
# settings to be present in the configuration file:
# - GGV2_CORE_FILE_URL
# - GGV2_CORE_SIGNATURE
# - GGV2_RESOURCE_FILE
# - GGV2_ROOT_CA_CERT_URL
# - GGV2_NUCLEUS_LAUNCH_PARAMS
# - OPENJDK_FILE_URL
# - OPENJDK_SIGNATURE
# - FLEET_PROVISIONING_PLUGIN_URL
# - FLEET_PROVISIONING_PLUGIN_SIGNATURE
# - SYSTEM_CERTIFICATE_FILE_PATH
# - SYSTEM_PRIVATE_KEY_PATH
# - SYSTEM_ROOT_CA_PATH
# - SYSTEM_ROOT_PATH
# - SERVICES_AWS_GREENGRASS_NUCLEUS_VERSION
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_ROOT_PATH
# - SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_AWS_REGION
# - SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_IOT_CRED_ENDPOINT
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_ROLE_ALIAS
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_DATA_ENDPOINT
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_CREDENTIAL_ENDPOINT
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_PROVISIONING_TEMPLATE
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_CLAIM_CERTIFICATE_PATH
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_CLAIM_CERTIFICATE_PRIVATE_KEY
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_ROOT_CA_PATH
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_NAME
# - SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_GROUP_NAME
print_to_journal_info "Reading in configuration parameters from $1"
source $1

# Print out the configuration parameters we just sourced
print_to_journal_info "GGV2_CORE_FILE_URL: ${GGV2_CORE_FILE_URL}"
print_to_journal_info "GGV2_CORE_SIGNATURE: ${GGV2_CORE_SIGNATURE}"
print_to_journal_info "GGV2_RESOURCE_FILE: ${GGV2_RESOURCE_FILE}"
print_to_journal_info "GGV2_ROOT_CA_CERT_URL: ${GGV2_ROOT_CA_CERT_URL}"
print_to_journal_info "GGV2_NUCLEUS_LAUNCH_PARAMS: ${GGV2_NUCLEUS_LAUNCH_PARAMS}"
print_to_journal_info "OPENJDK_FILE_URL: ${OPENJDK_FILE_URL}"
print_to_journal_info "OPENJDK_SIGNATURE: ${OPENJDK_SIGNATURE}"
print_to_journal_info "FLEET_PROVISIONING_PLUGIN_URL: ${FLEET_PROVISIONING_PLUGIN_URL}"
print_to_journal_info "FLEET_PROVISIONING_PLUGIN_SIGNATURE: ${FLEET_PROVISIONING_PLUGIN_SIGNATURE}"
print_to_journal_info "SYSTEM_CERTIFICATE_FILE_PATH: ${SYSTEM_CERTIFICATE_FILE_PATH}"
print_to_journal_info "SYSTEM_PRIVATE_KEY_PATH: ${SYSTEM_PRIVATE_KEY_PATH}"
print_to_journal_info "SYSTEM_ROOT_CA_PATH: ${SYSTEM_ROOT_CA_PATH}"
print_to_journal_info "SYSTEM_ROOT_PATH: ${SYSTEM_ROOT_PATH}"
print_to_journal_info "SERVICES_AWS_GREENGRASS_NUCLEUS_VERSION: ${SERVICES_AWS_GREENGRASS_NUCLEUS_VERSION}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_ROOT_PATH: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_ROOT_PATH}"
print_to_journal_info "SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_AWS_REGION: ${SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_AWS_REGION}"
print_to_journal_info "SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_IOT_CRED_ENDPOINT: ${SERVICES_AWS_GREENGRASS_NUCLEUS_CONFIGURATION_IOT_CRED_ENDPOINT}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_ROLE_ALIAS: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_ROLE_ALIAS}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_DATA_ENDPOINT: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_DATA_ENDPOINT}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_CREDENTIAL_ENDPOINT: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_IOT_CREDENTIAL_ENDPOINT}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_PROVISIONING_TEMPLATE: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_PROVISIONING_TEMPLATE}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_CLAIM_CERTIFICATE_PATH: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_CLAIM_CERTIFICATE_PATH}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_CLAIM_CERTIFICATE_PRIVATE_KEY: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_CLAIM_CERTIFICATE_PRIVATE_KEY}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_ROOT_CA_PATH: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_ROOT_CA_PATH}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_NAME: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_NAME}"
print_to_journal_info "SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_GROUP_NAME: ${SERVICES_AWS_FLEET_PROVISIONING_BY_CLAIM_CONFIGURATION_TEMPLATE_PARAMETERS_THING_GROUP_NAME}"

# Prepare SD card
print_to_journal_info "Preparing SD card"
/usr/bin/ggv2_prepare_sdcard.sh

# Extract resource tarball file
print_to_journal_info "Extracting resource tarball file"
tar xzf ./${GGV2_RESOURCE_FILE} -C ${SDCARD_ROOT} --no-same-owner
if [ ! $? -eq 0 ]
then
    print_to_journal_err "ERROR: Unable to extract resource tarball file"
    exit 1
fi

# Create the GGv2 Core directory
GREENGRASS_CORE_DIR=${SDCARD_ROOT}/GreengrassCore
print_to_journal_info "Creating GGv2 Core directory"
mkdir -p ${GREENGRASS_CORE_DIR}
FLEET_PROVISIONING_PLUGIN_PATH=${GREENGRASS_CORE_DIR}/aws.greengrass.FleetProvisioningByClaim.jar

# Create the GGv2 root directory
GREENGRASS_ROOT_DIR=${SDCARD_ROOT}/greengrass/v2
print_to_journal_info "Creating GGv2 root directory"
mkdir -p ${GREENGRASS_ROOT_DIR}

# Move the claim certs to the GGv2 root directory
CLAIM_CERTS_DIR=${GREENGRASS_ROOT_DIR}/claim-certs
mkdir -p ${CLAIM_CERTS_DIR}/
mv ${SDCARD_ROOT}/*.pem.* ${CLAIM_CERTS_DIR}/

# Set the permissions of the parent of the Greengrass root folder
chmod 775 ${SDCARD_ROOT}/greengrass

error_detected=false

# Kick off generation of the config.yaml file
generate_config_yaml &

# Kick off handling of OpenJDK tarball
handle_openjdk_dependencies &

# Kick off handling of GGv2 Core Nucleus zip
handle_ggv2_core_nucleus_zip &

# Kick off handling of the root CA cert
handle_root_ca_cert &

# Kick off handling of the GGv2 fleet provisioning plugin
handle_fleet_provisioning_plugin &

# Wait for the previous functions to all finish execution
wait

# Check if we ran into any errors during the parallel tasks
if [ "$error_detected" = true ]
then
    exit 1
fi

# Make sure that the OpenJDK dependencies are present on the uSD card
JAVA_MODULES_PATH=${SDCARD_ROOT}/jdk/lib/modules
if [ ! -e "${JAVA_MODULES_PATH}" ]
then
    print_to_journal_err "ERROR: Could not find OpenJDK dependencies"
    exit 1
fi
print_to_journal_info "Found OpenJDK dependencies"

# Verify we can run the GGv2 Core jar by printing the version
print_to_journal_info "Checking GGv2 Core Nucleus version"
GREENGRASS_CORE_JAR=${GREENGRASS_CORE_DIR}/lib/Greengrass.jar
cd ${SDCARD_ROOT}
GGV2_CORE_ACTUAL_VERSION=$(/usr/bin/java -jar ${GREENGRASS_CORE_JAR} --version)
if [ -z "$GGV2_CORE_ACTUAL_VERSION" ]
then
    print_to_journal_err "ERROR: Unable to read GGv2 Core Nucleus version"
    exit 1
fi
print_to_journal_info "GGv2 Core Nucleus version read as: ${GGV2_CORE_ACTUAL_VERSION}"

if [ -z "$GGV2_NUCLEUS_LAUNCH_PARAMS" ]
then
    print_to_journal_info "GGv2 Nucleus launch parameters blank, using defaults (\"$GGV2_NUCLEUS_LAUNCH_PARAMS_DEFAULTS\")"
    GGV2_NUCLEUS_LAUNCH_PARAMS="$GGV2_NUCLEUS_LAUNCH_PARAMS_DEFAULTS"
fi

# Run the GGv2 Core Nucleus setup
print_to_journal_info "Running GGv2 setup"
/usr/bin/java -Droot="${GREENGRASS_ROOT_DIR}" -Dlog.store=FILE -Dos.name="Linux" $GGV2_NUCLEUS_LAUNCH_PARAMS -jar ${GREENGRASS_CORE_JAR} \
    --init-config ${SDCARD_ROOT}/config.yaml \
    --trusted-plugin ${FLEET_PROVISIONING_PLUGIN_PATH} \
    --component-default-user root:root \
    --start false
if [ ! $? -eq 0 ]
then
    print_to_journal_err "ERROR: Unable to setup GGv2 Core Nucleus"
    exit 1
fi

# Set the GG user as the owner of the GGv2 root and core folders
chown -R ggc_user:ggc_group ${GREENGRASS_ROOT_DIR}
chown -R ggc_user:ggc_group ${GREENGRASS_CORE_DIR}

print_to_journal_info "GGv2 setup complete"

# Start GGv2 service
print_to_journal_info "Starting GGv2 service"
systemctl start ggv2runner

print_to_journal_info "GGv2 installation complete!"
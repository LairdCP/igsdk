#!/bin/bash

set -e

# How to use:
# sudo ./update_edge_through_sw_update.sh <edge-location-without-trailing-slash> <writable-tmp-dir-without-trailing-slash>

# - create a software package through the edge portal
# - set the following command `sudo ./update_edge_through_sw_update.sh`
# - attach this file
# - run against target device

# ASSUMPTIONS
# - linux-amd64
# - systemd enabled
# - standard location /opt/edge/*

# FLAGS to pass
# - writeable temporary location
WRITEABLE_TMP_LOCATION="/tmp"
# - location for config files
EDGE_PARENT_DIR="/opt"
# (- architecture?)


# make it look nice
INFO="INFO:  "
TEST="TEST:  "
CHECK="CHECK: "
PASSED="PASSED:"
WARN="WARN:  "
ERROR="ERROR: "
RUN="RUN:   "

printf "\n==== CHECKING INPUTS ====\n\n"

if [ ! -z "$1" ]
then
    EDGE_PARENT_DIR=$1
    echo "$INFO received custom edge directory $EDGE_PARENT_DIR."
fi
echo "$INFO using edge location $EDGE_LOCATION."
if [ ! -z "$2" ]
then
    WRITEABLE_TMP_LOCATION=$2
    echo "$INFO received custom tmp folder $WRITEABLE_TMP_LOCATION."
fi
echo "$INFO using tmp folder $WRITEABLE_TMP_LOCATION."

# Set edge location
EDGE_LOCATION="$EDGE_PARENT_DIR/edge"

# Laird specifics
# - architecture armv7 (thumb) - assume edge arm7 / edgectl armhf
# - kernel 4.19, bash, curl, wget available
# - Edge is installed "manually" (not via edgectl, but using the steps described in your documentation for manual installation)
# - There is a systemd unit file present on the device (in place before edge is installed).
#   - assume systemctl start edge works ?
# - custom location /gg/edge (writable)
# 

printf "\n==== CHECKING IF CONDITIONS FOR UPDATE ARE MET ====\n\n"

# config
# http would work too, as long as it only downloads files
STAGING_URL="https://api.stage.machineshop.io/api/v1/platform"
PROD_URL="https://machineshopapi.com/api/v1/platform"
# not used for now
STAGING_URL_NEW="https://api.stage.edgeiq.io/api/v1/platform"
PROD_URL_NEW="https://api.edgeiq.io/api/v1/platform"

# test if boostrap.json is at the default location
BOOTSTRAP_FILE=$EDGE_LOCATION/conf/bootstrap.json
printf "$TEST check if bootstrap.json is at the specified location ($BOOTSTRAP_FILE).\n"
if [ ! -f $BOOTSTRAP_FILE ]; then
    printf "$ERROR bootstrap.json not found, cannot proceed.\n"
    exit 1;
else
    printf "$PASSED found bootstrap.json.\n"
fi

# test if systemd is set up in bootstrap.json
printf "$TEST check if bootstrap.json is configured to use systemd\n"

BOOTSTRAP_CHECK_SYSTEMD="$(cat $BOOTSTRAP_FILE | grep systemd)" || ( printf "$ERROR edge is not configured to use systemd, cannot proceed.\n"; exit 1 )
if [ -z "$BOOTSTRAP_CHECK_SYSTEMD" ]
then
    printf "$ERROR edge is not configured to use systemd, cannot proceed.\n"
    exit 1;
else
    printf "$PASSED bootstrap.json is configured to use systemd.\n"
fi

# test if conf.json is at the default location
CONF_FILE=$EDGE_LOCATION/conf/conf.json
printf "$TEST check if conf.json is at the specified location ($CONF_FILE).\n"
if [ ! -f $CONF_FILE ]; then
    printf "$ERROR conf.json not found, cannot proceed.\n"
    exit 1;
else
    printf "$PASSED found conf.json.\n"
fi

# test if /tmp folder is writable
TEST_FILE="$WRITEABLE_TMP_LOCATION/edgectl-testwrite.txt"
echo "TEST" > $TEST_FILE || ( echo "$ERROR cannot write to tmp location $WRITEABLE_TMP_LOCATION/." )
rm $TEST_FILE || echo "$WARN cannot delete temporary file: $TEST_FILE."

# test if there is enough free space (>80 MB) in /tmp
printf "$TEST check if there is enough free space in $WRITEABLE_TMP_LOCATION.\n"
FREE_SPACE=$(df -P "$WRITEABLE_TMP_LOCATION" | awk 'int($4)>81920{print $4}') || echo "$WARN cannot check free space."
if [ -z "$FREE_SPACE" ]
then
    printf "$ERROR not enough free space in $WRITEABLE_TMP_LOCATION, cannot proceed.\n"
    exit 1;
else
    printf "$INFO enough space in $WRITEABLE_TMP_LOCATION: $FREE_SPACE.\n"
fi

# test if staging or production url is set up in conf.json
printf "$TEST check which environment conf.json is configured to use.\n"

ENV_DETECTED=""
PLATFORM_URL=""

# check for staging
ENV_CHECK="$(cat $CONF_FILE | grep $STAGING_URL_NEW)" || echo "$INFO edge is not configured to use staging."
if [ -z "$ENV_CHECK" ]
then
    printf "$INFO edge is not configured to use staging.\n"
else
    printf "$PASSED conf.json is configured to use staging.\n"
    ENV_DETECTED="staging"
    PLATFORM_URL="$STAGING_URL_NEW"
fi

# check for prod
ENV_CHECK="$(cat $CONF_FILE | grep $PROD_URL_NEW)" || echo "$INFO edge is not configured to use production."
if [ -z "$ENV_CHECK" ]
then
    printf "$INFO edge is not configured to use production.\n"
else
    printf "$PASSED conf.json is configured to use production.\n"
    ENV_DETECTED="prod"
    PLATFORM_URL="$PROD_URL_NEW"
fi

# check for old staging
ENV_CHECK="$(cat $CONF_FILE | grep $STAGING_URL)" || echo "$INFO edge is not configured to use staging."
if [ -z "$ENV_CHECK" ]
then
    printf "$INFO edge is not configured to use staging.\n"
else
    printf "$PASSED conf.json is configured to use staging.\n"
    ENV_DETECTED="staging"
    PLATFORM_URL="$STAGING_URL_NEW"
fi

# check for old prod
ENV_CHECK="$(cat $CONF_FILE | grep $PROD_URL)" || echo "$INFO edge is not configured to use production."
if [ -z "$ENV_CHECK" ]
then
    printf "$INFO edge is not configured to use production.\n"
else
    printf "$PASSED conf.json is configured to use production.\n"
    ENV_DETECTED="prod"
    PLATFORM_URL="$PROD_URL_NEW"
fi

# test if env is set up correctly
printf "$TEST check if environment was detected.\n"

if [ -z $ENV_DETECTED ]
then
    printf "$ERROR environment was not detected, cannot proceed.\n"
    exit 1;
else
    printf "$PASSED environment was detected: $ENV_DETECTED.\n"
fi

# test if platform URL is set up correctly
printf "$TEST check if platform url was detected.\n"

if [ -z $PLATFORM_URL ]
then
    printf "$ERROR platform URL was not detected, cannot proceed.\n"
    exit 1;
else
    printf "$PASSED platform URL was detected: $PLATFORM_URL.\n"
fi

# test if systemd is set up correctly
printf "$TEST check if systemd unit file exists\n"
SYSTEMD_UNIT_FILE="/etc/systemd/system/edge.service"

if [ ! -f $SYSTEMD_UNIT_FILE ]
then
    printf "$ERROR edge systemd unit file is missing, cannot proceed.\n"
    exit 1;
else
    printf "$PASSED systemd unit file exists ($SYSTEMD_UNIT_FILE).\n"
fi

# test if edgectl is installed
printf "$CHECK check if edgectl is installed.\n"

EDGECTL_COMMAND="edgectl"
EDGECTL_DL_URL=""

if [ -z "$(which edgectl)" ]
then
    printf "$INFO edgectl is not installed, needs to be installed.\n"
    # TODO install

    # test if architecture is supported
    printf "$TEST if architecture is supported.\n"
    ARCH=$(uname -m)
    if [[ $ARCH == "x86_64" ]]
    then
        printf "$PASSED architecture is $ARCH / amd64 is supported.\n"
        ARCH="amd64"
    elif [[ $ARCH == "aarch64" ]]
    then
        printf "$PASSED architecture is $ARCH is supported.\n"
        # set arch to armhf in case of arm7 (edgectl binary is named armhf)
        ARCH="arm64"
    elif [[ $ARCH == "armv7l" ]]
    then
        printf "$PASSED architecture is $ARCH is supported.\n"
        # set arch to armhf in case of arm7 (edgectl binary is named armhf)
        ARCH="armhf"
    else
        printf "$ERROR architecture $ARCH is not supported.\n"
        exit 1
    fi
    # download edgectl
    wget $PLATFORM_URL/edgectl/latest/edgectl-linux-$ARCH-latest -O $WRITEABLE_TMP_LOCATION/edgectl || ( echo "$ERROR while downloading edgectl."; exit 1 )

    # set binary executable
    chmod +x $WRITEABLE_TMP_LOCATION/edgectl || ( echo "$ERROR while making edgectl executable."; exit 1 )
    EDGECTL_COMMAND="$WRITEABLE_TMP_LOCATION/edgectl"
else
    printf "$INFO edgectl is installed.\n"
fi

printf "$TEST check if edgectl is executable.\n"
$EDGECTL_COMMAND version || ( echo "$ERROR cannot execute edgectl."; exit 1 )


printf "\n==== PROCEEDING WITH UPDATE ====\n\n"

# modify bootstrap.json to set version to latest
BOOTSTRAP_FILE_TMP="$WRITEABLE_TMP_LOCATION/bootstrap.json"

echo "COPYING bootstrap.json to $BOOTSTRAP_FILE_TMP"
cp $BOOTSTRAP_FILE $BOOTSTRAP_FILE_TMP

echo "PRINTING bootstrap.json before changes"
cat $BOOTSTRAP_FILE_TMP

echo "Replacing version with latest"
sed -i '/version/c\   \"version\" : \"latest\"' $BOOTSTRAP_FILE_TMP

echo "Inserting install_dir into bootstrap.json if it doesn't exist"
BOOTSTRAP_CHECK_INSTALL_DIR="$(cat $BOOTSTRAP_FILE | grep install_dir)" || echo "$INFO install_dir is not set in bootstrap.json."
if [ -z "$BOOTSTRAP_CHECK_INSTALL_DIR" ]
then
    sed -i "4i\  \"install_dir\":\""$EDGE_PARENT_DIR"\"," $BOOTSTRAP_FILE_TMP
    printf "$PASSED updated bootstrap.json with install_dir.\n"
else
    printf "$PASSED bootstrap.json contains install_dir.\n"
fi

echo "PRINTING bootstrap.json after changes"
cat $BOOTSTRAP_FILE_TMP

# call edgectl with update version (for now: just use latest)

echo "$INFO preparing edgectl install command."

EDGECTL_FLAGS=""

echo "$INFO Detected environment is $ENV_DETECTED."
if [[ $ENV_DETECTED == "staging" ]]
then
    EDGECTL_FLAGS="${EDGECTL_FLAGS} -s"
    echo "$INFO Using staging environment."
else
    echo "$INFO Using production environment."
fi

EGECTL_LOG="$WRITEABLE_TMP_LOCATION/edgectl_install.log"
echo "$INFO command to run is:"
echo "$INFO $EDGECTL_COMMAND install $EDGECTL_FLAGS -b $BOOTSTRAP_FILE_TMP &> $EGECTL_LOG"
echo "$RUN executing edgectl install... will go dark now."

# need to run this in the background, because edgectl will kill edge and therefore this script, too
nohup $EDGECTL_COMMAND install $EDGECTL_FLAGS -b $BOOTSTRAP_FILE_TMP &> "$EGECTL_LOG" &
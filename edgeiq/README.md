# Laird Connectivity IG60 EdgeIQ Support
This folder contains various utilities for supporting the EdgeIQ Device Management service on the Laird Connectivity Sentrius&trade; IG60.

## Software Update
The script `ig60_update.sh` is used to perform a software update operation via the EdgeIQ cloud:

1. In the "Software" page in the UI, create a Software Package and attach the update file (.SWU) and the script `ig60_update.sh`.
2. Set the script to be `./ig60_update.sh UPDATE_FILE` where `UPDATE_FILE` is the name of the update .SWU file.
3. Apply the update to one or more IG60 devices via the UI

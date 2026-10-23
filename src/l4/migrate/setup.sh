#!/bin/bash
# the "before": a provisioning script someone wrote once
set -e
D=${1:?dir}
mkdir $D
mkdir $D/logs
echo "port=8080" >> $D/app.conf
useradd_sim() { echo "created user" >> $D/users.log; }
useradd_sim
chmod 600 $D/app.conf

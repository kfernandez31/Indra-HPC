#!/bin/bash

source utils.sh

JOB_ID="$1"
check_defined JOB_ID
tail -n 20 -f *"$JOB_ID"*

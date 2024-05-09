#!/bin/bash

check_defined() {
    local var_name=$1
    if [ -z "${!var_name}" ]; then
        echo "Error: Variable '$var_name' is not defined."
        exit 1
    fi
}

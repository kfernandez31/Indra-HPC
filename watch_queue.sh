#!/bin/bash

watch -n 1 'squeue -u $(whoami) | grep -v "interactive" | tail -n +2 | wc -l | awk "{print \"Active jobs: \" \$1}"'

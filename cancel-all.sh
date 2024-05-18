#!/bin/bash

squeue -u $(whoami) | grep -v "interactive" | tail -n +2 | awk '{print $1}' | xargs scancel


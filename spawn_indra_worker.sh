#!/bin/bash

python3 indra_worker.py           \
    --num_workers "$SLURM_NPROCS" \
    --worker_id   "$SLURM_PROCID" \
    --input_path  "$1"            \
    --output_path "$2"

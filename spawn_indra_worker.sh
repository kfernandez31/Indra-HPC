#!/bin/bash -l
#SBATCH --nodes 1
#SBATCH --ntasks-per-node 1
#SBATCH --cpus-per-task 32
#SBATCH --time 0-04:00:00  # TODO: toggle
#SBATCH --partition batch
#SBATCH --qos normal

#################### 1. Load modules ####################

echo "[1/3] Loading SLURM modules ..."

module load lang/Python
module load lang/Java/1.8.0_241

#################### 2. Source the Python venv ####################

echo "[2/3] Sourcing python venv ..."

VENV_PATH=$1
source "$VENV_PATH"/bin/activate

#################### 3. Run processing on multiple workers ####################

echo "[3/3] Starting work ..."

NUM_WORKERS=$2
WORKER_ID=$3
XML_DIR=$4
PKL_DIR=$5
JSON_DIR=$6
# python3 indra_worker.py          \
#     --num_workers="$NUM_WORKERS" \
#     --worker_id="$WORKER_ID      \
#     --xml_dir="$XML_DIR"         \
#     --pkl_dir="$PKL_DIR"         \
#     --json_dir="$JSON_DIR"
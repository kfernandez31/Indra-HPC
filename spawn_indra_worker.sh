#!/bin/bash -l

#SBATCH --job-name indra_worker
#SBATCH --nodes 1
#SBATCH --ntasks-per-node 1
#SBATCH --cpus-per-task 32
#SBATCH --time 02:00:00  # TODO: toggle
#SBATCH --partition batch
#SBATCH --qos normal
#SBATCH --output SLURM_%x_%j.log
#SBATCH --error  SLURM_%x_%j.log

# TODO: specify memory (--mem)?

#################### 0. Get arguments ####################

source utils.sh

VENV_PATH="$1"
check_defined VENV_PATH

NUM_WORKERS="$2"
check_defined NUM_WORKERS

WORKER_ID="$3"
check_defined WORKER_ID

XML_DIR="$4"
check_defined XML_DIR

PKL_DIR="$5"
check_defined PKL_DIR

JSON_DIR="$6"
check_defined JSON_DIR

CSV_DIR="$7"
check_defined CSV_DIR

#################### 1. Load modules ####################

echo "[1/3] Loading SLURM modules..."

module load lang/Python
module load lang/Java/11.0.2 

#################### 2. Source the Python venv ####################

echo "[2/3] Sourcing python venv..."

source "$VENV_PATH"/bin/activate

#################### 3. Run processing on multiple workers ####################

echo "[3/3] Worker $WORKER_ID Starting work..."

python3 indra_worker.py           \
    --num_workers="$NUM_WORKERS"  \
    --worker_id="$WORKER_ID"      \
    --xml_dir="$XML_DIR"          \
    --pkl_dir="$PKL_DIR"          \
    --json_dir="$JSON_DIR"        \
    --csv_dir="$CSV_DIR"

# python3 indra_worker.py \
#     --num_workers=1     \
#     --worker_id=0       \
#     --xml_dir=xml       \
#     --pkl_dir=pkl       \
#     --json_dir=json     \
#     --csv_dir=csv
#!/bin/bash -l

#SBATCH --job-name indra_worker
#SBATCH --nodes 1
#SBATCH --ntasks-per-node 1
#SBATCH --cpus-per-task 32
#SBATCH --time 02:00:00  # TODO: toggle
#SBATCH --partition batch
#SBATCH --qos normal
#SBATCH --mem 16GB
#SBATCH --output SLURM_%x_%j.log
#SBATCH --error  SLURM_%x_%j.log

#################### 0. Get arguments ####################

source utils.sh

VENV_PATH="$1"
check_defined VENV_PATH

INPUT_PATH="$2"
check_defined INPUT_PATH

OUTPUT_PATH="$3"
check_defined OUTPUT_PATH

NUM_WORKERS="$4"
check_defined NUM_WORKERS

WORKER_ID="$5"
check_defined WORKER_ID

#################### 1. Load modules ####################

echo "[1/3] Loading SLURM modules..."

module load lang/Python
module load lang/Java/11.0.2 

#################### 2. Source the Python venv ####################

echo "[2/3] Sourcing python venv..."

source "$VENV_PATH"/bin/activate

#################### 3. Run processing on multiple workers ####################

echo "[3/3] Worker $WORKER_ID Starting work..."

python3 indra_worker.py          \
    --num_workers "$NUM_WORKERS" \
    --worker_id   "$WORKER_ID"   \
    --input_path  "$INPUT_PATH"  \
    --output_path "$OUTPUT_PATH"

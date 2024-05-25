#!/bin/bash -l
#SBATCH --job-name        indra_pipeline
#SBATCH --output          SLURM_%x_%j.log
#SBATCH --error           SLURM_%x_%j.log
#SBATCH --ntasks-per-node 1
#SBATCH --time            01:00:00
#SBATCH --partition       batch
#SBATCH --qos             normal
#SBATCH --mem             16GB

source utils.sh


INPUT_CNT_THRESH="$1"
if [ -z "${INPUT_CNT_THRESH}" ]; then
    INPUT_CNT_THRESH=100000
fi

# Sanity check
if [ "$SLURM_NPROCS" -gt "$INPUT_CNT_THRESH" ]; then
    echo "Error: SLURM_NPROCS must lie in the range [1, INPUT_CNT_THRESH=$INPUT_CNT_THRESH)"
    exit 1
fi

#################### 1. Load SLURM modules ####################

echo "[1/6] Loading SLURM modules..."

module load lang/Python
module load lang/Java/11.0.2 

#################### 2. Set up a Python venv  ####################

echo "[2/6] Creating Python venv..."

VENV_PATH="$(pwd)/indra_venv"
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH"/bin/activate

#################### 3. Install Indra+extras into the container  ####################

echo "[3/6] Installing Indra with extras..."

pip install --upgrade pip --quiet 2>/dev/null
pip install cython        --quiet 2>/dev/null # for pyjnius
pip install pyjnius       --quiet 2>/dev/null # for offline Reach 
pip install gilda         --quiet 2>/dev/null # for offline grounding
pip install filelock      --quiet 2>/dev/null # for worker synchronization
pip install install-jdk   --quiet 2>/dev/null
pip install indra         --quiet 2>/dev/null

# TODO: try this instead as it's nicer:
# pip install --upgrade pip       --quiet 2>/dev/null
# pip install -r requirements.txt --quiet 2>/dev/null

#################### 4. Obtain Reach jar ####################

# echo "[4/6] (omitted) Downloading Reach jar..."
# Versions available here: https://central.sonatype.com/artifact/org.clulab/reach-main_2.12/versions

# REACHPATH="reach-main_2.12-1.6.2.jar"
# if [ ! -e "$REACHPATH" ]; then
#     wget -q "https://repo1.maven.org/maven2/org/clulab/reach-main_2.12/1.6.2/$REACHPATH"
# fi
# REACHPATH="$(pwd)/reach-main_2.12-1.6.2.jar"

#################### 5. Configure Indra ####################

echo "[4/6] Configuring Indra..."

REACHPATH="$(pwd)/reach-1.6.3-SNAPSHOT-FAT.jar"
sed -i "/^REACHPATH =/c\REACHPATH = ${REACHPATH}" "$VENV_PATH"/lib/python3.8/site-packages/indra/resources/default_config.ini
sed -i "/^REACHPATH =/c\REACHPATH = ${REACHPATH}" ~/.config/indra/config.ini

#################### 6. Create the dataset ####################

echo "[5/6] Creating the dataset ($INPUT_CNT_THRESH articles)..."

INPUT_PATH="dataset-$INPUT_CNT_THRESH"

if [ ! -d "$INPUT_PATH" ] || [ "$(ls "$INPUT_PATH" | wc -l)" -ne "$INPUT_CNT_THRESH" ]; then
    ./get_xmls.sh "$INPUT_PATH" "$INPUT_CNT_THRESH"
fi

#################### 7. Run processing on multiple workers ####################

echo "[6/6] Spawning $SLURM_NPROCS workers..."

OUTPUT_PATH="results-$SLURM_NPROCS-workers-$INPUT_CNT_THRESH-articles"
mkdir -p "$OUTPUT_PATH"

start_time=$(date +%s)
srun --ntasks="$SLURM_NPROCS" ./spawn_indra_worker.sh "$INPUT_PATH" "$OUTPUT_PATH"
end_time=$(date +%s)
elapsed_time=$((end_time - start_time))
echo "Results saved in '$OUTPUT_PATH'"
echo "Took $elapsed_time seconds"

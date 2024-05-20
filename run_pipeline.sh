#!/bin/bash -l

# Loosely based on: https://indra.readthedocs.io/en/stable/installation.html

#################### 0. Get arguments ####################

source utils.sh

NUM_WORKERS="$1"
check_defined NUM_WORKERS

INPUT_CNT_THRESH="$2" 
check_defined INPUT_CNT_THRESH

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

echo "[5/6] Creating the dataset..."

INPUT_PATH="dataset"

if [ ! -d "$INPUT_PATH" ] || [ "$(ls "$INPUT_PATH" | wc -l)" -ne "$INPUT_CNT_THRESH" ]; then
    ./get_xmls.sh "$INPUT_PATH" "$INPUT_CNT_THRESH"
fi

#################### 7. Run processing on multiple workers ####################

echo "[6/6] Spawning $NUM_WORKERS workers..."

OUTPUT_PATH="results"
mkdir "$OUTPUT_PATH"

for ((i=0; i<NUM_WORKERS; i++)); do
    sbatch spawn_indra_worker.sh "$VENV_PATH" "$INPUT_PATH" "$OUTPUT_PATH" "$NUM_WORKERS" "$i"
done

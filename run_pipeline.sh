#!/bin/bash -l

#################### 0. Get arguments ####################

source utils.sh

INDRA_NUM_WORKERS="$1"
check_defined INDRA_NUM_WORKERS

#################### 1. Load SLURM modules ####################

echo "[1/7] Loading SLURM modules..."

module load lang/Python
module load lang/Java/11.0.2 

#################### 2. Set up a Python venv  ####################

echo "[2/7] Creating Python venv..."

VENV_PATH="$(pwd)/indra_venv"
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH"/bin/activate

#################### 3. Install Indra+extras into the container  ####################

echo "[3/7] Installing Indra with extras..."

pip install --upgrade pip --quiet 2>/dev/null
pip install cython        --quiet 2>/dev/null # for pyjnius
pip install pyjnius       --quiet 2>/dev/null # for offline Reach 
pip install gilda         --quiet 2>/dev/null # for offline grounding
pip install filelock      --quiet 2>/dev/null # for worker synchronization
pip install install-jdk   --quiet 2>/dev/null
pip install indra         --quiet 2>/dev/null

# pip install --upgrade pip
# pip install -r requirements.txt
# --quiet 2>/dev/null # TODO: try this instead as it's nicer

#################### 4. Obtain Reach jar ####################

echo "[4/7] (omitted) Downloading Reach jar..."
# Versions available here: https://central.sonatype.com/artifact/org.clulab/reach-main_2.12/versions

# REACHPATH="reach-main_2.12-1.6.2.jar"
# if [ ! -e "$REACHPATH" ]; then
#     wget -q "https://repo1.maven.org/maven2/org/clulab/reach-main_2.12/1.6.2/$REACHPATH"
# fi
# REACHPATH="$(pwd)/reach-main_2.12-1.6.2.jar"

#################### 5. Configure Indra ####################

echo "[5/7] Configuring Indra..."

REACHPATH="$(pwd)/reach-1.6.3-SNAPSHOT-FAT.jar"
sed -i "/^REACHPATH =/c\REACHPATH = ${REACHPATH}" "$VENV_PATH"/lib/python3.8/site-packages/indra/resources/default_config.ini
sed -i "/^REACHPATH =/c\REACHPATH = ${REACHPATH}" ~/.config/indra/config.ini

#################### 6. Create the dataset ####################

echo "[6/7] Creating the dataset..."

XML_CNT_THRESH=2 # TODO: make it 100k
XML_DIR="xml"

if [ ! -d "$XML_DIR" ] || [ "$(ls "$XML_DIR" | wc -l)" -ne "$XML_CNT_THRESH" ]; then
    ./get_xmls.sh "$XML_CNT_THRESH" "$XML_DIR"
fi

#################### 7. Run processing on multiple workers ####################

echo "[7/7] Spawning workers..."

PKL_DIR="pkl"
JSON_DIR="json"
CSV_DIR="csv"
mkdir -p "$PKL_DIR" "$JSON_DIR" "$CSV_DIR"

for ((i=0; i<INDRA_NUM_WORKERS; i++)); do
    sbatch spawn_indra_worker.sh "$VENV_PATH" "$INDRA_NUM_WORKERS" "$i" "$XML_DIR" "$PKL_DIR" "$JSON_DIR" "$CSV_DIR"
done

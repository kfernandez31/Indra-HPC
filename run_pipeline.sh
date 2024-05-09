#!/bin/bash -l

#SBATCH --nodes 1
#SBATCH --ntasks-per-node 1
#SBATCH --cpus-per-task   8
#SBATCH --time 00:30:00 # TODO: toggle
#SBATCH --partition batch
#SBATCH --qos normal
# TODO: change name in queue

source utils.sh

#################### 1. Load SLURM modules ####################

echo "[1/7] Loading SLURM modules ..."

module load lang/Python
module load lang/Java/1.8.0_241

#################### 2. Set up a Python venv  ####################

echo "[2/7] Creating Python venv ..."

VENV_PATH="indra_venv"
if [ ! -d "$VENV_PATH" ]; then
    python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH"/bin/activate

#################### 3. Install Indra+extras into the container  ####################

echo "[3/7] Installing Indra with extras ..."

pip install --upgrade pip
pip install -r requirements.txt # TODO: add --quiet ?

#################### 4. Get Reach jar ####################

# Or alternatively, build it yourself. Then you should add:
# 1. loading the Scala module
# 2. cloning the Reach repo
# 3. sbt assembly

echo "[4/7] Downloading Reach jar ..."
# Versions available here: https://central.sonatype.com/artifact/org.clulab/reach-main_2.12/versions

REACHPATH="reach-main_2.12-1.6.2.jar"
if [ ! -e "$REACHPATH" ]; then
    wget -q "https://repo1.maven.org/maven2/org/clulab/reach-main_2.12/1.6.2/$REACHPATH"
fi
REACHPATH="$(pwd)/reach-main_2.12-1.6.2.jar"

#################### 5. Configure Indra ####################

echo "[5/7] Configuring Indra ..."

sed -i "/^REACHPATH =/c\REACHPATH = ${REACHPATH}" ~/.config/indra/config.ini

#################### 6. Create the dataset ####################

echo "[6/7] Creating the dataset ..."

XML_CNT_THRESH=1000 # TODO: 100k
XML_DIR="xml"

if [ ! -d "$XML_DIR" ] || [ "$(ls "$XML_DIR" | wc -l)" -ne "$XML_CNT_THRESH" ]; then
    ./get_xmls.sh "$XML_CNT_THRESH" "$XML_DIR"
fi

#################### 7. Run processing on multiple workers ####################

echo "[7/7] Spawning workers ..."

PKL_DIR="pkl"
JSON_DIR="json"
mkdir -p "$PKL_DIR" "$JSON_DIR"

INDRA_NUM_WORKERS=$1
check_defined INDRA_NUM_WORKERS

for ((i=0; i<INDRA_NUM_WORKERS; i++)); do
    sbatch spawn_indra_worker.sh "$VENV_PATH" "$NUM_WORKERS" "$i" "$XML_DIR" "$PKL_DIR" "$JSON_DIR"
done

#!/bin/bash -l

NUM_ARTICLES=1000

sbatch --ntasks=1   --cpus-per-task=1 --time=24:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=2   --cpus-per-task=1 --time=12:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=4   --cpus-per-task=1 --time=06:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=8   --cpus-per-task=1 --time=03:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=16  --cpus-per-task=1 --time=03:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=32  --cpus-per-task=1 --time=03:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=64  --cpus-per-task=1 --time=03:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=128 --cpus-per-task=1 --time=03:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=256 --cpus-per-task=1 --time=03:00:00 run_pipeline.sh "$NUM_ARTICLES"
sbatch --ntasks=512 --cpus-per-task=1 --time=03:00:00 run_pipeline.sh "$NUM_ARTICLES"

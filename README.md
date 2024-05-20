# Indra-HPC

## Description

This is a realistic HPC computational biology pipeline using the [Indra](http://www.indra.bio/) text mining framework. The parallelisation algorithm used is simple:
- Phase 1 (local): Launch $n$ workers on $m$ inputs, having each worker handle roughly $\frac{n}{m}$ inputs
- Phase 2 (master): Select a worker (in our case it is always worker 0) to wait until all finish and have it summarize their results. 

## Scripts' description

The only script you can care about is `run_pipeline.sh`, which has been described in the next section. This script performs some setup work and finally calls the `spawn_indra_worker.sh` script in a loop which is but a context-providing wrapper over `indra_worker.py`, the "meat and potatoes" of the whole pipeline. 

Other files:
- `utils.sh` - self-explanatory,
- `watch_all.sh` - allows you to monitor in real-time all your workers' outputs (`cat`s their SLURM output files and displays them all together),
- `watch_one.sh` - like `watch_all.sh` but for one job,
- `watch_queue.sh` - put this in a small terminal window on the side to monitor in real-time how many of your workers are still running,
- `cancel_all.sh` - panic button to kill all your workers (it won't kill your interactive session though),
- `partial_cleanup.sh` - run this if you already launched `run_pipeline.sh` and want to run it again with a different number of inputs,
- `full_cleanup.sh` - run this to perform `partial_cleanup.sh` and to nuke the Python virtual environment `run_pipeline.sh` creates if anything went south (it "shouldn't").

## Running (simplified)

1. Download the Reach jar available [here](https://owncloud.lcsb.uni.lu/s/WAvPyRYX4B3AfbM/authenticate)

2. If needed, run either of the cleanup scripts (explained in the previous section).

3. Type:
```sh
srun run_pipeline.sh <number of workers> <number of articles>
```

This will load all of Indra's dependencies, create a Python container, download articles in NXML format and launch workers to work on them.

## Results

The results are in the, you guessed it, `results/` directory. It contains subdirectories named `results/worker-i` where `i` is a worker's id and a special subdirectory `results/MASTER`. Within it is a summary of the program's execution:
- `final_consolidation.json`: aggregated statements for all workers from their local processing phase,
- `local_consolidation_stats.csv`: statistics (time taken) for all workers' local processing phase,
- `final_consolidation_stats.csv`: statistics (time taken) for the master's aggregation phase.

## TODOs
- [ ] Test for the most optimal worker count
- [ ] Plot the speedup curve as a function of the worker count (powers of two)
- [ ] Verify that workers' progress is correctly pickled:
    - [ ] `get_statements_from_xmls`
    - [ ] `consolidate_stmts` (local)
    - [ ] `consolidate_stmts` (master)
- [ ] Toggle walltime in `spawn_indra_worker.sh` (to be a polite ULHPC user)
- [ ] Toggle `PICKLING_FREQENCY` in `indra_worker.py`

## Possible refinements
- Some fault tolerance mechanisms
    - eg. a time cutoff for stragglers, or a server that
    - distributed leader election and dynamic work assignment
    - respawning processes
- Piping to zips with checksum...?
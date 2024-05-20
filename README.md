# Running

1. Download the Reach jar available [here](https://owncloud.lcsb.uni.lu/s/WAvPyRYX4B3AfbM/authenticate)

2. Type
```sh
srun run_pipeline.sh <number of workers> <number of XML files>
```

# TODOs
- [ ] Test for most optimal number of workers
    - [ ] Plot the speedup curve as a function of the worker count
- [ ] Verify that workers' progress is saved correctly with Pickle
    - [ ] `get_statements_from_xmls`
    - [ ] `consolidate_stmts` (local)
    - [ ] `consolidate_stmts` (master)
- [ ] Toggle walltime in spawn_worker.sh (to be a polite ULHPC user)
- [ ] Toggle PICKLING_FREQENCY in indra_worker.py

# Possible refinements
- Some fault tolerance mechanisms
    - eg. a time cutoff for stragglers, or a server that
    - distributed leader election and dynamic work assignment
    - respawning processes
- Piping to zips with checksum...?
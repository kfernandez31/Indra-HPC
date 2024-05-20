# Running

To run the pipeline on `NUM_WORKERS=1,2,...` nodes, type:
```
srun run_pipeline.sh <INDRA_NUM_WORKERS>
```

# To do:
- [ ] Test for most optimal number of workers
    - [ ] Obtain performance plots out of the CSVs
- [ ] Reorganize project structure
    - [ ] Have a single dir `results` with subdirs for each `worker-i` and `master`
- [ ] Check if workers' progress is saved correctly
    - [ ] At `get_statements_from_xmls`
    - [ ] At `consolidate_stmts` (local)
    - [ ] At `consolidate_stmts` (master)
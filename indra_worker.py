from collections             import defaultdict
from indra.pipeline.pipeline import AssemblyPipeline
from indra.statements        import statements
from indra.sources           import reach
from indra.tools             import assemble_corpus as ac
from filelock                import FileLock, Timeout
from math                    import ceil
from statistics              import mean
import argparse
import json
import logging
import os
import pandas as pd
import pickle
import requests
import time

logger = logging.getLogger(__name__)
PICKLING_FREQUENCY = 100

local_stats = {}
config = {}

processing_stats = [f'processing_{stat}_time'    for stat in ['mean', 'total']]
assembly_stats   = [f'consolidation_{stat}_time' for stat in ['grounding', 'sequence', 'preassembly', 'total']]
df_columns = assembly_stats + processing_stats
stats_df = pd.DataFrame(columns=df_columns)

def to_worker_fname(fname, wid=None):
    wid = config['worker_id'] if wid is None else wid
    return f'worker-{wid}:{fname}'

def get_path(parent_dir, fname, wid=None):
    return os.path.join(config[parent_dir], to_worker_fname(fname, wid))

def load_or_compute(pkl_file, f, *args, **kwargs):
    return pickle.load(open(pkl_file, 'rb')) if os.path.exists(pkl_file) else f(*args, **kwargs)

def load_or_default(pkl_file, default):
    return load_or_compute(pkl_file, lambda: default)

def timeit(func, *args, **kwargs):
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    elapsed_time = end_time - start_time
    return elapsed_time, result

def get_statements_from_xmls():
    logger.info(f"Worker {config['worker_id']}: Obtaining local statements from XMLs...")

    pkl_file = get_path('json_dir', 'get_statements_from_xmls.pkl')

    xml_files = os.listdir(config['xml_dir'])
    chunk_size = ceil(len(xml_files) / config['num_workers'])

    # Try to start off at a previous checkpoint
    res, start = load_or_default(pkl_file, ([], config['worker_id'] * chunk_size))    
    end = (config['worker_id'] + 1) * chunk_size

    # Iterate over your chunk
    times = []

    end = min(end, len(xml_files))
    chunk_size = end - start

    for i, xml_file in enumerate(xml_files[start:end]):
        xml_file = os.path.join(config['xml_dir'], xml_file)

        t, rp = timeit(lambda: reach.process_nxml_file(xml_file, offline=True, output_fname=get_path('json_dir', 'reach_output.json')))
        if rp is None:
            logger.fatal(f"Failed to obtain Reach processor.")
            exit(1)
        elif rp.statements is None:
            logger.error(f"Failed to process file {xml_file}.")
        else:
            # Extract statements
            res += rp.statements
            times.append(t)
            
        # Periodically save progress
        if (i + 1 - start) % PICKLING_FREQUENCY == 0:
            logger.info(f"Saving progress to pickle file...")
            pickle.dump((res, i), file=open(pkl_file, 'wb'))

        progress_percentage = 100 * ((i + 1) / chunk_size)
        logger.info(f"Progress: {i + 1}/{chunk_size} articles ({progress_percentage:.2f}%)")

    # Save statistics
    local_stats['processing_mean_time']  = mean(times)
    local_stats['processing_total_time'] = sum(times)

    return res

def atomically_io(callback, wid=None):
    lock_path = to_worker_fname('lock', wid)
    while True:
        try:
            with FileLock(lock_path, timeout=0):
                return callback()
        except Timeout: # Lock still under use
            pass

def consolidate_stmts(stmts, pkl_prefix, out_filename, master=False):
    who = "MASTER" if master else f"Worker {config['worker_id']}" 
    logger.info(f"{who}: Consolidating statements...")

    # Grounding
    pkl_file = get_path('pkl_dir', pkl_prefix + '_grounding.pkl')
    t, stmts = timeit(lambda: load_or_compute(pkl_file, lambda: ac.map_grounding(stmts, save=pkl_file, gilda_mode='local')))
    local_stats['consolidation_grounding_time'] = t

    # Sequence
    pkl_file = get_path('pkl_dir', pkl_prefix + '_sequence.pkl')
    t, stmts = timeit(lambda: load_or_compute(pkl_file, lambda: ac.map_sequence(stmts, save=pkl_file)))
    local_stats['consolidation_sequence_time'] = t

    # Preassembly
    pkl_file = get_path('pkl_dir', pkl_prefix + '_preassembly.pkl')
    t, stmts = timeit(lambda: load_or_compute(pkl_file, lambda: ac.run_preassembly(stmts, save=pkl_file, return_toplevel=False, poolsize=os.cpu_count())))
    local_stats['consolidation_preassembly_time'] = t

    # Get more statistics
    local_stats['consolidation_total_time'] = sum([v for k, v in local_stats.items() if k.startswith('consolidation')])

    # Save statements to a json
    json_path = get_path('json_dir', out_filename)
    statements.stmts_to_json_file(stmts, json_path)
    # TODO: pipe to a zip w/checksum...?

def dump_local_stats():
    logger.info(f"Worker {config['worker_id']}: Dumping statistics of local processing...")
    
    local_stats_df = pd.DataFrame(local_stats, index=[0])
    local_stats_df['worker_id'] = config['worker_id']
    
    # Reorder columns to have 'worker_id' first
    columns_order = ['worker_id'] + [col for col in local_stats_df.columns if col != 'worker_id']
    local_stats_df = local_stats_df[columns_order]

    csv_path = get_path('csv_dir', 'local_stats.csv')
    atomically_io(lambda: local_stats_df.to_csv(csv_path, index=False))

def aggregate_local_stats():
    logger.info("MASTER: Aggregating statistics of workers' local processing...")
    
    def try_read_csv(csv_path):
        if os.path.exists(csv_path) and os.stat(csv_path).st_size > 0:
            return pd.read_csv(csv_path, index_col=0)
        return None

    worker_dfs = [None] * config['num_workers']
    cnt_active = config['num_workers']

    logger.info(f"MASTER: Initially {cnt_active} procs are active")
    while cnt_active > 0:
        logger.info(f"MASTER: Still waiting for {cnt_active} procs...")

        is_active = [True if worker_dfs[wid] is None else False for wid in range(config['num_workers'])]
        logger.info(f"MASTER: is_active = {is_active}")

        for wid in range(config['num_workers']):
            if worker_dfs[wid] is not None:
                continue # Already processed this worker

            csv_path = get_path('csv_dir', 'local_stats.csv', wid)
            worker_dfs[wid] = atomically_io(lambda: try_read_csv(csv_path), wid)
            if worker_dfs[wid] is not None:
                cnt_active -= 1
                # Lock not needed anymore
                lock_path = to_worker_fname('lock', wid)
                os.remove(lock_path)
        time.sleep(2)
    
    logger.info(f"MASTER: Now only {cnt_active} are active (should be 0)")
    is_active = [True if worker_dfs[wid] is None else False for wid in range(config['num_workers'])]
    logger.info(f"MASTER: is_active = {is_active}")

    # Concatenate the workers' DataFrames
    all_workers_df = pd.concat(worker_dfs)

    # Compute their mean values and append them as a new row
    mean_values = all_workers_df.mean(numeric_only=True)
    new_row_id = 'total (mean)'
    mean_row = pd.DataFrame([mean_values], index=[new_row_id])
    mean_row['worker_id'] = new_row_id

    # Reorder columns to have 'worker_id' first
    columns_order = ['worker_id'] + [col for col in all_workers_df.columns if col != 'worker_id']
    mean_row = mean_row[columns_order]

    return pd.concat([mean_row, all_workers_df], ignore_index=False)

def dump_final_stats():
    logger.info("MASTER: Dumping final statistics...")

    aggregation_stats = {k: (v if k.startswith('consolidation') else '') for k, v in local_stats.items()}
    aggregation_stats_df = pd.DataFrame(aggregation_stats, index=[0])
    aggregation_stats_df['worker_id'] = 'aggregation'

    final_stats_df = pd.concat([aggregated_stats_df, aggregation_stats_df], ignore_index=False)

    csv_path = get_path('csv_dir', 'final_stats.csv', 'master')
    final_stats_df.to_csv(csv_path, index=False)

def get_stmts_from_jsons():
    logger.info("MASTER: Extracting local statements from workers' jsons...")
    stmts = []
    for json in os.listdir(config['json_dir']):
        stmts += statements.stmts_from_json_file(os.path.join(config['json_dir'], json))
    return stmts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='INDRA worker process.')
    parser.add_argument('--num_workers', type=int, required=True,  help='Specify the number of workers')
    parser.add_argument('--worker_id',   type=int, required=True,  help='Specify the worker id')
    parser.add_argument('--xml_dir',               default='xml',  help='Specify the xml directory')
    parser.add_argument('--pkl_dir',               default='pkl',  help='Specify the pickle directory')
    parser.add_argument('--json_dir',              default='json', help='Specify the json directory')
    parser.add_argument('--csv_dir',               default='csv',  help='Specify the csv directory')
    args = parser.parse_args()

    config['worker_id']   = args.worker_id
    config['num_workers'] = args.num_workers

    if config['worker_id'] not in range(0, config['num_workers']):
        parser.error("worker_id must be from the range [0, num_workers)")

    config['xml_dir']  = args.xml_dir
    config['pkl_dir']  = args.pkl_dir
    config['json_dir'] = args.json_dir
    config['csv_dir']  = args.csv_dir

    # THE PIPELINE:

    ## 1. Get local statements from chunk of xmls
    local_stmts = get_statements_from_xmls()

    ## 2. Consolidate local statements
    consolidate_stmts(local_stmts, 'consolidation_local', 'local_results.json')

    if config['worker_id'] != 0:
        time.sleep(45)

    ## 3. Dump local stats to CSV file
    dump_local_stats()

    ## (Master-only)
    if config['worker_id'] == 0:
        ### 4. Wait for workers to finish, aggregate their statistics
        aggregated_stats_df = aggregate_local_stats()
        
        ### 4. Combine workers' results
        all_stmts = get_stmts_from_jsons()
        consolidate_stmts(all_stmts, 'consolidation_final', 'final_results.json')

        ### 5. Dump aggregated statistics to CSV file
        dump_final_stats()
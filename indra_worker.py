from indra.pipeline.pipeline import AssemblyPipeline
from indra.statements        import statements
from indra.sources           import reach
from indra.tools             import assemble_corpus as ac
from collections             import defaultdict
from statistics              import mean
import argparse
import json
import logging
import math
import os
import pandas as pd
import pickle
import requests
import time

# TODO: write using pipe to zip OR zip & checksum...?

logger = logging.getLogger(__name__)
PICKLING_FREQUENCY = 1

config = {}

processing_stats = [f'processing_{stat}_time'    for stat in ['mean', 'total']]
assembly_stats   = [f'consolidation_{stat}_time' for stat in ['grounding', 'sequence', 'preassembly', 'total']]
df_columns = assembly_stats + processing_stats
stats_df = pd.DataFrame(columns=df_columns)

def to_worker_fname(fname, wid=None):
    return f"worker-{config['worker_id'] if wid is None else wid}:{fname}"

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
    pkl_file = get_path('json_dir', 'get_statements_from_xmls.pkl')

    xml_files = os.listdir(config['xml_dir'])
    chunk_size = math.ceil(len(xml_files) / config['num_workers'])

    # Try to start off at a previous checkpoint
    res, start = load_or_default(pkl_file, ([], config['worker_id'] * chunk_size))    
    end = (config['worker_id'] + 1) * chunk_size

    # Iterate over your chunk
    logger.debug(f"Starting work over chunk [{start}, {end})...")
    times = []
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
            pickle.dump((res, i), file=open(pkl_file, 'wb'))

    # Save statistics
    local_stats['processing_mean_time']  = mean(times)
    local_stats['processing_total_time'] = sum(times)

    return res

def consolidate_stmts(stmts, pkl_prefix, out_filename):
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

    # Save statements to a json
    statements.stmts_to_json_file(stmts, get_path('json_dir', out_filename))

    # More statistics
    local_stats['consolidation_total_time'] = sum([v for k, v in local_stats.items() if k.startswith('consolidation')])

def dump_local_stats():
    local_stats_df = pd.DataFrame(local_stats, index=[0])
    local_stats_df['worker_id'] = config['worker_id']
    local_stats_df.to_csv(get_path('csv_dir', 'local_stats.csv'), index=False)

def aggregate_local_stats():
    all_stats_dfs = [pd.read_csv(get_path('csv_dir', f'local_stats.csv', wid), index_col=0) for wid in range(config['num_workers'])]
    pd.concat(all_stats_dfs).to_csv(get_path('csv_dir', 'final_stats.csv')) # TODO: add some processing such as taking the mean

def get_stmts_from_jsons():
    jsons = os.listdir(config['json_dir'])
    return [statements.stmts_from_json_file(os.path.join(config['json_dir'], json)) for json in jsons]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='INDRA worker process.')
    parser.add_argument('--num_workers', type=int, required=True, help='Specify the number of workers')
    parser.add_argument('--worker_id',   type=int, required=True, help='Specify the worker id')
    parser.add_argument('--xml_dir',               required=True, help='Specify the xml directory')
    parser.add_argument('--pkl_dir',               required=True, help='Specify the pickle directory')
    parser.add_argument('--json_dir',              required=True, help='Specify the json directory')
    parser.add_argument('--csv_dir',             required=True, help='Specify the statistics directory')
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

    from indra import get_config
    print(get_config('REACHPATH'))
    print(get_config('CLASSPATH'))

    ## 2. Consolidate local statements
    consolidate_stmts(local_stmts, 'consolidation_local', get_path('json_dir', 'intermediate_results.json'))

    ## 3. Dump local stats to CSV file
    dump_local_stats()

    ## 4. Master-only: aggregate workers' results
    if config['worker_id'] == 0:
        all_stmts = get_stmts_from_jsons()
        consolidate_stmts(all_stmts, 'consolidation_final', get_path('json_dir', 'final_results.json')) 

        aggregate_local_stats()
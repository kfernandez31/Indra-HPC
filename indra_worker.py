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
PICKLING_FREQUENCY = 10 # TODO: toggle

local_stats = {}
final_stats = {}
config      = {}

processing_stats = [f"processing_{stat}"    for stat in ['mean', 'total']]
assembly_stats   = [f"consolidation_{stat}" for stat in ['grounding', 'sequence', 'preassembly', 'total']]
df_columns = assembly_stats + processing_stats
stats_df = pd.DataFrame(columns=df_columns)

def pretty_worker_name(wid):
    return f"worker-{wid}"

def get_path(fname, wid):
    return os.path.join(config['output_path'], pretty_worker_name(wid), fname)

def get_own_path(fname):
    return get_path(fname, config['worker_id'])

def load_or_compute(pkl_file, f, *args, **kwargs):
    return pickle.load(open(pkl_file, 'rb')) if os.path.exists(pkl_file) else f(*args, **kwargs)

def timeit(func, *args, **kwargs):
    start_time = time.time()
    result = func(*args, **kwargs)
    end_time = time.time()
    elapsed_time = end_time - start_time
    return elapsed_time, result

def log_info(message, master=False):
    wname = 'MASTER' if master else pretty_worker_name(config['worker_id'])
    logger.info(f"{wname}: {message}")

def get_statements_from_xmls():
    log_info("Obtaining local statements from XMLs...")

    pkl_file = get_own_path('local_statements_progress.pkl')
    xml_files = [f for f in os.listdir(config['input_path']) if f.endswith('.xml')]

    # Process only a [start, end) chunk of the files
    chunk_size = ceil(len(xml_files) / config['num_workers'])
    res, start = load_or_compute(pkl_file, lambda: ([], config['worker_id'] * chunk_size))    
    end = min(len(xml_files), (config['worker_id'] + 1) * chunk_size)
    chunk_size = end - start

    def progress(i):
        return round(100 * ((i + 1) / chunk_size), 2)

    if res != []:
        log_info(f"Resuming work from at {progress(i)}% progress")

    times = []
    for i, xml_file in enumerate(xml_files[start:end]):
        log_info(f"Processing article {xml_file}...")

        xml_file = os.path.join(config['input_path'], xml_file)
        output_json = get_own_path('reach_output.json') # TODO: uncomment the line below if you do not wish the file to get overridden
        # output_json = get_own_path(f'reach_output-{start + i}.json')

        t, rp = timeit(lambda: reach.process_nxml_file(xml_file, offline=True, output_fname=output_json))
        if rp is None:
            logger.fatal(f"{pretty_worker_name(config['worker_id'])}: Failed to obtain Reach processor")
            exit(1)
        elif rp.statements is None:
            logger.error(f"{pretty_worker_name(config['worker_id'])}: Failed to process file {xml_file}")
        else:
            # Extract statements
            res += rp.statements
            times.append(t)
            
        # Periodically save progress
        if (i + 1 - start) % PICKLING_FREQUENCY == 0:
            log_info("Saving progress to pickle file...")
            pickle.dump((res, i), file=open(pkl_file, 'wb'))

        log_info(f"Progress: {i + 1}/{chunk_size} articles ({progress(i)}%)")

    # Save statistics
    local_stats['processing_mean_time']  = mean(times)
    local_stats['processing_total_time'] = sum(times)

    return res

def atomically_io(callback, wid):
    lock_path = get_path('lock', wid=wid)
    while True:
        try:
            with FileLock(lock_path, blocking=True):
                return callback()
        except Timeout: # Lock still under use
            pass

def consolidate_stmts(stmts, master=False):
    phase = ('final' if master else 'local')
    log_info(f"Consolidating {phase} statements...", master=master)
    phase += '_consolidation'

    stats = final_stats if master else local_stats

    def run_stage(stage, callback, *args, **kwargs):
        key = phase + '_' + stage
        pkl_file = get_own_path(key + '.pkl')
        kwargs['save'] = pkl_file
        t, stmts = timeit(load_or_compute, pkl_file, lambda: callback(*args, **kwargs))
        stats[key] = t
        return stmts

    stmts = run_stage('grounding',   ac.map_grounding,   stmts, gilda_mode='local')
    stmts = run_stage('sequence',    ac.map_sequence,    stmts)
    stmts = run_stage('preassembly', ac.run_preassembly, stmts, return_toplevel=False, poolsize=os.cpu_count())

    stats[phase + '_total'] = sum([v for k, v in stats.items() if k.startswith(phase)])

    # Save statements to a json
    json_path = get_own_path(phase + '.json')
    statements.stmts_to_json_file(stmts, json_path)

def collect_local_stats():
    log_info("Aggregating statistics of local processing...", master=True)
    
    def try_read_csv(csv_path):
        if os.path.exists(csv_path) and os.stat(csv_path).st_size > 0:
            return pd.read_csv(csv_path, index_col='worker_id')
        return None

    worker_dfs = [None] * config['num_workers']
    cnt_active = config['num_workers']

    while cnt_active > 0:
        stragglers = [wid for wid in range(config['num_workers']) if worker_dfs[wid] is None]
        log_info(f"Waiting for {cnt_active} workers to finish...", master=True)
        log_info(f"Stragglers: {stragglers}", master=True)

        time.sleep(5) # to not overheat the processor

        for wid in range(config['num_workers']):
            if worker_dfs[wid] is not None:
                continue # Already processed 

            csv_path = get_path('local_consolidation_stats.csv', wid=wid)
            worker_dfs[wid] = atomically_io(lambda: try_read_csv(csv_path), wid=wid)
            if worker_dfs[wid] is not None:
                cnt_active -= 1
                # Lock not needed anymore
                lock_path = get_path('lock', wid=wid)
                os.remove(lock_path)

    return pd.concat(worker_dfs, ignore_index=False)

def dump_local_stats():
    log_info("Dumping statistics of local processing...")
    
    stats_df = pd.DataFrame(local_stats, index=['worker_id'])
    stats_df['worker_id'] = config['worker_id']
    columns_order = ['worker_id'] + [col for col in stats_df.columns if col != 'worker_id']
    stats_df = stats_df[columns_order]

    csv_path = get_own_path('local_consolidation_stats.csv')
    atomically_io(lambda: stats_df.to_csv(csv_path, index=False), wid=config['worker_id'])
    log_info("FINISHED!")

def dump_master_stats(aggregated_stats_df):
    log_info("Dumping statistics of final processing...", master=True)

    aggregated_stats_df.loc['mean'] = aggregated_stats_df.mean()
    aggregated_stats_df.loc['min']  = aggregated_stats_df.min()
    aggregated_stats_df.loc['max']  = aggregated_stats_df.mean()

    csv_path = get_own_path('local_consolidation_stats.csv')
    aggregated_stats_df.to_csv(csv_path, index=True)

    final_stats_df = pd.DataFrame(final_stats, index=[0])
    csv_path = get_own_path('final_consolidation_stats.csv')
    final_stats_df.to_csv(csv_path, index=True)
    log_info("FINISHED!", master=True)

def get_stmts_from_jsons():
    log_info("Extracting local statements from local jsons...", master=True)

    stmts = []
    for wid in range(config['num_workers']):
        wname = pretty_worker_name(wid)
        json_path = get_path('local_consolidation.json', wid=wid)
        stmts += statements.stmts_from_json_file(json_path)

    return stmts

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='INDRA worker process.')
    parser.add_argument('--num_workers', required=True, help="Specify the number of workers", type=int)
    parser.add_argument('--worker_id',   required=True, help="Specify the worker id",         type=int)
    parser.add_argument('--input_path',  required=True, help="Specify the path to the input directory")
    parser.add_argument('--output_path', required=True, help="Specify the path to the output directory")
    args = parser.parse_args()

    config['num_workers'] = args.num_workers
    config['worker_id']   = args.worker_id
    config['input_path']  = args.input_path
    config['output_path'] = args.output_path

    if config['worker_id'] not in range(0, config['num_workers']):
        parser.error("worker_id must lie in the range [0, num_workers)")

    os.makedirs(get_own_path(''), exist_ok=True)

    # THE PIPELINE:

    ## 1. Get local statements from chunk of xmls
    local_stmts = get_statements_from_xmls()

    ## 2. Consolidate local statements
    consolidate_stmts(local_stmts)

    ## 3. Dump local stats to CSV file
    dump_local_stats()

    ## (Master-only)
    if config['worker_id'] == 0:
        config['worker_id'] = 'MASTER'
        os.makedirs(get_own_path(''), exist_ok=True)
        ### 4. Wait for workers to finish, collect their statistics
        collected_stats_df = collect_local_stats()
        
        ### 5. Combine workers' results
        all_stmts = get_stmts_from_jsons()
        consolidate_stmts(all_stmts, master=True)

        ### 6. Dump aggregated statistics to CSV file
        dump_master_stats(collected_stats_df)
        os.rename(get_own_path(''), os.path.join(config['output_path'], 'MASTER'))

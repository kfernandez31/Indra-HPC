from indra                   import literature
from indra.statements        import statements
from indra.sources           import reach
from indra.tools             import assemble_corpus as ac
from indra.pipeline.pipeline import AssemblyPipeline
from collections             import defaultdict
import pickle as pkl
import argparse
import requests
import logging
# import gilda # TODO: remove?
import math
import os

logger = logging.getLogger(__name__)
OFFLINE               = False # True
PICKLING_FREQUENCY    = 1

config = {
    'xml_dir'  : 'xml',
    'json_dir' : 'json',
    'pkl_dir'  : 'pkl',
}

def to_worker_fname(fname):
    return f"worker-{config['worker_id']}:{fname}"

def get_pkl_path(fname):
    return os.path.join(config['pkl_dir'], to_worker_fname(fname) + '.pkl')

def get_json_path(fname):
    return os.path.join(config['json_dir'], to_worker_fname(fname) + '.json')

def load_or_compute(pkl_file, f, *args, **kwargs):
    return pkl.load(open(pkl_file, 'rb')) if os.path.exists(pkl_file) else f(*args, **kwargs)

def load_or_default(pkl_file, default):
    return load_or_compute(pkl_file, lambda: default)

def get_statements_from_xmls():
    pkl_file = get_pkl_path('get_statements_from_xmls')

    xml_files = os.listdir(config['xml_dir'])
    chunk_size = math.ceil(len(xml_files) / config['num_workers'])

    res, start = load_or_default(pkl_file, ([], config['worker_id'] * chunk_size))    
    end = (config['worker_id'] + 1) * chunk_size

    # iterate over your chunk
    for i, xml_file in enumerate(xml_files[start:end]):
        xml_file = os.path.join(config['xml_dir'], xml_file)
        rp = reach.process_nxml_file(xml_file, offline=OFFLINE, output_fname=get_json_path('reach_output.json'))
        res += [rp.statements]

        # periodically save progress
        if (i + 1 - start) % PICKLING_FREQUENCY == 0:
            pkl.dump((res, i), file=open(pkl_file, 'wb'))
    return res

def consolidate_stmts(stmts, pkl_prefix, out_filename):
    # Grounding
    pkl_file = get_pkl_path(pkl_prefix + '_grounding')
    stmts = load_or_compute(pkl_file, ac.map_grounding, stmts, save=pkl_file, gilda_mode='local')

    # Sequence
    pkl_file = get_pkl_path(pkl_prefix + '_sequence')
    stmts = load_or_compute(pkl_file, ac.map_sequence, stmts, save=pkl_file)

    # Preassembly
    pkl_file = get_pkl_path(pkl_prefix + '_preassembly')
    stmts = load_or_compute(pkl_file, ac.run_preassembly, stmts, save=pkl_file, return_toplevel=False, poolsize=os.cpu_count())

    statements.stmts_to_json_file(stmts, get_json_path(out_filename))

    # TODO: write using pipe to zip OR zip & checksum

def get_stmts_from_jsons():
#  indra.statements.statements.stmt_from_json(json_in)
#  indra.statements.statements.stmts_from_json(jsons_in)
    return [] # TODO

# TODO: read_stmts_from_json & AssemblyPipeline::run
# TODO: batch/paper processing time, assembly per paper/total 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='INDRA worker process.')
    parser.add_argument('--num_workers', type=int, required=True, help='Specify the number of workers')
    parser.add_argument('--worker_id',   type=int, required=True, help='Specify the worker id')
    parser.add_argument('--xml_dir',  default=config['xml_dir'],  help='Specify the xml directory')
    parser.add_argument('--pkl_dir',  default=config['pkl_dir'],  help='Specify the pickle directory')
    parser.add_argument('--json_dir', default=config['json_dir'], help='Specify the json directory')
    args = parser.parse_args()

    config['worker_id']   = args.worker_id
    config['num_workers'] = args.num_workers

    if config['worker_id'] not in range(0, config['num_workers']):
        parser.error("worker_id must be from the range [0, num_workers)")

    config['xml_dir']  = args.xml_dir
    config['pkl_dir']  = args.pkl_dir
    config['json_dir'] = args.json_dir

    # THE PIPELINE:

    ## 1. Get own statements from chunk of xmls
    own_stmts = get_statements_from_xmls()

    ## 2. Consolidate own statements
    consolidate_stmts(own_stmts, 'consolidation_1', get_json_path('intermediate_results'))

    ## 3. Master-only: aggregate workers' result
    if config['worker_id'] == 0:
        all_stmts = get_stmts_from_jsons()
        consolidate_stmts(all_stmts, 'consolidation_2', os.path.join(config['json_dir'], 'final_results.json'))

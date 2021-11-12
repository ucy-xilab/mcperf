import argparse
import functools
import logging
import subprocess
import sys
import os

log = logging.getLogger(__name__)

def exec_command(cmd):
    result = subprocess.run(cmd.split(), stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    for l in result.stdout.decode('utf-8').splitlines():
        logging.info(l)
    for l in result.stderr.decode('utf-8').splitlines():
        logging.info(l)
    return result.stdout.decode('utf-8').splitlines()
        
def run_single_experiment(root_results_dir, name, idx, qps):
    time = 120
    results_dir_name = "{}-{}".format(name, idx)
    results_dir_path = os.path.join(root_results_dir, results_dir_name)
    memcached_results_dir_path = os.path.join(results_dir_path, 'memcached')
    exec_command("./profiler.py -n node1 start")
    stdout = exec_command("./memcache-perf/mcperf -s node1 --noload -B -T 40 -Q 1000 -D 4 -C 4 -a node2 -a node3 -a node4 -a node5 -c 4 -q {} -t {}".format(qps, time))    
    exec_command("./profiler.py -n node1 stop")
    exec_command("./profiler.py -n node1 report -d {}".format(memcached_results_dir_path))
    mcperf_results_path_name = os.path.join(results_dir_path, 'mcperf')
    with open(mcperf_results_path_name, 'w') as fo:
        for l in stdout:
            fo.write(l+'\n')

def run_multiple_experiments(root_results_dir, name):
    request_qps = [10000, 50000, 100000, 200000, 300000, 400000, 500000, 1000000, 2000000]
    root_results_dir = os.path.join(root_results_dir, name)
    exec_command("./memcache-perf/mcperf -s node1 --loadonly")
    for q in request_qps:
        instance_name = '-'.join(['qps' + str(q)])
        run_single_experiment(root_results_dir, instance_name, 0, q)

def main(argv):
    logging.getLogger('').setLevel(logging.INFO)
    if len(argv) < 1:
        raise Exception("Experiment name is missing")
    name = argv[0]
    run_multiple_experiments('/users/hvolos01/data', name)

if __name__ == '__main__':
    main(sys.argv[1:])
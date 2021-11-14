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

def run_ansible_playbook(inventory, extravars, playbook, tags=None):
    extravars = ' '.join(extravars)
    if tags:
        tags = '--tags "{}"'.format(tags) 
    else:
        tags = ""
    cmd = 'ansible-playbook -v -i {} -e "{}" {} {}'.format(inventory, extravars, tags, playbook)
    print(cmd)
    r = os.system(cmd)

def run_remote():
    extravars = ['WORKER_THREADS=10', 'MEMORY_LIMIT_MB=16384 PIN_THREADS=true']
    run_ansible_playbook(inventory='hosts', extravars=extravars, playbook='ansible/mcperf.yml', tags='run_memcached,run_agents')

def kill_remote():
    extravars = ['WORKER_THREADS=10', 'MEMORY_LIMIT_MB=16384 PIN_THREADS=true']
    run_ansible_playbook(inventory='hosts', extravars=extravars, playbook='ansible/mcperf.yml', tags='kill_memcached,kill_agents')

def run_single_experiment(root_results_dir, name, idx, qps, records, ia_key_value):
    time = 120
    warmup_qps=1000000
    warmup_time=1
    results_dir_name = "{}-{}".format(name, idx)
    results_dir_path = os.path.join(root_results_dir, results_dir_name)
    memcached_results_dir_path = os.path.join(results_dir_path, 'memcached')
    # prepare memcached and mcperf agents
    kill_remote()
    run_remote()
    exec_command("./memcache-perf/mcperf -s node1 --loadonly -r {} {}".format(records, ia_key_value))
    # warmup run
    stdout = exec_command("./memcache-perf/mcperf -s node1 --noload -B -T 40 -Q 1000 -D 4 -C 4 -a node2 -a node3 -a node4 -a node5 -c 4 -q {} -t {} -r {} {}".format(warmup_qps, warmup_time, records, ia_key_value))    
    # measured run
    exec_command("./profiler.py -n node1 start")
    stdout = exec_command("./memcache-perf/mcperf -s node1 --noload -B -T 40 -Q 1000 -D 4 -C 4 -a node2 -a node3 -a node4 -a node5 -c 4 -q {} -t {} -r {} {}".format(qps, time, records, ia_key_value))    
    exec_command("./profiler.py -n node1 stop")
    exec_command("./profiler.py -n node1 report -d {}".format(memcached_results_dir_path))
    mcperf_results_path_name = os.path.join(results_dir_path, 'mcperf')
    with open(mcperf_results_path_name, 'w') as fo:
        for l in stdout:
            fo.write(l+'\n')

def run_multiple_experiments(root_results_dir, name):
    ia_key_value='--iadist=fb_ia --keysize=fb_key --valuesize=fb_value'
    records=1000000
    request_qps = [10000, 10000, 50000, 100000, 200000, 300000, 400000, 500000, 1000000, 2000000]
    root_results_dir = os.path.join(root_results_dir, name)
    for q in request_qps:
        instance_name = '-'.join(['qps=' + str(q)])
        run_single_experiment(root_results_dir, instance_name, 0, q, records, ia_key_value)

def configure_machine():
    extravars = ['TURBO=false']
    run_ansible_playbook(inventory='hosts', extravars=extravars, playbook='ansible/configure.yml')

def main(argv):
    configure_machine()
    return
    logging.getLogger('').setLevel(logging.INFO)
    if len(argv) < 1:
        raise Exception("Experiment name is missing")
    name = argv[0]
    run_multiple_experiments('/users/hvolos01/data', name)

if __name__ == '__main__':
    main(sys.argv[1:])

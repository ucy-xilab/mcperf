import argparse
import copy
import functools
import logging
import subprocess
import sys
import os
import configparser

import common 

log = logging.getLogger(__name__)


def exec_command(cmd):
    logging.info(cmd)
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

def run_remote(conf):
    extravars = [
        'WORKER_THREADS={}'.format(conf.memcached_worker_threads), 
        'MEMORY_LIMIT_MB={}'.format(conf.memcached_memory_limit_mb), 
        'PIN_THREADS={}'.format(conf.memcached_pin_threads)]
    run_ansible_playbook(
        inventory='hosts', 
        extravars=extravars, 
        playbook='ansible/mcperf.yml', 
        tags='run_memcached,run_agents')

def kill_remote(conf):
    extravars = [
        'WORKER_THREADS={}'.format(conf.memcached_worker_threads), 
        'MEMORY_LIMIT_MB={}'.format(conf.memcached_memory_limit_mb), 
        'PIN_THREADS={}'.format(conf.memcached_pin_threads)]
    run_ansible_playbook(
        inventory='hosts', 
        extravars=extravars, 
        playbook='ansible/mcperf.yml', tags='kill_memcached,kill_agents')

def configure_memcached_node(conf):
    extravars = [
        'TURBO={}'.format(conf.system_turbo)
    ]
    run_ansible_playbook(
        inventory='hosts', 
        extravars=extravars, 
        playbook='ansible/configure.yml')

def agents_list():
    config = configparser.ConfigParser(allow_no_value=True)
    config.read('hosts')
    return [key for key in config['agents']]

def agents_parameter():
    la = ["-a " + a for a in agents_list()]
    return ' '.join(la)

def run_single_experiment(root_results_dir, conf, idx):
    name = conf.shortname()
    results_dir_name = "{}-{}".format(name, idx)
    results_dir_path = os.path.join(root_results_dir, results_dir_name)
    memcached_results_dir_path = os.path.join(results_dir_path, 'memcached')

    # prepare memcached and mcperf agents
    kill_remote(conf)
    run_remote(conf)
    exec_command("./memcache-perf/mcperf -s node1 --loadonly -r {} "
        "--iadist={} --keysize={} --valuesize={}"
        .format(conf.mcperf_records, conf.mcperf_iadist, conf.mcperf_keysize, conf.mcperf_valuesize))

    # do a warmup run
    stdout = exec_command(
        "./memcache-perf/mcperf -s node1 --noload -B -T 40 -Q 1000 -D 4 -C 4 "
        "{} -c 4 -q {} -t {} -r {} " 
        "--iadist={} --keysize={} --valuesize={}"
        .format(agents_parameter(), conf.mcperf_warmup_qps, conf.mcperf_warmup_time, conf.mcperf_records, conf.mcperf_iadist, conf.mcperf_keysize, conf.mcperf_valuesize))    

    # do the measured run
    exec_command("./profiler.py -n node1 start")
    stdout = exec_command(
        "./memcache-perf/mcperf -s node1 --noload -B -T 40 -Q 1000 -D 4 -C 4 "
        "{} -c 4 -q {} -t {} -r {} "
        "--iadist={} --keysize={} --valuesize={}"
        .format(agents_parameter(), conf.mcperf_qps, conf.mcperf_time, conf.mcperf_records, conf.mcperf_iadist, conf.mcperf_keysize, conf.mcperf_valuesize))
    exec_command("./profiler.py -n node1 stop")

    # write statistics 
    exec_command("./profiler.py -n node1 report -d {}".format(memcached_results_dir_path))
    mcperf_results_path_name = os.path.join(results_dir_path, 'mcperf')
    with open(mcperf_results_path_name, 'w') as fo:
        for l in stdout:
            fo.write(l+'\n')

def run_multiple_experiments(root_results_dir, batch_name, batch_conf):
    configure_memcached_node(batch_conf)
    request_qps = [10000, 10000, 50000, 100000, 200000, 300000, 400000, 500000, 1000000, 2000000]
    root_results_dir = os.path.join(root_results_dir, batch_name)
    for qps in request_qps:
        instance_conf = copy.copy(batch_conf)
        instance_conf.set('mcperf_qps', qps)
        run_single_experiment(root_results_dir, instance_conf, 0)

def main(argv):
    batch_conf = common.Configuration({
        'system_turbo': True, 
        'memcached_worker_threads': 10,
        'memcached_memory_limit_mb': 16384,
        'memcached_pin_threads': 'true',
        'mcperf_time': 10,
        'mcperf_warmup_qps': 1000000,
        'mcperf_warmup_time': 1,
        'mcperf_records': 1000000,
        'mcperf_iadist': 'fb_ia',
        'mcperf_keysize': 'fb_key',
        'mcperf_valuesize': 'fb_value'
    })
    logging.getLogger('').setLevel(logging.INFO)
    if len(argv) < 1:
        raise Exception("Experiment name is missing")
    batch_name = argv[0]
    run_multiple_experiments('/users/hvolos01/data', batch_name, batch_conf)

if __name__ == '__main__':
    main(sys.argv[1:])

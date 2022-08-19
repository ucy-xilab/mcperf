import argparse
import copy
import functools
import logging
import subprocess
import sys
import time 
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

def run_ansible_playbook(inventory, extravars=None, playbook=None, tags=None):
    extravars = ' '.join(extravars) if extravars else ''
    if tags:
        tags = '--tags "{}"'.format(tags) 
    else:
        tags = ""
    cmd = 'ansible-playbook -v -i {} -e "{}" {} {}'.format(inventory, extravars, tags, playbook)
    print(cmd)
    r = os.system(cmd)

def run_socwatch(conf,name):
    extravars = [
        'MONITOR_TIME={}'.format("40"),
        'OUTPUT_FILE={}'.format(name)]
    run_ansible_playbook(
        inventory='hosts',
        extravars=extravars,
        playbook='./ansible/profiler.yml',
        tags='run_socwatch')

def run_socwatch_io(conf,name):
    extravars = [
        'OUTPUT_FILE={}'.format(name)]
    run_ansible_playbook(
        inventory='hosts',
        extravars=extravars,
        playbook='./ansible/profiler.yml',
        tags='run_socwatch_io')


def set_uncore_freq(conf, freq_mhz):
    freq_hex=format(freq_mhz//100, 'x')
    msr_val = "0x{}{}".format(freq_hex, freq_hex) 
    
    extravars = [
       'MSR_VALUE={}'.format(msr_val)]
    run_ansible_playbook(
       inventory='hosts', 
       extravars=extravars, 
       playbook='ansible/configure.yml')

def set_core_freq(conf, freq_mhz):
    extravars = [
       'CORE_FREQ={}MHz'.format(freq_mhz)]
    run_ansible_playbook(
       inventory='hosts', 
       extravars=extravars, 
       playbook='ansible/configure_core_freq.yml')

def run_profiler(conf):
    run_ansible_playbook(
        inventory='hosts', 
        playbook='ansible/profiler.yml', 
        tags='run_profiler')

def kill_profiler(conf):
    run_ansible_playbook(
        inventory='hosts', 
        playbook='ansible/profiler.yml', 
        tags='kill_profiler')

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

def host_is_reachable(host):
  return True if os.system("ping -c 1 {}".format(host)) == 0 else False

def memcached_node():
    config = configparser.ConfigParser(allow_no_value=True)
    config.read('hosts')
    node = list(config['memcached'].items())
    if len(node) > 1:
        raise Exception('Do not support multiple memcached nodes')
    return node[0][0]

def wait_for_remote_node(node):
    while not host_is_reachable(node):
        logging.info('Waiting for remote host {}...'.format(node))
        time.sleep(30)
        pass

def configure_memcached_node(conf):
    node = memcached_node()
    print('ssh -n {} "cd ~/mcperf; sudo python3 configure.py -v --turbo={} --kernelconfig={} -v"'.format(node, conf['turbo'], conf['kernelconfig']))
    rc = os.system('ssh -n {} "cd ~/mcperf; sudo python3 configure.py -v --turbo={} --kernelconfig={} -v"'.format(node, conf['turbo'], conf['kernelconfig']))
    exit_status = rc >> 8 
    if exit_status == 2:
        logging.info('Rebooting remote host {}...'.format(node))
        os.system('ssh -n {} "sudo shutdown -r now"'.format(node))
        logging.info('Waiting for remote host {}...'.format(node))
        time.sleep(30)
        while not host_is_reachable(node):
            logging.info('Waiting for remote host {}...'.format(node))
            time.sleep(30)
            pass
        os.system('ssh -n {} "cd ~/mcperf; sudo python3 configure.py -v --turbo={} --kernelconfig={} -v"'.format(node, conf['turbo'], conf['kernelconfig']))

def agents_list():
    config = configparser.ConfigParser(allow_no_value=True)
    config.read('hosts')
    return [key for key in config['agents']]

def agents_parameter():
    la = ["-a " + a for a in agents_list()]
    return ' '.join(la)

def run_single_experiment(root_results_dir, name_prefix, conf, idx):
    name = name_prefix + conf.shortname()
    results_dir_name = "{}-{}".format(name, idx)
    results_dir_path = os.path.join(root_results_dir, results_dir_name)
    memcached_results_dir_path = os.path.join(results_dir_path, 'memcached')

    # cleanup any processes left by a previous run
    kill_profiler(conf)
    kill_remote(conf)

    # prepare profiler, memcached, and mcperf agents
    run_profiler(conf)
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
    run_socwatch(conf,results_dir_name)
    run_socwatch_io(conf,results_dir_name)
    stdout = exec_command(
        "./memcache-perf/mcperf -s node1 --noload -B -T 40 -Q 1000 -D 4 -C 4 "
        "{} -c 4 -q {} -t {} -r {} "
        "--iadist={} --keysize={} --valuesize={}"
        .format(agents_parameter(), conf.mcperf_qps, conf.mcperf_time, conf.mcperf_records, conf.mcperf_iadist, conf.mcperf_keysize, conf.mcperf_valuesize))
    exec_command("./profiler.py -n node1 stop")

    #check if socwatch is still processing
    active_socwatch=exec_command("/users/ganton12/mcperf/scripts/check-socwatch-status.sh node1")
    while (int(active_socwatch[0]) > 2):
       time.sleep(30)
       active_socwatch=exec_command("/users/ganton12/mcperf/scripts/check-socwatch-status.sh node1")

    exec_command("python3 ./profiler.py -n node1 report -d {}".format(memcached_results_dir_path))

    mcperf_results_path_name = os.path.join(results_dir_path, 'mcperf')
    with open(mcperf_results_path_name, 'w') as fo:
        for l in stdout:
            fo.write(l+'\n')

    # write statistics 
    exec_command("./profiler.py -n node1 report -d {}".format(memcached_results_dir_path))
    mcperf_results_path_name = os.path.join(results_dir_path, 'mcperf')
    with open(mcperf_results_path_name, 'w') as fo:
        for l in stdout:
            fo.write(l+'\n')

    # cleanup
    kill_remote(conf)
    kill_profiler(conf)


def run_multiple_experiments_with_varying_freq(root_results_dir, batch_name, system_conf, batch_conf, iter):
    configure_memcached_node(system_conf)
    name_prefix = "turbo={}-kernelconfig={}-".format(system_conf['turbo'], system_conf['kernelconfig'])
    request_qps = [10000, 50000, 100000, 200000, 300000, 400000, 500000]
    root_results_dir = os.path.join(root_results_dir, batch_name)
    set_uncore_freq(system_conf, 1600)
    for freq in [1400, 1600, 1800, 2000, 2200, 2400]:
        set_core_freq(system_conf, freq)
        for qps in request_qps:
            instance_conf = copy.copy(batch_conf)
            instance_conf.set('mcperf_qps', qps)
            instance_conf.set('memcached_freq', freq)
            run_single_experiment(root_results_dir, name_prefix, instance_conf, iter)

def run_multiple_experiments(root_results_dir, batch_name, system_conf, batch_conf, iter):
    configure_memcached_node(system_conf)
    name_prefix = "turbo={}-kernelconfig={}-".format(system_conf['turbo'], system_conf['kernelconfig'])
    #request_qps = [10000, 50000, 100000, 200000, 300000, 400000, 500000, 1000000, 2000000]
    #request_qps = [10000, 50000, 100000, 200000, 300000, 400000, 500000, 600000, 700000, 800000]
    request_qps = [10000, 50000, 100000, 200000, 300000, 400000, 500000]
    root_results_dir = os.path.join(root_results_dir, batch_name)
    set_uncore_freq(system_conf, 2000)
    for qps in request_qps:
        instance_conf = copy.copy(batch_conf)
        instance_conf.set('mcperf_qps', qps)
        run_single_experiment(root_results_dir, name_prefix, instance_conf, iter)



def main(argv):
    system_confs = [
##        {'turbo': True,  'kernelconfig': 'vanilla'},
##        {'turbo': False,  'kernelconfig': 'vanilla'},
#         {'turbo': False, 'kernelconfig': 'baseline'},
#         {'turbo': False, 'kernelconfig': 'disable_c6'},
#         {'turbo': True, 'kernelconfig': 'baseline'},
         {'turbo': False, 'kernelconfig': 'disable_cstates'},
##         {'turbo': False, 'kernelconfig': 'disable_c6'},
#         {'turbo': True, 'kernelconfig': 'disable_c6'},
#         {'turbo': False, 'kernelconfig': 'disable_c1e_c6'},
#         {'turbo': True, 'kernelconfig': 'disable_c1e_c6'},
##         {'turbo': False, 'kernelconfig': 'quick_c1'},
##         {'turbo': True, 'kernelconfig': 'quick_c1'},
##         {'turbo': False, 'kernelconfig': 'quick_c1_disable_c6'},
##         {'turbo': True, 'kernelconfig': 'quick_c1_disable_c6'},
##         {'turbo': False, 'kernelconfig': 'quick_c1_c1e'},
##         {'turbo': True, 'kernelconfig': 'quick_c1_c1e'},
##         {'turbo': True, 'kernelconfig': 'disable_cstates'},
    ]
    batch_conf = common.Configuration({
        'memcached_worker_threads': 10,
        'memcached_memory_limit_mb': 16384,
        'memcached_pin_threads': 'true',
        'mcperf_time': 120,
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
    for iter in range(0, 3):
        for system_conf in system_confs:
            run_multiple_experiments('/users/hvolos01/data', batch_name, system_conf, batch_conf, iter)

if __name__ == '__main__':
    main(sys.argv[1:])

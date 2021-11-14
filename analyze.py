import ast 
import os
import re
import sys
import matplotlib.pyplot as plt

def derive_datatype(datastr):
    try:
        return type(ast.literal_eval(datastr))
    except:
        return type("")

def parse_mcperf_stats(mcperf_results_path):
    stats = None
    with open(mcperf_results_path, 'r') as f:
        stats = {}
        for l in f:
            if l.startswith('#type'):
                stat_names = l.split()[1:]
                read_stats = next(f).split()[1:]
                update_stats = next(f).split()[1:]
                read_stats_dict = {}
                update_stats_dict = {}
                for i, stat_name in enumerate(stat_names):
                    read_stats_dict[stat_name] = float(read_stats[i])
                    update_stats_dict[stat_name] = float(update_stats[i])
                stats['read'] = read_stats_dict
                stats['update'] = update_stats_dict
    return stats

def read_timeseries(filepath):
    header = None
    timeseries = None
    with open(filepath, 'r') as f:
        header = f.readline().strip()
        timeseries = []
        data = f.readline().strip().split(',')
        datatype = derive_datatype(data[1])
        f.seek(0)
        for l in f.readlines()[1:]:
            data = l.strip().split(',')
            timestamp = int(data[0])
            value = datatype(data[1])
            timeseries.append((timestamp, value))
    return (header, timeseries)            

def add_metric_to_dict(stats_dict, metric_name, metric_value):
    head = metric_name.split('.')[0]
    tail = metric_name.split('.')[1:]
    if tail:
        stats_dict = stats_dict.setdefault(head, {})
        add_metric_to_dict(stats_dict, '.'.join(tail)   , metric_value)
    else:
        stats_dict[head] = metric_value

def parse_cstate_stats(stats_dir):
    stats = {}
    prog = re.compile('(.*)\.(.*)\.(.*)')
    for f in os.listdir(stats_dir):
        m = prog.match(f)
        if m:
            stats_file = os.path.join(stats_dir, f)
            cpu_id = m.group(0)
            state_name = m.group(1)
            metric_name = m.group(2)
            (metric_name, timeseries) = read_timeseries(stats_file)
            add_metric_to_dict(stats, metric_name, timeseries)
    return stats

def parse_single_instance_stats(stats_dir):
    stats = {}
    server_stats_dir = os.path.join(stats_dir, 'memcached')
    server_cstate_stats = parse_cstate_stats(server_stats_dir)
    stats['server'] = server_cstate_stats
    mcperf_stats_file = os.path.join(stats_dir, 'mcperf')
    stats['mcperf'] = parse_mcperf_stats(mcperf_stats_file)
    return stats

def parse_multiple_instances_stats(stats_dir, pattern='.*'):
    stats = {}
    for f in os.listdir(stats_dir):
        instance_dir = os.path.join(stats_dir, f)
        stats[f] = parse_single_instance_stats(instance_dir)
    return stats

def cpu_state_time_perc(data, cpu_id):
    cpu_str = "CPU{}".format(cpu_id)
    state_names = ['POLL', 'C1', 'C1E', 'C6']
    state_time_perc = []
    total_state_time = 0
    time_us = 0
    for state_name in state_names:
        (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
        (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
        time_us = max(time_us, (ts_end - ts_start) * 1000000.0)
        total_state_time += val_end - val_start

    time_us = max(time_us, total_state_time)
    for state_name in state_names:
        (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
        (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
        state_time_perc.append((val_end-val_start)/time_us)
    # calculate C0 
    state_time_perc[0] = 1 - sum(state_time_perc[1:4])
    state_names[0] = 'C0' 
    return state_time_perc

def avg_state_time_perc(stats, cpu_id_list):
    total_state_time_perc = [0]*4
    cpu_count = 0
    for cpud_id in cpu_id_list:
        cpu_count += 1
        total_state_time_perc = [a + b for a, b in zip(total_state_time_perc, cpu_state_time_perc(stats, cpud_id))]
    avg_state_time_perc = [a/b for a, b in zip(total_state_time_perc, [cpu_count]*len(total_state_time_perc))]
    return avg_state_time_perc

def shortname(qps, turbo):
    l = []
    l.append('qps={}'.format(qps))
    l.append('turbo={}'.format(turbo))
    l.append('0')
    return '-'.join(l)

def plot_residency_per_qps(stats, qps_list, turbo):
    bars = []
    labels = []
    state_names = ['C0', 'C1', 'C1E', 'C6']
    for qps in qps_list:
        instance_name = shortname(qps, turbo)
        time_perc = avg_state_time_perc(stats[instance_name]['server'], range(0, 10))
    
        labels.append(str(int(qps/1000))+'K')
        bar = []
        for state_id in range(0, len(state_names)):
            bar.append(time_perc[state_id])
        bars.append(bar)
        print(bar)
    
    width = 0.35       # the width of the bars: can also be len(x) sequence
        
    fig, ax = plt.subplots()

    bottom = [0] * len(bars)
    for state_id, state_name in enumerate(state_names):
        vals = []
        for bar in bars:
            vals.append(bar[state_id])
        ax.bar(labels, vals, width, label=state_name, bottom=bottom)
        for i, val in enumerate(vals):
            bottom[i] += val    

    ax.set_ylabel('C-State Residency (fraction)')
    ax.set_xlabel('Request Rate (QPS)')
    ax.legend()

    plt.show()

def plot_latency_per_qps(stats, qps_list, turbo_list):
    axis_scale = 0.001
    for turbo in turbo_list:
        read_avg = []
        read_p99 = []
        extra_params = 'turbo={}'.format(turbo)
        for qps in qps_list:
            instance_name = shortname(qps, turbo)
            mcperf_stats = stats[instance_name]['mcperf']
            read_avg.append(mcperf_stats['read']['avg'])
            read_p99.append(mcperf_stats['read']['p99'])

        fig, ax = plt.subplots()
        qps_list = [q *axis_scale for q in qps_list]
        plt.plot(qps_list, read_avg, label='read avg - {}'.format(extra_params))
        plt.plot(qps_list, read_p99, label='read p99 - {}'.format(extra_params))

    ax.set_ylabel('Latency (us)')
    ax.set_xlabel('Request Rate (KQPS)')
    ax.legend()

    plt.show()

def plot_power_per_qps(stats, qps_list, turbo_list):
    axis_scale = 0.001
    for turbo in turbo_list:
        power = []
        extra_params = 'turbo={}'.format(turbo)
        for qps in qps_list:
            instance_name = shortname(qps, turbo)
            system_stats = stats[instance_name]['server']
            for k in system_stats.keys():
                print(k)
            print(system_stats['power/energy-pkg/'])
            read_avg.append(mcperf_stats['read']['avg'])

        fig, ax = plt.subplots()
        qps_list = [q *axis_scale for q in qps_list]
        plt.plot(qps_list, power, label=extra_params)

    ax.set_ylabel('Power (W)')
    ax.set_xlabel('Request Rate (KQPS)')
    ax.legend()

    plt.show()

def main(argv):
    stats_root_dir = argv[1]
    stats = parse_multiple_instances_stats(stats_root_dir)
    qps_list = [10000, 50000, 100000, 200000, 300000, 400000, 500000, 1000000, 2000000]
    turbo_list = [True]
    #plot_residency_per_qps(stats, qps_list, turbo_list[0])
    #plot_latency_per_qps(stats, qps_list, turbo_list)
    plot_power_per_qps(stats, qps_list, turbo_list)

if __name__ == '__main__':
    main(sys.argv)

import ast
import os
import re
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf

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
            if l.startswith('Total QPS'):
                stats['total_qps'] = float(l.split()[3])
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

def parse_perf_stats(stats_dir):
    stats = {}
    prog = re.compile('(.*)\.(.*)\.(.*)')
    for f in os.listdir(stats_dir):
        m = prog.match(f)
        if not m:
            stats_file = os.path.join(stats_dir, f)
            (metric_name, timeseries) = read_timeseries(stats_file)
            add_metric_to_dict(stats, metric_name, timeseries)
    return stats

def parse_single_instance_stats(stats_dir):
    stats = {}
    server_stats_dir = os.path.join(stats_dir, 'memcached')
    server_cstate_stats = parse_cstate_stats(server_stats_dir)
    server_perf_stats = parse_perf_stats(server_stats_dir)
    stats['server'] = {**server_cstate_stats, **server_perf_stats}
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
    # determine time window of measurements
    for state_name in state_names:
        if state_name in data[cpu_str]:
            (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
            (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
            time_us = max(time_us, (ts_end - ts_start) * 1000000.0)
            total_state_time += val_end - val_start    
    time_us = max(time_us, total_state_time)
    # calculate percentage
    for state_name in state_names:
        if state_name in data[cpu_str]:
            (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
            (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
            state_time_perc.append((val_end-val_start)/time_us)
    # calculate C0 as the remaining time 
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

def system_conf_shortname(system_conf):
    l = [
        'turbo={}'.format(system_conf['turbo']),
        'kernelconfig={}'.format(system_conf['kernelconfig']),
    ]
    return '-'.join(l) + '-'

def shortname(qps=None):
    l = []
    if qps:
        l.append('qps={}'.format(qps))
    l.append('0')
    return '-'.join(l)

def plot_residency_per_target_qps(stats, system_conf, qps_list):
    bars = []
    labels = []
    state_names = ['C0']
    check_state_names = ['C1', 'C1E', 'C6']
    for state_name in check_state_names:
        instance_name = system_conf_shortname(system_conf) + shortname('10000')
        if state_name in stats[instance_name]['server']['CPU0']:
            state_names.append(state_name)
    for qps in qps_list:
        instance_name = system_conf_shortname(system_conf) + shortname(qps)
        time_perc = avg_state_time_perc(stats[instance_name]['server'], range(0, 10))
    
        labels.append(str(int(qps/1000))+'K')
        bar = []
        for state_id in range(0, len(state_names)):
            bar.append(time_perc[state_id])
        bars.append(bar)
    
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
    plt.title(system_conf_shortname(system_conf))
    #plt.show()
    return fig

def plot_latency_per_target_qps(stats, system_confs, qps_list):
    axis_scale = 0.001
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    for system_conf in system_confs:
        read_avg = []
        read_p99 = []
        extra_params = system_conf_shortname(system_conf)
        for qps in qps_list:
            instance_name = system_conf_shortname(system_conf) + shortname(qps)
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

    return fig

def plot_qps_per_target_qps(stats, system_confs, qps_list):
    axis_scale = 0.001
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    for system_conf in system_confs:
        total_qps = []
        extra_params = system_conf_shortname(system_conf)
        for qps in qps_list:
            instance_name = system_conf_shortname(system_conf) + shortname(qps)
            mcperf_stats = stats[instance_name]['mcperf']
            total_qps.append(mcperf_stats['total_qps'])

        fig, ax = plt.subplots()
        qps_list = [q *axis_scale for q in qps_list]
        total_qps = [q *axis_scale for q in total_qps]
        plt.plot(qps_list, total_qps, label='total qps - {}'.format(extra_params))

    ax.set_ylabel('Total Rate (KQPS)')
    ax.set_xlabel('Request Rate (KQPS)')
    ax.legend()

    return fig


def avg_power(timeseries):
    total_val = 0
    for (ts, val) in timeseries:
        total_val += val
    time = timeseries[-1][0] - timeseries[0][0]
    return total_val / time

def plot_power_per_target_qps(stats, system_confs, qps_list):
    axis_scale = 0.001
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    for system_conf in system_confs:
        power = []
        extra_params = system_conf_shortname(system_conf)
        for qps in qps_list:
            instance_name = system_conf_shortname(system_conf) + shortname(qps)
            system_stats = stats[instance_name]['server']
            power.append(avg_power(system_stats['power/energy-pkg/']))

        fig, ax = plt.subplots()
        qps_list = [q *axis_scale for q in qps_list]
        plt.plot(qps_list, power, label=extra_params)

    ax.set_ylabel('Power (W)')
    ax.set_xlabel('Request Rate (KQPS)')
    ax.legend()
    
    return fig

def main(argv):
    interactive = False
    stats_root_dir = argv[1]
    stats = parse_multiple_instances_stats(stats_root_dir)
    system_confs = [
        {'turbo': False, 'kernelconfig': 'baseline'},
        {'turbo': False, 'kernelconfig': 'disable_cstates'},
        {'turbo': False, 'kernelconfig': 'disable_c6'},
        {'turbo': False, 'kernelconfig': 'quick_c1'},
        {'turbo': False, 'kernelconfig': 'quick_c1_disable_c6'},
        {'turbo': False, 'kernelconfig': 'quick_c1_c1e'},
    ]
    qps_list = [10000, 50000, 100000, 200000, 300000, 400000, 500000, 1000000, 2000000]

    pdf = matplotlib.backends.backend_pdf.PdfPages("output.pdf")
    for system_conf in system_confs:
        firstPage = plt.figure()
        firstPage.clf()
        txt = system_conf_shortname(system_conf)
        firstPage.text(0.5,0.5, txt, transform=firstPage.transFigure, size=14, ha="center")
        pdf.savefig(firstPage)
        plt.close()
        if system_conf['kernelconfig'] != 'disable_cstates':
            fig1 = plot_residency_per_target_qps(stats, system_conf, qps_list)
            pdf.savefig(fig1)
        fig2 = plot_qps_per_target_qps(stats, system_conf, qps_list)
        pdf.savefig(fig2)
        fig3 = plot_latency_per_target_qps(stats, system_conf, qps_list)
        pdf.savefig(fig3)
        fig4 = plot_power_per_target_qps(stats, system_conf, qps_list)
        pdf.savefig(fig4)
        if interactive:
            plt.show()
        plt.close()
    pdf.close()

if __name__ == '__main__':
    main(sys.argv)

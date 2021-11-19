import ast
import copy
import csv
import os
import re
import statistics
import sys
import matplotlib.pyplot as plt
import matplotlib.backends.backend_pdf

def derive_datatype(datastr):
    try:
        return type(ast.literal_eval(datastr))
    except:
        return type("")

def system_conf_fullname(system_conf):
    l = [
        'turbo={}'.format(system_conf['turbo']),
        'kernelconfig={}'.format(system_conf['kernelconfig']),
    ]
    return '-'.join(l) + '-'

def system_conf_shortname(system_conf):
    short_kernelconfig = {
        'baseline': 'baseline',
        'disable_cstates': 'no_cstates',
        'disable_c6': 'no_c6',
        'disable_c1e_c6': 'no_c1e_c6',
        'quick_c1': 'q_c1',
        'quick_c1_c1e': 'q_c1_c1e',
        'quick_c1_disable_c6': 'q_c1-no_c6',
    }
    l = [
        'T' if system_conf['turbo'] else 'NT',
        short_kernelconfig[system_conf['kernelconfig']]
    ]
    return '-'.join(l) + '-'

def shortname(qps=None):
    return 'qps={}'.format(qps)

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
        add_metric_to_dict(stats_dict, '.'.join(tail), metric_value)
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
        instance_name = f[:f.rfind('-')]
        stats.setdefault(instance_name, []).append(parse_single_instance_stats(instance_dir))
    return stats

def cpu_state_time_perc_OBSOLETE(data, cpu_id):
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

def avg_state_time_perc_OBSOLETE(stats, cpu_id_list):
    total_state_time_perc = [0]*4
    cpu_count = 0
    for cpud_id in cpu_id_list:
        cpu_count += 1
        total_state_time_perc = [a + b for a, b in zip(total_state_time_perc, cpu_state_time_perc_OBSOLETE(stats, cpud_id))]
    avg_state_time_perc = [a/b for a, b in zip(total_state_time_perc, [cpu_count]*len(total_state_time_perc))]
    return avg_state_time_perc

def cpu_state_time_perc(data, cpu_id):
    cpu_str = "CPU{}".format(cpu_id)
    state_names = ['POLL', 'C1', 'C1E', 'C6']
    state_time_perc = []
    total_state_time = 0
    time_us = 0
    # FIXME: time duration is currently hardcoded 
    # determine time window of measurements
    for state_name in state_names:
        if state_name in data[cpu_str]:
            (ts_start, val_start) = data[cpu_str][state_name]['time'][0]
            (ts_end, val_end) = data[cpu_str][state_name]['time'][-1]
            time_us = max(time_us, (ts_end - ts_start) * 1000000.0)
            total_state_time += val_end - val_start    
    time_us = max(time_us, total_state_time)
    print(time_us)

def avg_state_time_perc(stats, cpu_id_list):
    for stat in stats:
        total_state_time_perc = [0]*4
        cpu_count = 0
        for cpud_id in cpu_id_list:
            cpu_count += 1
            total_state_time_perc = [a + b for a, b in zip(total_state_time_perc, cpu_state_time_perc(stats, cpud_id))]
        avg_state_time_perc = [a/b for a, b in zip(total_state_time_perc, [cpu_count]*len(total_state_time_perc))]
    return avg_state_time_perc

def get_residency_per_target_qps(stats, system_conf, qps_list):
    bars = []
    labels = []
    # determine used C-states
    state_names = ['C0']
    check_state_names = ['C1', 'C1E', 'C6']
    for state_name in check_state_names:
        instance_name = system_conf_fullname(system_conf) + shortname('10000')
        if state_name in stats[instance_name][0]['server']['CPU0']:
            state_names.append(state_name)
    raw = []
    raw.append(['State'] + [str(q) for q in qps_list])
    for state_id in range(0, len(state_names)):
        row = [state_names[state_id]]
        for qps in qps_list:
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            #for stat in stats[instance_name]:
            stat = stats[instance_name][0]
            time_perc = avg_state_time_perc_OBSOLETE(stat['server'], range(0, 10))
            row.append(time_perc[state_id])
        raw.append(row)
    return raw

def plot_residency_per_target_qps(stats, system_conf, qps_list):
    raw = get_residency_per_target_qps(stats, system_conf, qps_list)
    width = 0.35        
    fig, ax = plt.subplots()
    header_row = raw[0]
    bottom = [0] * len(header_row[1:])
    labels = [str(int(int(c)/1000))+'K' for c in header_row[1:]]
    for row in raw[1:]:
        state_name = row[0]
        vals = [float(c) for c in row[1:]]
        ax.bar(labels, vals, width, label=state_name, bottom=bottom)
        for i, val in enumerate(vals):
            bottom[i] += val    
    ax.set_ylabel('C-State Residency (fraction)')
    ax.set_xlabel('Request Rate (QPS)')
    ax.legend()
    plt.title(system_conf_fullname(system_conf))
    return fig

def get_latency_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'read_avg_avg') 
        header_row.append(system_conf_shortname(system_conf) + 'read_avg_std') 
        header_row.append(system_conf_shortname(system_conf) + 'read_p99_avg') 
        header_row.append(system_conf_shortname(system_conf) + 'read_p99_std') 
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            read_avg = []
            read_p99 = []
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                mcperf_stats = stat['mcperf']
                read_avg.append(mcperf_stats['read']['avg'])
                read_p99.append(mcperf_stats['read']['p99'])
            row.append(str(statistics.mean(read_avg)))
            row.append(str(statistics.stdev(read_avg)) if len(read_avg) > 1 else 'N/A')
            row.append(str(statistics.mean(read_p99)))
            row.append(str(statistics.stdev(read_p99)) if len(read_p99) > 1 else 'N/A')
        raw.append(row)
    return raw

def column_matches(filter, column_name):
    for f in filter:
        if f in column_name:
            return True
    return False

def plot_latency_per_target_qps(stats, system_confs, qps_list, filter=None):
    axis_scale = 0.001
    axis_qps_list = [q *axis_scale for q in qps_list]
    fig, ax = plt.subplots()
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = get_latency_per_target_qps(stats, system_confs, qps_list)
    header_row = raw[0]
    data_rows = raw[1:]
    for i, y_column_name in enumerate(header_row[1::2]):
        if filter and not column_matches(filter, y_column_name):
            continue
        y_vals = []
        y_vals_err = []
        y_column_id = 1 + i * 2
        for row_id, row in enumerate(data_rows):
            y_vals.append(float(data_rows[row_id][y_column_id]))
            y_val_err = data_rows[row_id][y_column_id+1] 
            y_vals_err.append(float(y_val_err) if y_val_err != 'N/A' else 0)
        plt.errorbar(axis_qps_list, y_vals, yerr = y_vals_err, label=y_column_name)

    ax.set_ylabel('Latency (us)')
    ax.set_xlabel('Request Rate (KQPS)')
    ax.legend(loc='upper left')

    return fig

def get_total_qps_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'Total-QPS-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'Total-QPS-std') 
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            total_qps = []
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                mcperf_stats = stat['mcperf']
                total_qps.append(mcperf_stats['total_qps'])
            row.append(str(statistics.mean(total_qps)))
            row.append(str(statistics.stdev(total_qps)) if len(total_qps) > 1 else 'N/A')
        raw.append(row)
    return raw

def plot_total_qps_per_target_qps(stats, system_confs, qps_list):
    axis_scale = 0.001
    fig, ax = plt.subplots()
    axis_qps_list = [q *axis_scale for q in qps_list]
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    for system_conf in system_confs:
        total_qps = []
        extra_params = system_conf_shortname(system_conf)
        for qps in qps_list:
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            mcperf_stats = stats[instance_name]['mcperf']
            total_qps.append(mcperf_stats['total_qps'])

        total_qps = [q *axis_scale for q in total_qps]
        plt.plot(axis_qps_list, total_qps, label='total qps - {}'.format(extra_params))

    ax.set_ylabel('Total Rate (KQPS)')
    ax.set_xlabel('Request Rate (KQPS)')
    ax.legend(loc='lower right')

    return fig

def avg_power(timeseries):
    total_val = 0
    for (ts, val) in timeseries:
        total_val += val
    time = timeseries[-1][0] - timeseries[0][0]
    return total_val / time

def get_power_per_target_qps(stats, system_confs, qps_list):
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    raw = []
    header_row = []
    header_row.append('QPS')
    for system_conf in system_confs:
        header_row.append(system_conf_shortname(system_conf) + 'power-pkg-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'power-pkg-std') 
        header_row.append(system_conf_shortname(system_conf) + 'power-ram-avg') 
        header_row.append(system_conf_shortname(system_conf) + 'power-ram-std') 
    raw.append(header_row)
    for i, qps in enumerate(qps_list):
        row = [str(qps)]
        for system_conf in system_confs:
            power_pkg = []
            power_ram = []
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            for stat in stats[instance_name]:
                system_stats = stat['server']
                power_pkg.append(avg_power(system_stats['power/energy-pkg/']))
                power_ram.append(avg_power(system_stats['power/energy-ram/']))
            row.append(str(statistics.mean(power_pkg)))
            row.append(str(statistics.stdev(power_pkg)) if len(power_pkg) > 1 else 'N/A' )
            row.append(str(statistics.mean(power_ram)))
            row.append(str(statistics.stdev(power_ram)) if len(power_ram) > 1 else 'N/A')
        raw.append(row)
    return raw

def plot_power_per_target_qps(stats, system_confs, qps_list):
    axis_scale = 0.001
    axis_qps_list = [q *axis_scale for q in qps_list]
    if not isinstance(system_confs, list):
        system_confs = [system_confs]
    fig, ax = plt.subplots()
    for system_conf in system_confs:
        pkg_power = []
        ram_power = []
        extra_params = system_conf_shortname(system_conf)
        for qps in qps_list:
            instance_name = system_conf_fullname(system_conf) + shortname(qps)
            system_stats = stats[instance_name]['server']
            pkg_power.append(avg_power(system_stats['power/energy-pkg/']))
            ram_power.append(avg_power(system_stats['power/energy-ram/'])) 
        plt.plot(axis_qps_list, pkg_power, label='pkg power - {}'.format(extra_params))
        plt.plot(axis_qps_list, ram_power, label='ram power - {}'.format(extra_params))

    ax.set_ylabel('Power (W)')
    ax.set_xlabel('Request Rate (KQPS)')
    ax.legend(loc='lower right')

def write_csv(filename, rows):
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',',
                                quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for row in rows:
            writer.writerow(row)    

def write_csv_all(stats, system_confs, qps_list):
    for system_conf in system_confs:
        if system_conf['kernelconfig'] != 'disable_cstates':
            raw1 = get_residency_per_target_qps(stats, system_conf, qps_list)
            write_csv(system_conf_fullname(system_conf) + 'residency_per_target_qps' + '.csv', raw1)
        raw2 = get_total_qps_per_target_qps(stats, system_conf, qps_list)
        write_csv(system_conf_fullname(system_conf) + 'total_qps_per_target_qps' + '.csv', raw2)
        raw3 = get_latency_per_target_qps(stats, system_conf, qps_list)
        write_csv(system_conf_fullname(system_conf) + 'latency_per_target_qps' + '.csv', raw3)
        raw4 = get_power_per_target_qps(stats, system_conf, qps_list)
        write_csv(system_conf_fullname(system_conf) + 'power_per_target_qps' + '.csv', raw4)

def filter_system_confs(system_confs, turbo):
    turbo_system_confs = []
    for s in system_confs:
        if s['turbo'] == turbo:
            turbo_system_confs.append(s)
    return turbo_system_confs

def write_latency_to_single_csv(stats, system_confs, qps_list):
    turbo_system_confs = filter_system_confs(system_confs, turbo=True)
    turbo_raw = get_latency_per_target_qps(stats, turbo_system_confs, qps_list)
    noturbo_system_confs = filter_system_confs(system_confs, turbo=False)
    noturbo_raw = get_latency_per_target_qps(stats, noturbo_system_confs, qps_list)
    write_csv('all_latency_per_target_qps' + '.csv', turbo_raw + noturbo_raw)

def write_power_to_single_csv(stats, system_confs, qps_list):
    turbo_system_confs = filter_system_confs(system_confs, turbo=True)
    turbo_raw = get_power_per_target_qps(stats, turbo_system_confs, qps_list)
    noturbo_system_confs = filter_system_confs(system_confs, turbo=False)
    noturbo_raw = get_power_per_target_qps(stats, noturbo_system_confs, qps_list)
    write_csv('all_power_per_target_qps' + '.csv', turbo_raw + [] + noturbo_raw)

def write_total_qps_to_single_csv(stats, system_confs, qps_list):
    turbo_system_confs = filter_system_confs(system_confs, turbo=True)
    turbo_raw = get_total_qps_per_target_qps(stats, turbo_system_confs, qps_list)
    noturbo_system_confs = filter_system_confs(system_confs, turbo=False)
    noturbo_raw = get_total_qps_per_target_qps(stats, noturbo_system_confs, qps_list)
    write_csv('all_total_qps_per_target_qps' + '.csv', turbo_raw + noturbo_raw)

def plot_stack(stats, system_confs, qps_list, interactive=True):
    pdf = matplotlib.backends.backend_pdf.PdfPages("all.pdf")
    for system_conf in system_confs:
        if system_conf['kernelconfig'] != 'disable_cstates':
            fig1 = plot_residency_per_target_qps(stats, system_conf, qps_list)
            pdf.savefig(fig1)
    # fig2 = plot_total_qps_per_target_qps(stats, system_confs, qps_list)
    # pdf.savefig(fig2)
    # fig3 = plot_latency_per_target_qps(stats, system_confs, qps_list, filter = ['read_avg'])
    # pdf.savefig(fig3)
    # fig4 = plot_power_per_target_qps(stats, system_confs, qps_list)
    # pdf.savefig(fig4)
    if interactive:
        plt.show()
    # plt.close(fig2)
    # plt.close(fig3)
    # plt.close(fig4)
    pdf.close()

def main(argv):
    stats_root_dir = argv[1]
    stats = parse_multiple_instances_stats(stats_root_dir)
    system_confs = [
        # {'turbo': False, 'kernelconfig': 'baseline'},
        # {'turbo': False, 'kernelconfig': 'disable_cstates'},
        # {'turbo': False, 'kernelconfig': 'disable_c6'},
#        {'turbo': False, 'kernelconfig': 'disable_c1e_c6'},
        # {'turbo': False, 'kernelconfig': 'quick_c1'},
        # {'turbo': False, 'kernelconfig': 'quick_c1_disable_c6'},
        # {'turbo': False, 'kernelconfig': 'quick_c1_c1e'},
        {'turbo': True, 'kernelconfig': 'baseline'},
        # {'turbo': True, 'kernelconfig': 'disable_cstates'},
#        {'turbo': True, 'kernelconfig': 'disable_c6'},
#        {'turbo': True, 'kernelconfig': 'disable_c1e_c6'},
        # {'turbo': True, 'kernelconfig': 'quick_c1'},
        # {'turbo': True, 'kernelconfig': 'quick_c1_disable_c6'},
        # {'turbo': True, 'kernelconfig': 'quick_c1_c1e'},
    ]
    qps_list = [10000, 50000, 100000, 200000, 300000, 400000, 500000, 1000000, 2000000]
    qps_list = [10000, 50000, 100000, 200000, 300000, 400000, 500000]
    #plot(stats, system_confs, qps_list, interactive=False)
    plot_stack(stats, system_confs, qps_list, interactive=True)
    write_csv_all(stats, system_confs, qps_list)
    #write_latency_to_single_csv(stats, system_confs, qps_list)
    #write_power_to_single_csv(stats, system_confs, qps_list)
    #write_total_qps_to_single_csv(stats, system_confs, qps_list)

if __name__ == '__main__':
    main(sys.argv)

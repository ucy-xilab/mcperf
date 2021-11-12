import ast 
import os
import sys
import matplotlib.pyplot as plt

def derive_datatype(datastr):
    try:
        return type(ast.literal_eval(datastr))
    except:
        return type("")

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

def read_data(data_dir):
    data = {}
    for fname in os.listdir(data_dir):
        filepath = os.path.join(data_dir, fname)
        (header, timeseries) = read_timeseries(filepath)
        data[header] = timeseries
    return data

def cpu_state_time_perc(data, cpu_id):
    state_names = ['POLL', 'C1', 'C1E', 'C6']
    state_time_perc = []
    total_state_time = 0
    time_us = 0
    for state_name in state_names:
        metric_name = "CPU{}.{}.time".format(cpu_id, state_name)
        (ts_start, val_start) = data[metric_name][0]
        (ts_end, val_end) = data[metric_name][-1]
        time_us = max(time_us, (ts_end - ts_start) * 1000000.0)
        total_state_time += val_end - val_start

    time_us = max(time_us, total_state_time)
    for state_name in state_names:
        metric_name = "CPU{}.{}.time".format(cpu_id, state_name)
        (ts_start, val_start) = data[metric_name][0]
        (ts_end, val_end) = data[metric_name][-1]
        state_time_perc.append((val_end-val_start)/time_us)
    # calculate C0 
    state_time_perc[0] = 1 - sum(state_time_perc[1:4])
    state_names[0] = 'C0' 
    return state_time_perc


def avg_state_time_perc(data_dir, cpu_id_list):
    data = read_data(data_dir)
    total_state_time_perc = [0]*4
    cpu_count = 0
    for cpud_id in cpu_id_list:
        cpu_count += 1
        total_state_time_perc = [a + b for a, b in zip(total_state_time_perc, cpu_state_time_perc(data, cpud_id))]
    avg_state_time_perc = [a/b for a, b in zip(total_state_time_perc, [cpu_count]*len(total_state_time_perc))]
    return avg_state_time_perc

def main(argv):
    data_dir = argv[1]
    time_perc = avg_state_time_perc(data_dir, range(0, 40))
    state_names = ['C0', 'C1', 'C1E', 'C6']

    labels = ['Q00']
    bars = []
    bar = []
    for state_id in range(0, len(state_names)):
        bar.append(time_perc[state_id])
    bars.append(bar)
    width = 0.35       # the width of the bars: can also be len(x) sequence

    fig, ax = plt.subplots()

    for bar in bars:
        for (state_name, val) in zip(state_names, bar):
            ax.bar(labels, val, width, label=state_name)

    ax.set_ylabel('C-State Residency')
    ax.set_xlabel('Request Rate')
    ax.legend()

    plt.show()

if __name__ == '__main__':
    main(sys.argv)

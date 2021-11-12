import ast 
import os
import sys

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
    for state_name in state_names:
        metric_name = "CPU{}.{}.time".format(cpu_id, state_name)
        (ts_start, val_start) = data[metric_name][0]
        (ts_end, val_end) = data[metric_name][-1]
        time_us = (ts_end - ts_start) * 1000000.0
        state_time_perc.append((val_end-val_start)/time_us)
    # calculate C0 
    state_time_perc[0] = 1 - min(1, sum(state_time_perc[1:4]))
    state_names[0] = 'C0' 
    print(state_time_perc)    


def main(argv):
    data_dir = argv[1]
    data = read_data(data_dir)
    for cpud_id in range(0,40):
       cpu_state_time_perc(data, cpud_id)

if __name__ == '__main__':
    main(sys.argv)

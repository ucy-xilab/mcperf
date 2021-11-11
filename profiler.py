from xmlrpc.server import SimpleXMLRPCServer
import xmlrpc.client
import argparse
import functools
import logging
import os
import sys
import socket
import time
import threading
import subprocess
import re

# TODO: ProfilerGroup has a tick thread that wakes up at the minimum sampling period and wakes up each profiler if it has to wake up

# def power_state_diff(new_vector, old_vector):
#     diff = []
#     for (new, old) in zip(new_vector, old_vector):
#         diff.append([x[0] - x[1] for x in zip(new, old)])
#     return diff
 
class EventProfiling:
    def __init__(self):
        self.terminate_thread = threading.Condition()
        self.is_active = False

    def profile_thread(self):
        while self.is_active:
            timestamp = int(time.time())
            self.sample(timestamp)

            self.terminate_thread.acquire()
            self.terminate_thread.wait(timeout=1)
            self.terminate_thread.release()

    def start(self):
        self.is_active=True
        self.thread = threading.Thread(target=EventProfiling.profile_thread, args=(self,))
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        self.is_active=False
        self.terminate_thread.acquire()
        self.terminate_thread.notify()
        self.terminate_thread.release()


class PerfEventProfiling(EventProfiling):
    def __init__(self):
        super().__init__()
        self.events = self.get_perf_power_events()
        self.timeseries = {}
        for e in self.events:
            self.timeseries[e] = []

    def get_perf_power_events(self):
        events = []
        result = subprocess.run(['perf', 'list'], stdout=subprocess.PIPE)
        for l in result.stdout.decode('utf-8').splitlines():
            l = l.lstrip()
            m = re.match("(power/energy-.*/)\s*\[Kernel PMU event]", l)
            if m:
                events.append(m.group(1))
        return events

    def sample(self, timestamp):
        events_str = ','.join(self.events)
        cmd = ['sudo', 'perf', 'stat', '-a', '-e', events_str, 'sleep', '1']
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        out = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        for e in self.events:
            for l in out:
                l = l.lstrip()
                m = re.match("(.*)\s+.*\s+{}".format(e), l)
                if m:
                    value = m.group(1)
                    self.timeseries[e].append((timestamp, float(value)))

    def report(self):
        return self.timeseries

class MpstatProfiling(EventProfiling):
    def __init__(self):
        super().__init__()
        self.timeseries = {}
        self.timeseries['cpu_util'] = []

    def sample(self, timestamp):
        cmd = ['mpstat', '1', '1']
        result = subprocess.run(cmd, stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        lines = result.stdout.decode('utf-8').splitlines() + result.stderr.decode('utf-8').splitlines()
        for l in lines:
            if 'Average' in l:
                idle_val = float(l.split()[-1])
                self.timeseries['cpu_util'].append((timestamp, 100.00-idle_val))
                return 

    def report(self):
        return self.timeseries

class StateProfiling(EventProfiling):
    def __init__(self):
        super().__init__()
        self.state_names = StateProfiling.power_state_names()
        self.timeseries = {}

    @staticmethod
    def power_state_names():
        state_names = []
        stream = os.popen('ls /sys/devices/system/cpu/cpu0/cpuidle/')
        states = stream.readlines()
        for state in states:
            state = state.strip()
            stream = os.popen("cat /sys/devices/system/cpu/cpu0/cpuidle/{}/name".format(state))
            state_names.append(stream.read().strip())
        return state_names

    @staticmethod
    def power_state_metric(cpu_id, state_id, metric):
        output = open("/sys/devices/system/cpu/cpu{}/cpuidle/state{}/{}".format(cpu_id, state_id, metric)).read()
        return int(output)

    def sample_power_state_metric(self, metric, timestamp):
        for cpu_id in range(0, os.cpu_count()):
            for state_id in range(0, len(self.state_names)):
                state_name = self.state_names[state_id]
                key = "CPU{}.{}.{}".format(cpu_id, state_name, metric)
                value = StateProfiling.power_state_metric(cpu_id, state_id, metric)
                self.timeseries.setdefault(key, []).append((timestamp, value))

    def sample(self, timestamp):
        self.sample_power_state_metric('usage', timestamp)
        self.sample_power_state_metric('time', timestamp)

    def report(self):
        print('report')
        return self.timeseries

class ProfilingService:
    def __init__(self, profilers):
        self.profilers = profilers
        
    def start(self):
        for p in self.profilers:
            p.start()        

    def stop(self):
        for p in self.profilers:
            p.stop()        

    def report(self):
        timeseries = {}
        for p in self.profilers:
            print(p.report())
            t = p.report()
            timeseries = {**timeseries, **t}
        return timeseries


def server(port):
    perf_event_profiling = PerfEventProfiling()
    mpstat_profiling = MpstatProfiling()
    state_profiling = StateProfiling()
    profiling_service = ProfilingService([perf_event_profiling, mpstat_profiling, state_profiling])
    hostname = socket.gethostname().split('.')[0]
    server = SimpleXMLRPCServer((hostname, port), allow_none=True)
    server.register_instance(profiling_service)
    print("Listening on port {}...".format(port))
    server.serve_forever()

class StartAction:
    @staticmethod
    def add_parser(subparsers):
        parser = subparsers.add_parser('start', help = "Start profiling")
        parser.set_defaults(func=StartAction.action)

    @staticmethod
    def action(args):
        with xmlrpc.client.ServerProxy("http://{}:{}/".format(args.hostname, args.port)) as proxy:
            proxy.start()

class StopAction:
    @staticmethod
    def add_parser(subparsers):
        parser = subparsers.add_parser('stop', help = "Stop profiling")
        parser.set_defaults(func=StopAction.action)

    @staticmethod
    def action(args):
        with xmlrpc.client.ServerProxy("http://{}:{}/".format(args.hostname, args.port)) as proxy:
            proxy.stop()

class ReportAction:
    @staticmethod
    def add_parser(subparsers):
        parser = subparsers.add_parser('report', help = "Report profiling")
        parser.set_defaults(func=ReportAction.action)

    @staticmethod
    def action(args):
        with xmlrpc.client.ServerProxy("http://{}:{}/".format(args.hostname, args.port)) as proxy:
            stats = proxy.report()
            print(stats)

def parse_args():
    """Configures and parses command-line arguments"""
    parser = argparse.ArgumentParser(
                    prog = 'profiler',
                    description='profiler',
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "-n", "--hostname", dest='hostname',
        help="profiler server hostname")
    parser.add_argument(
        "-p", "--port", dest='port', type=int, default=8000,
        help="profiler server port")
    parser.add_argument(
        "-v", "--verbose", dest='verbose', action='store_true',
        help="verbose")

    subparsers = parser.add_subparsers(dest='subparser_name', help='sub-command help')
    actions = [StartAction, StopAction, ReportAction]
    for a in actions:
      a.add_parser(subparsers)

    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s')

    if args.verbose:
        logging.getLogger('').setLevel(logging.INFO)
    else:
        logging.getLogger('').setLevel(logging.ERROR)

    if args.hostname:
        if 'func' in args:
            args.func(args)
        else:
            raise Exception('Attempt to run in client mode but no command is given')
    else:
        server(args.port)

def real_main():
    parse_args()

def main():
    real_main()
    return
    try:
        real_main()
    except Exception as e:
        logging.error("%s %s" % (e, sys.stderr))
        sys.exit(1)

if __name__ == '__main__':
    main()

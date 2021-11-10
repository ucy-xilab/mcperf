from xmlrpc.server import SimpleXMLRPCServer
import xmlrpc.client
import argparse
import functools
import logging
import sys
import socket
import time
import threading
import subprocess
import re

class Profiling:
    def __init__(self):
        self.terminate = threading.Condition()
        self.is_active = False

    def perf_power_events(self):
        result = subprocess.run(['perf', 'list'], stdout=subprocess.PIPE)
        for l in result.stdout.decode('utf-8').splitlines():
            m = re.match("\s*power/energy-(.*)/\s*\[Kernel PMU event]", l)
            if m:
                print(m.group(1))
            

    def perf_stat_power(self):
        #result = subprocess.run(['perf', 'stat'], stdout=subprocess.PIPE)
        print(result.stdout.decode('utf-8'))

profiling = Profiling()
profiling.perf_power_events()
#profiling.perf_stat_power()
sys.exit(0)

def profile_thread():
    while profiling.is_active:
        print('perf')
        profiling.perf_stat_power()

        profiling.terminate.acquire()
        profiling.terminate.wait(timeout=1)
        profiling.terminate.release()

def start():
    global profiling
    profiling.is_active=True
    x = threading.Thread(target=profile_thread)    
    x.daemon = True
    x.start()

def stop():
    global profiling
    profiling.is_active=False
    profiling.terminate.acquire()
    profiling.terminate.notify()
    profiling.terminate.release()

def server(port):
    hostname = socket.gethostname().split('.')[0]
    server = SimpleXMLRPCServer((hostname, port), allow_none=True)
    print("Listening on port {}...".format(port))
    server.register_function(start, "start")
    server.register_function(stop, "stop")
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
    actions = [StartAction, StopAction]
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

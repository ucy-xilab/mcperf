from xmlrpc.server import SimpleXMLRPCServer
import xmlrpc.client
import argparse
import functools
import logging
import sys


def is_even(n):
    return n % 2 == 0

def server():
    server = SimpleXMLRPCServer(("node0", 8000))
    print("Listening on port 8000...")
    server.register_function(is_even, "is_even")
    server.serve_forever()


def client():
    with xmlrpc.client.ServerProxy("http://node0:8000/") as proxy:
        print("3 is even: %s" % str(proxy.is_even(3)))
        print("100 is even: %s" % str(proxy.is_even(100)))

class ProfileAction:
    @staticmethod
    def add_parser(subparsers):
        parser = subparsers.add_parser('profile', help = "Add user to test cluster")
        parser.set_defaults(func=ProfileAction.action)

    @staticmethod
    def action(args):
        client()

def parse_args():
    """Configures and parses command-line arguments"""
    parser = argparse.ArgumentParser(
                    prog = 'profile',
                    description='profile',
                    formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    parser.add_argument(
        "-s", "--server", dest='server',
        help="run profiler server")
    parser.add_argument(
        "-v", "--verbose", dest='verbose', action='store_true',
        help="verbose")

    subparsers = parser.add_subparsers(dest='subparser_name', help='sub-command help')
    actions = [ProfileAction]
    for a in actions:
      a.add_parser(subparsers)

    args = parser.parse_args()
    logging.basicConfig(format='%(levelname)s:%(message)s')

    if args.verbose:
        logging.getLogger('').setLevel(logging.INFO)
    else:
       logging.getLogger('').setLevel(logging.ERROR)

    if args.server:
        if args.func:
            args.func(args)
    else:
        server()

def real_main():
    parse_args()

def main():
    #real_main()
    #return
    try:
        real_main()
    except Exception as e:
        logging.error("%s %s" % (e, sys.stderr))
        sys.exit(1)


if __name__ == '__main__':
    main()

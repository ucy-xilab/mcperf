sudo apt update
sudo apt install ansible -y

./mcperf.sh build_and_deploy


./memcache-perf/mcperf -s node1 --loadonly

./memcache-perf/mcperf -s node1 --noload -B -T 16 -Q 1000 -D 4 -C 4 -a node2 -a node3 -a node4 -a node5 -a node6 -a node7 -c 4 -q 2000000

python3 profiler.py -n node1 start

./memcache-perf/mcperf -s node1 --noload -B -T 16 -Q 1000 -D 4 -C 4 -a node2 -c 4 -q 2000000

python3 profiler.py -n node1 stop

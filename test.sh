python3 profiler.py -n node0 start
taskset -c 4 ./spin 10
#sleep 10
python3 profiler.py -n node0 stop
python3 profiler.py -n node0 report -d ~/data/0/

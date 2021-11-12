python3 profiler.py -n node0 start
COUNTER=0; while [ $COUNTER -lt 3000000 ]; do let COUNTER=COUNTER+1; done;
COUNTER=0; while [ $COUNTER -lt 3000000 ]; do let COUNTER=COUNTER+1; done;
python3 profiler.py -n node0 stop
python3 profiler.py -n node0 report -d ~/data/0/

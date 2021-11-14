# Running experiments

./mcperf.sh build_and_deploy
python3 run_experiment BATCH_NAME

# Analyzing data
python3 pull.py HOSTNAME
python3 analyze.py data/BATCH_NAME


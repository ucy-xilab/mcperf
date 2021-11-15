# Running experiments

./mcperf.sh build_and_deploy
python3 run_experiment BATCH_NAME

# Analyzing data
python3 pull.py HOSTNAME
python3 analyze.py data/BATCH_NAME

# Building kernel packages on Ubuntu 18.04

sudo apt update
sudo apt-get install build-essential linux-source bc kmod cpio flex libncurses5-dev libelf-dev libssl-dev
sudo chmod a+rwx /mydata
wget https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-4.15.18.tar.xz
tar -xf linux-4.15.18.tar.xz
cp /boot/config-4.15.0-159-generic .config

Edit .config
Set CONFIG_LOCALVERSION to "10-20"
Set CONFIG_SYSTEM_TRUSTED_KEYS to ""

Edit ./drivers/idle/intel_idle.c:661

make -j`nproc` bindeb-pkg

sudo dpkg -i linux-headers-4.15.18_4.15.18-1_amd64.deb linux-image-4.15.18_4.15.18-1_amd64.deb
sudo dpkg -i linux-headers-4.15.18-c1-1-1-c1e-10-20_4.15.18-c1-1-1-c1e-10-20-4_amd64.deb linux-image-4.15.18-c1-1-1-c1e-10-20_4.15.18-c1-1-1-c1e-10-20-4_amd64.deb
sudo dpkg -i linux-headers-4.15.18-c1-1-1-c1e-05-20_4.15.18-c1-1-1-c1e-05-20-5_amd64.deb linux-image-4.15.18-c1-1-1-c1e-05-20_4.15.18-c1-1-1-c1e-05-20-5_amd64.deb

# Running experiments

```
./mcperf.sh install_dep
./mcperf.sh build_install
python3 run_experiment.py BATCH_NAME
```

# Analyzing data
```
python3 pull.py HOSTNAME
python3 analyze.py data/BATCH_NAME
```

# Building kernel packages on Ubuntu 18.04

```
sudo apt update
sudo apt-get install build-essential linux-source bc kmod cpio flex libncurses5-dev libelf-dev libssl-dev
sudo chmod a+rwx /mydata
wget https://cdn.kernel.org/pub/linux/kernel/v4.x/linux-4.15.18.tar.xz
tar -xf linux-4.15.18.tar.xz
cp /boot/config-4.15.0-159-generic .config
```

Edit .config

```
CONFIG_LOCALVERSION="c1-2-2-c1e-10-20"
CONFIG_SYSTEM_TRUSTED_KEYS=""
```

```
make oldconfig
```

Edit ./drivers/idle/intel_idle.c:661

```
make -j`nproc` bindeb-pkg
```

```
sudo dpkg -i linux-headers-4.15.18-c1-2-2-c1e-10-20_4.15.18-c1-2-2-c1e-10-20-1_amd64.deb linux-image-4.15.18-c1-2-2-c1e-10-20_4.15.18-c1-2-2-c1e-10-20-1_amd64.deb
sudo dpkg -i linux-headers-4.15.18-c1-1-1-c1e-10-20_4.15.18-c1-1-1-c1e-10-20-2_amd64.deb linux-image-4.15.18-c1-1-1-c1e-10-20_4.15.18-c1-1-1-c1e-10-20-2_amd64.deb
sudo dpkg -i linux-headers-4.15.18-c1-1-1-c1e-05-20_4.15.18-c1-1-1-c1e-05-20-3_amd64.deb linux-image-4.15.18-c1-1-1-c1e-05-20_4.15.18-c1-1-1-c1e-05-20-3_amd64.deb
```

# Building kernel tools

```
make -C tools/perf
```

```
sudo apt install pciutils-dev
make -C tools/power/cpupower
```

# Configuring kernel

```
ssh -n node1 'cd ~/mcperf; sudo python3 configure.py -v --kernelconfig=baseline -v'
```

# Setting and checking uncore freq

[Setting uncore freq](https://www.linkedin.com/pulse/manually-setting-uncore-frequency-intel-cpus-johannes-hofmann/)

```
sudo likwid-perfctr -C 0-2 -g CLOCK sleep 1
```

# Installing Vtune - SoCWatch

Install dependencies

```
sudo apt-get install libgtk-3-0 libasound2 
```

Add the Intel oneAPI repository

```
cd /tmp
wget https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
sudo apt-key add GPG-PUB-KEY-INTEL-SW-PRODUCTS.PUB
echo "deb https://apt.repos.intel.com/oneapi all main" | sudo tee /etc/apt/sources.list.d/oneAPI.list

```

Install vtune profiler

```
sudo apt update
sudo apt install intel-oneapi-vtune
```

Set environment variables

```

source /opt/intel/oneapi/vtune/latest/env/vars.sh

```

# Parse SoCWatch and Vtune Output

### Vtune does not have a parsing script only parse command

```
/opt/intel/oneapi/vtune/2022.3.0/bin64/vtune -report summary -r "data directory"
```

### Parse SoCWatch

To get the PC1 residency and the number of transitions after a full idle 

```
python3 ./overlapping_intervals.py "trace_file"
```

To get the distribution of idle_periods

```
python3 ./idle_distribution.py "trace file" "num cores" "start core id" "end core id"
```
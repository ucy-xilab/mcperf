#!/bin/bash

export ANSIBLE_HOST_KEY_CHECKING=False

build_memcached () {
  if [[ -f "memcached/memcached" ]]
  then 
    return
  fi
  git clone --branch 1.6.12 https://github.com/memcached/memcached.git
  pushd memcached
  ./autogen.sh
  ./configure
  make -j4
  popd
}

build_mcperf () {
  if [[ -f "memcache-perf/mcperf" ]]
  then 
    return
  fi
  git clone https://github.com/shaygalon/memcache-perf
  pushd memcache-perf
  make -j4
  popd
}

build_and_deploy () {
  sudo apt update
  sudo apt install ansible -y
  ansible-playbook -v -i hosts ansible/configure.yml --tags "dependencies"
  build_memcached
  build_mcperf
  pushd ~
  tar -czf mcperf.tgz mcperf
  popd
  ansible-playbook -v -i hosts ansible/configure.yml --tags "mcperf"
}

run_profiler () {
  ansible-playbook -v -i hosts ansible/profiler.yml --tags "run_profiler"
}

kill_profiler () {
  ansible-playbook -v -i hosts ansible/profiler.yml --tags "kill_profiler"
}

run_remote () {
  ansible-playbook -v -i hosts ansible/mcperf.yml --tags "run_server,run_agents"
}

kill_remote () {
  ansible-playbook -v -i hosts ansible/mcperf.yml --tags "kill_server,run_servers"
}

run_server () {
  ansible-playbook -v -i hosts ansible/mcperf.yml --tags "run_server"
}

kill_server () {
  ansible-playbook -v -i hosts ansible/mcperf.yml --tags "kill_server"
}

status_remote () {
  ansible-playbook -v -i hosts ansible/mcperf.yml --tags "status"
}

run_experiment () {
  python3 profiler.py -n node1 start
  ./memcache-perf/mcperf -s node1 --noload -B -T 16 -Q 1000 -D 4 -C 4 -a node2 -c 4 -q 2000000
  python3 profiler.py -n node1 stop
}


"$@"

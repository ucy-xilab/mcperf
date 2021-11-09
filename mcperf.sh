#!/bin/bash

ANSIBLE_HOST_KEY_CHECKING=False

build_memcached () {
  if [ -d "memcached" ]
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
  if [ -d "memcache-perf" ]
  then 
    return
  fi
  git clone https://github.com/shaygalon/memcache-perf
  pushd memcache-perf
  make -j4
  popd
  cp ./memcache-perf/mcperf .
}

build_and_deploy () {
  build_memcached
  build_mcperf
  ansible-playbook -v -i hosts mcperf.yml --tags "configuration"
}

run_remote () {
  ansible-playbook -v -i hosts mcperf.yml --tags "run"
}

kill_remote () {
  ansible-playbook -v -i hosts mcperf.yml --tags "kill"
}

status_remote () {
  ansible-playbook -v -i hosts mcperf.yml --tags "status"
}



"$@"

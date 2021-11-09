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
  build_mcperf
  ansible-playbook -v -i hosts deploy.yml
}

run_agents () {
  ansible-playbook -v -i hosts run-mcperf.yml
}

run_master () {
  echo 'run'
}

run_memcached_server () {
  echo 'run'
}

"$@"

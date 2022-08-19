#!/bin/bash

#execute  telnet for memcached processing time
if [[ -z $1 ]]; then

	echo "Wrong enter node ip"
	exit
fi

node=$1
socwatch_status=`ssh $node "ps aux | grep \"socwatch\" | wc -l"`
echo "$socwatch_status"

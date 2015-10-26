
#!/bin/bash

set -v

cd "${BASH_SOURCE%/*}" || exit

CLUSTER_PREFIX="kafka"

if [ "$#" -ne 0 ]; then
    ARGS="$@"
else
    ARGS="up -d"
fi

DOCKER_HOST=tcp://192.168.99.100:2375
docker-compose -f node-192.168.99.100.yml -p "$CLUSTER_PREFIX" $ARGS

DOCKER_HOST=tcp://192.168.99.101:2375
docker-compose -f node-192.168.99.101.yml -p "$CLUSTER_PREFIX" $ARGS

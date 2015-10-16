
#!/bin/bash

set -v

cd "${BASH_SOURCE%/*}" || exit

CLUSTER_PREFIX="kafka"

DOCKER_HOST=tcp://192.168.99.100:2375
docker-compose -f node-192.168.99.100.yml -p "$CLUSTER_PREFIX" up -d

DOCKER_HOST=tcp://192.168.99.101:2375
docker-compose -f node-192.168.99.101.yml -p "$CLUSTER_PREFIX" up -d

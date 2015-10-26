#!/usr/bin/env python

import os
import sys
import uuid
import yaml
import stat
from collections import defaultdict
from docopt import docopt

usage = """Kafka Cluster Generator

Usage:
    kafka-cluster.py --kafka=<kafka>
                     --zookeeper=<zookeeper>
                     [--manager=<manager>]
                     [<dir>]

Generates a set of docker-compose.yml files and a script for deploying the
containers. The hostnames of the addresses are Docker hosts and the ports
(if provided) will be the port that is exposed for that service.

The order of the brokers is preserved and is used to generate the broker
ID. If new brokers are added, append this to the original list to preserve
the existing order.
"""


DEFAULT_DOCKER_PORT = 2375
DEFAULT_KAFKA_PORT = 9092
DEFAULT_ZOOKEEPER_PORT = 2181
DEFAULT_MANAGER_PORT = 9000


def zookeeper_compose(port=DEFAULT_ZOOKEEPER_PORT):
    return {
        'image': 'wurstmeister/zookeeper',
        'restart': 'always',
        'ports': [
            '{:d}:2181'.format(port),
        ],
        'volumes': [
            '/data/zookeeper/data:/opt/zookeeper-3.4.6/data/',
        ]
    }


def kafka_compose(host, broker_id, zks, port=DEFAULT_KAFKA_PORT, link=False):
    zks = ','.join(zks)
    logs_dir = '/kafka/logs.{}'.format(broker_id)

    config = {
        'image': 'wurstmeister/kafka:0.8.2.1',
        'restart': 'always',
        'environment': {
            'JMX_PORT': 9093,
            'KAFKA_BROKER_ID': broker_id,
            'KAFKA_ADVERTISED_HOST_NAME': host,
            'KAFKA_ADVERTISED_PORT': port,
            'KAFKA_ZOOKEEPER_CONNECT': zks,
            'KAFKA_LOG_DIRS': logs_dir,
            'KAFKA_LOG_RETENTION_HOURS': 2147483647,
            'KAFKA_LOG_RETENTION_BYTES': -1,
            'KAFKA_OFFSETS_STORAGE': 'kafka',
            'KAFKA_DUAL_COMMIT_ENABLED': 'false',
            'KAFKA_CONTROLLED_SHUTDOWN_ENABLE': 'true',
            'KAFKA_AUTO_LEADER_REBALANCE_ENABLE': 'true',
            'KAFKA_DELETE_TOPIC_ENABLE': 'true',
        },
        'ports': [
            '9093:9093',
            '{:d}:9092'.format(port),
        ],
        'volumes': [
            '/data/kafka/logs.{:d}:{:s}'.format(broker_id, logs_dir),
        ],
    }

    if link:
        config['links'] = ['zk:zk']

    return config


def manager_compose(zks, secret=None, port=9000, link=False):
    zks = ','.join(zks)

    if not secret:
        secret = str(uuid.uuid4())

    config = {
        'image': 'sheepkiller/kafka-manager',
        'restart': 'always',
        'ports': [
            '{:d}:9000'.format(port),
        ],
        'environment': {
            'ZK_HOSTS': zks,
            'APPLICATION_SECRET': secret,
        },
    }

    if link:
        config['links'] = ['zk:zk']

    return config


script_header = """
#!/bin/bash

set -v

cd "${BASH_SOURCE%/*}" || exit

CLUSTER_PREFIX="kafka"

if [ "$#" -ne 0 ]; then
    ARGS="$@"
else
    ARGS="up -d"
fi
"""

script_template = """
DOCKER_HOST=tcp://{docker_host}:{docker_port}
docker-compose -f {file_name} -p "$CLUSTER_PREFIX" $ARGS
"""


def build_targets(root, brokers, zks, managers):
    if not root:
        root = '.'

    if not managers:
        managers = ()

    if not os.path.exists(root):
        os.makedirs(root)

    # Remove dupes.
    if len(set(brokers)) != len(brokers):
        print('Duplicate brokers listed.')
        sys.exit(1)

    if len(set(zks)) != len(zks):
        print('Duplicate zookeepers listed.')
        sys.exit(1)

    if len(set(managers)) != len(managers):
        print('Duplicate managers listed.')
        sys.exit(1)

    # Containers by Docker host.
    targets = defaultdict(dict)

    # Gather zookeeper hosts for reference by Kafka and Manager containers.
    zk_hosts = []

    for addr in zks:
        toks = addr.split(':')

        if len(toks) == 1:
            host = toks[0]
            port = DEFAULT_ZOOKEEPER_PORT
        else:
            host = toks[0]
            port = int(toks[1])

        zk_hosts.append('{}:{}'.format(host, port))

        config = zookeeper_compose(port=port)
        targets[host]['zk'] = config

    # Setup brokers.
    for i, addr in enumerate(brokers):
        toks = addr.split(':')

        if len(toks) == 1:
            host = toks[0]
            port = DEFAULT_KAFKA_PORT
        else:
            host = toks[0]
            port = int(toks[1])

        # Local copy.
        zks = zk_hosts[:]
        link_zk = False

        # Replace shared host with link.
        if 'zk' in targets[host]:
            for i, zk in enumerate(zks):
                if zk.startswith(host):
                    zks[i] = 'zk:{:s}'.format(zk.split(':')[1])
                    link_zk = True
                    break

        config = kafka_compose(host=host,
                               port=port,
                               broker_id=i,
                               zks=zks,
                               link=link_zk)

        targets[host]['kafka'] = config

    # Setup managers.
    for addr in managers:
        toks = addr.split(':')

        if len(toks) == 1:
            host = toks[0]
            port = DEFAULT_MANAGER_PORT
        else:
            host = toks[0]
            port = int(toks[1])

        # Local copy.
        zks = zk_hosts[:]
        link_zk = False

        # Replace shared host with link.
        if 'zk' in targets[host]:
            for i, zk in enumerate(zks):
                if zk.startswith(host):
                    zks[i] = 'zk:{:s}'.format(zk.split(':')[1])
                    link_zk = True
                    break

        config = manager_compose(port=port,
                                 zks=zks,
                                 link=link_zk)

        targets[host]['manager'] = config

    return targets


def write_files(root, hosts):
    # Write the docker-compose files for each host.
    for host, containers in hosts.items():
        name = os.path.join(root, 'node-{}.yml'.format(host))

        with open(name, 'w') as f:
            yaml.dump(containers, f, indent=4, default_flow_style=False)

    # Write deploy script.
    name = os.path.join(root, 'deploy-cluster.sh')

    with open(name, 'w') as f:
        f.write(script_header)

        for host in hosts:
            file_name = 'node-{}.yml'.format(host)

            f.write(script_template.format(docker_host=host,
                                           docker_port=DEFAULT_DOCKER_PORT,
                                           file_name=file_name))

    # Make the file executable.
    st = os.stat(name)
    os.chmod(name, st.st_mode | stat.S_IEXEC)


def main(root, brokers, zks, managers=None):
    targets = build_targets(root, brokers, zks, managers)
    write_files(root, targets)


if __name__ == '__main__':
    opts = docopt(usage)

    brokers = opts['--kafka'].split(',')
    zks = opts['--zookeeper'].split(',')
    managers = (opts['--manager'] or '').split(',')

    main(opts['<dir>'],
         brokers=brokers,
         zks=zks,
         managers=managers)

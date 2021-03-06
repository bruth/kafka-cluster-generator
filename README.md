# Kafka Cluster Generator

The cluster generator outputs a set of Docker Compose files for deploying a Kafka cluster.

**Features**

- Includes containers for Kafka, Zookeeper, and [Kafka Manager](https://github.com/yahoo/kafka-manager)
- Generates a set of [Docker Compose](https://docs.docker.com/compose/) files for each host
- Generates a script for deploying the containers for each file

## Example

This command generates files for deploying 3 Kafka brokers, 1 Zookeeper instance, and 1 Kafka Manager interface.

```
cluster-generator.py \
    --kafka=192.168.99.100,192.168.99.101:9093,192.168.99.101:9094 \
    --zookeeper=192.168.99.100 \
    --manager=192.168.99.100 \
    ./example
```

See the [example](./example) directory for the output.

To deploy, run:

```
./example/deploy-cluster.sh
```

## Install

```
pip install -r requirements.txt
```

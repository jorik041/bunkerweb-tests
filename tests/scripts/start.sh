#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration=$1

echo "Building BunkerWeb stack for integration \"$integration\" ..."

# Starting stack
if [ "$integration" == "Docker" ] ; then
    docker compose -f tests/docker-compose.yml pull
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Pull failed ❌"
        exit 1
    fi
    docker compose -f tests/docker-compose.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Build failed ❌"
        exit 1
    fi
    docker compose -f tests/docker-compose.yml up -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Up failed, retrying ... ⚠️"
        cleanup_stack
        docker compose -f tests/docker-compose.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "Up failed ❌"
            exit 1
        fi
    fi
elif [ "$integration" == "Autoconf" ] ; then
    docker compose -f tests/docker-compose.autoconf.yml pull
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Pull failed for autoconf stack ❌"
        exit 1
    fi
    docker compose -f /tmp/autoconf-services.yml pull
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Pull failed for autoconf services ❌"
        exit 1
    fi
    docker compose -f tests/docker-compose.autoconf.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Build failed for autoconf stack ❌"
        exit 1
    fi
    docker compose -f /tmp/autoconf-services.yml build
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Build failed for autoconf services ❌"
        exit 1
    fi
    docker compose -f tests/docker-compose.autoconf.yml up -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Up failed for autoconf stack, retrying ... ⚠️"
        cleanup_stack
        docker compose -f tests/docker-compose.autoconf.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "Up failed for autoconf stack ❌"
            exit 1
        fi
    fi
    docker compose -f /tmp/autoconf-services.yml up -d
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Up failed for autoconf services, retrying ... ⚠️"
        cleanup_stack
        docker compose -f /tmp/autoconf-services.yml up -d
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "Up failed for autoconf services ❌"
            exit 1
        fi
    fi
else # TODO add Swarm and Kubernetes
    sudo systemctl start bunkerweb
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Start failed for BunkerWeb ❌"
        exit 1
    fi
    sudo systemctl start bunkerweb-core
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Start failed for BunkerWeb Core ❌"
        exit 1
    fi
fi

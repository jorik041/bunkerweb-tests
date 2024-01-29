#!/bin/bash

integration=$1
trapped=false

if [ -z "$integration" ] ; then
    echo "Please provide an integration name as argument ❌"
    exit 1
elif [ "$integration" != "Docker" ] && [ "$integration" != "Linux" ] && [ "$integration" != "Autoconf" ] ; then # TODO: Add Swarm and Kubernetes
    echo "Integration \"$integration\" is not supported ❌"
    exit 1
fi

function cleanup_stack () {
    exit_code=$?
    echo "Cleaning up current stack ..."

    if [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then
        if [ "$integration" == "Docker" ] ; then
            docker compose -f tests/docker-compose.yml down -v --remove-orphans
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "Failed to stop BunkerWeb stack ❌"
                return 1
            fi
        elif [ "$integration" == "Autoconf" ] ; then
            docker compose -f /tmp/autoconf-services.yml down -v --remove-orphans
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "Failed to stop BunkerWeb Autoconf service ❌"
                return 1
            fi

            docker compose -f tests/docker-compose.autoconf.yml down -v --remove-orphans
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "Failed to stop BunkerWeb Autoconf stack ❌"
                return 1
            fi
        fi
    else
        sudo systemctl stop bunkerweb
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "Failed to stop BunkerWeb service ❌"
            return 1
        fi

        sudo systemctl stop bunkerweb-core
        # shellcheck disable=SC2181
        if [ $? -ne 0 ] ; then
            echo "Failed to stop BunkerWeb Core service ❌"
            return 1
        fi

        sudo journalctl --rotate --vacuum-time=1s
        sudo truncate -s 0 /var/log/bunkerweb/error.log
        sudo truncate -s 0 /var/log/bunkerweb/access.log
        sudo truncate -s 0 /var/log/bunkerweb/core.log
        sudo truncate -s 0 /var/log/bunkerweb/core-access.log
    fi

    if [ -f geckodriver.log ] ; then
        sudo rm -f geckodriver.log
    fi

    if [ "$exit_code" == 1 ] || ($trapped && [ "$exit_code" == 0 ] && [ "$(basename "$0")" == "run.sh" ]) ; then
        if docker ps -a -f "name=custom-api" | grep -q "custom-api" ; then
            docker stop custom-api
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "Failed to remove custom-api container ❌"
                return 1
            fi
        elif docker container ls -a -f "name=custom-api" | grep -q "custom-api" ; then
            docker container rm -f custom-api
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "Failed to remove custom-api container ❌"
                return 1
            fi
        fi

        if docker network ls -q -f "name=bw-universe" ; then
            docker network rm -f bw-universe
            # shellcheck disable=SC2181
            if [ $? -ne 0 ] ; then
                echo "Failed to remove bw-universe network ❌"
                return 1
            fi
        fi
    fi

    echo "Cleaning up current stack done ✅"
}

function log_stack () {
    echo "Showing BunkerWeb and BunkerWeb Core logs ..."

    if [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then
        docker logs bunkerweb
        docker logs bw-core
        if [ "$integration" == "Autoconf" ] ; then
            docker logs bw-autoconf
        fi
    else
        sudo journalctl -u bunkerweb --no-pager
        echo "Showing BunkerWeb error logs ..."
        sudo cat /var/log/bunkerweb/error.log
        echo "Showing BunkerWeb access logs ..."
        sudo cat /var/log/bunkerweb/access.log

        sudo journalctl -u bunkerweb-core --no-pager
        echo "Showing BunkerWeb core error logs ..."
        sudo cat /var/log/bunkerweb/core.log
        echo "Showing BunkerWeb core access logs ..."
        sudo cat /var/log/bunkerweb/core-access.log
    fi

    if docker ps -a -f "name=custom-api" | grep -q "custom-api" ; then
        echo "Showing custom-api logs ..."
        docker logs custom-api
    fi

    if [ -f geckodriver.log ] ; then
        echo "Showing Geckodriver logs ..."
        sudo cat geckodriver.log
    fi
}

function exit_wrapper() {
    exit_code=$?
    if [ "$exit_code" == 0 ] && [ "$(basename "$0")" != "run.sh" ] ; then
        return 0
    fi
    trapped=true

    log_stack
    cleanup_stack
}

# show logs and cleanup stack on exit
trap exit_wrapper EXIT

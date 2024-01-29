#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration=$1
timeout=$(cat /tmp/timeout.txt)

echo "Waiting for stack to be healthy ..."
i=0
if [ "$integration" == "Docker" ] || [ "$integration" == "Autoconf" ] ; then
    while [ $i -lt "$timeout" ] ; do
        if [ "$integration" == "Autoconf" ] ; then
            containers=("bunkerweb" "bw-core" "bw-autoconf")
        else
            containers=("bunkerweb" "bw-core")
        fi
        healthy="true"
        for container in "${containers[@]}" ; do
            check="$(docker inspect --format "{{json .State.Health }}" "$container" | grep "healthy")"
            if [ "$check" = "" ] ; then
                healthy="false"
                break
            fi
        done
        if [ "$healthy" = "true" ] ; then
            sleep 5
            echo "Docker stack is healthy ✅"
            break
        fi
        sleep 1
        i=$((i+1))
    done
    if [ $i -ge "$timeout" ] ; then
        echo "Docker stack is not healthy after $timeout seconds ❌"
        exit 1
    fi
else
    healthy="false"
    retries=0
    while [[ $healthy = "false" && $retries -lt 5 ]] ; do
        while [ $i -lt "$timeout" ] ; do
            if sudo grep -q "BunkerWeb is ready" "/var/log/bunkerweb/error.log" ; then
                echo "Linux stack is healthy ✅"
                break
            fi
            sleep 1
            i=$((i+1))
        done
        if [ $i -ge "$timeout" ] ; then
            sudo journalctl -u bunkerweb --no-pager
            echo "🛡️ Showing BunkerWeb error logs ..."
            sudo cat /var/log/bunkerweb/error.log
            echo "🛡️ Showing BunkerWeb access logs ..."
            sudo cat /var/log/bunkerweb/access.log
            echo "Linux stack is not healthy after $timeout seconds ❌"
            exit 1
        fi

        if sudo journalctl -u bunkerweb --no-pager | grep -q "SYSTEMCTL - ❌ " ; then
            echo "⚠ Linux stack got an issue, restarting ..."
            sudo journalctl --rotate
            sudo journalctl --vacuum-time=1s
            cleanup_stack
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
            retries=$((retries+1))
        else
            healthy="true"
        fi
    done
    if [ "$retries" -ge 5 ] ; then
        echo "Linux stack could not be healthy after $retries retries ❌"
        exit 1
    fi
fi

#!/bin/bash

# shellcheck disable=SC1091
source tests/scripts/utils.sh

integration=$1
type=$2
release=$3
category=$4

if [ -z "$type" ] ; then
    echo "Please provide a test type as 2nd argument ❌"
    exit 1
elif [ "$type" != "examples" ] && [ "$type" != "core" ] && [ "$type" != "ui" ] ; then
    echo "Type \"$type\" is not supported ❌"
    exit 1
elif [ -z "$release" ] ; then
    echo "Please provide a release as 3rd argument ❌"
    exit 1
elif [ -z "$category" ] ; then
    echo "Please provide a category as 4th argument ❌"
    exit 1
fi

first_run=true

if [[ "$category" =~ ";" ]] ; then
    mkdir -p /tmp/tests
    echo "$category" > /tmp/tests/actions.txt
    category=$(echo "$category" | cut -d ";" -f 1)
else
    if [ "$release" == "dev" ] || [ "$release" == "v2" ] ; then
        python3 tests/parse.py "core" --category "$category" --dev
    else
        python3 tests/parse.py "core" --category "$category"
    fi
fi

docker network create --subnet=10.20.30.0/24 --label "com.docker.compose.network=bw-universe" bw-universe
# shellcheck disable=SC2181
if [ $? -ne 0 ] ; then
    echo "Failed to create bw-universe network ❌"
    exit 1
fi

if grep -q "custom-api" tests/core/"$category".yml ; then
    docker build -t custom-api -f tests/misc/api/Dockerfile tests/misc/api
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Failed to build custom-api ❌"
        exit 1
    fi
    docker run -d --rm --name custom-api --network bw-universe --ip 10.20.30.30 -p 8000:8000 custom-api
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Failed to run custom-api ❌"
        exit 1
    fi
fi

while read -r test ; do
    echo "Generating test \"$test\" ..."

    if ! $first_run ; then
        cleanup_stack

        if [ "$integration" == "Linux" ] ; then
            sudo chown "$USER":"$USER" /etc/bunkerweb/config.yml
        fi
    fi

    if [ "$release" == "dev" ] || [ "$release" == "v2" ] ; then
        python3 tests/generate.py "$integration" "$type" "$test" --dev
    else
        python3 tests/generate.py "$integration" "$type" "$test"
    fi

    if [ "$integration" == "Linux" ] ; then
        sudo chown nginx:nginx /etc/bunkerweb/config.yml
    fi

    if $first_run && [ "$integration" == "Linux" ] ; then
        sudo apt install -fy /tmp/bunkerweb.deb
    else
        ./tests/scripts/start.sh "$integration"
        ret=$?
        # shellcheck disable=SC2181
        if [ $ret -ne 0 ] ; then
            exit $ret
        fi
    fi

    ./tests/scripts/wait.sh "$integration"
    ret=$?
    # shellcheck disable=SC2181
    if [ $ret -ne 0 ] ; then
        exit $ret
    fi

	python3 "tests/$type.py" "$test"
    # shellcheck disable=SC2181
    if [ $? -ne 0 ] ; then
        echo "Test \"$test\" failed ❌"
        exit 1
    fi

    echo "Test \"$test\" passed ✅"

    first_run=false
done < "/tmp/tests/actions.txt"

echo "All tests passed ✅"

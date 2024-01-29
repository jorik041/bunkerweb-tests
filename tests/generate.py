#!/usr/bin/python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from logging import DEBUG, ERROR, INFO, WARNING, addLevelName, basicConfig, getLogger
from os import getenv, sep
from os.path import join
from pathlib import Path

from models import Action, SeleniumAction

from pydantic import ValidationError
from yaml import safe_dump, safe_load

basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="[%Y-%m-%d %H:%M:%S]", level=DEBUG if getenv("ACTIONS_STEP_DEBUG", False) else INFO)

# Edit the default levels of the logging module
addLevelName(DEBUG, "🐛")
addLevelName(ERROR, "❌")
addLevelName(INFO, "ℹ️ ")
addLevelName(WARNING, "⚠️ ")

LOGGER = getLogger("GENERATE")

parser = ArgumentParser(prog="Tests generator", description="Generate all the files needed to run a test.")
parser.add_argument("integration", type=str, help="Integration to test", choices=["Docker", "Linux", "Autoconf"])  # TODO: Add Swarm and Kubernetes
parser.add_argument("type", type=str, help="Type of test to parse", choices=["examples", "core", "ui"])
parser.add_argument("test", type=str, help="Test to generate the files for")
parser.add_argument("--dev", action="store_true", help="Run in development mode")
ARGS = parser.parse_args()

integrations = safe_load(Path("tests", "integrations.yml").read_text())["dev" if ARGS.dev else "staging"]

test_split = ARGS.test.split(";")
filename = test_split[0]
action_str = test_split[1]

LOGGER.info(f"🛠 Running {filename} / {action_str} generation for integration {ARGS.integration}")

if ARGS.integration not in integrations:
    LOGGER.error(f"Integration {ARGS.integration} not found in integrations.yml")
    exit(1)

file_path = join("tests", ARGS.type, f"{filename}.yml")

LOGGER.info(f"📖 Reading {file_path}")

LOGGER.debug(f"Trying to open {file_path}")

data = safe_load(Path(file_path).read_text())

LOGGER.info("📖 Parsing test file")
LOGGER.debug(f"Data: {data}")

action_data = data.get("actions", {}).get(action_str, {})

LOGGER.debug(f"Action data: {action_data}")

if not action_data:
    LOGGER.error(f"Action {action_str} not found in {filename}.yml")
    exit(1)

action_type = action_data.get("type", "Type not found")

if action_type not in Action.model_fields["type"].annotation.__dict__["__args__"] and action_type not in SeleniumAction.model_fields["type"].annotation.__dict__["__args__"]:
    LOGGER.error(f'Action {action_str} has an invalid type "{action_type}"')
    exit(1)

try:
    class_ = getattr(__import__("models"), action_type.title())
    action = class_(**action_data)
except ValidationError:
    LOGGER.exception(f"Action {action_str} has invalid data")
    exit(1)

test_config = data.get("config", {})
test_config = test_config | data.get(ARGS.integration, {}).get("config", {})
config = safe_load(Path("tests", "config.yml").read_text())

LOGGER.debug(f"Test config: {test_config}")
LOGGER.debug(f"Default config: {config}")

if ARGS.integration != "Linux":
    config["core"]["listen_addr"] = "0.0.0.0"
    config["core"]["whitelist"] = "10.20.30.0/24"
    config["core"]["bunkerweb_instances"] = ["10.20.30.254"]

if ARGS.integration == "Autoconf":
    config["core"]["autoconf_mode"] = True
    config["core"]["server_name"] = ""
    config["core"]["multisite"] = True

    test_labels = data.get("labels", {})
    test_labels = test_labels | data.get(ARGS.integration, {}).get("labels", {})
    AUTOCONF_PATH = Path("tests", "misc", "autoconf-services.yml")
    autoconf = (
        safe_load(AUTOCONF_PATH.read_text())
        if AUTOCONF_PATH.is_file()
        else {
            "version": "3.5",
            "services": {
                "app1": {
                    "image": "nginxdemos/nginx-hello:0.2",
                    "networks": {
                        "bw-services": {
                            "ipv4_address": "192.168.0.254",
                            "aliases": ["app1"],
                        }
                    },
                }
            },
            "networks": {
                "bw-services": {
                    "external": True,
                },
            },
        }
    )

    LOGGER.debug(f"Test labels: {test_labels}")
    LOGGER.debug(f"Default labels: {autoconf}")

    if "labels" not in autoconf["services"]["app1"]:
        autoconf["services"]["app1"]["labels"] = {}

    for key, value in (test_labels | action.labels | getattr(action, ARGS.integration).labels).items():
        autoconf["services"]["app1"]["labels"][f"bunkerweb.{key.replace('bunkerweb.', '', 1).upper()}"] = value

    LOGGER.debug(f"Final labels: {autoconf}")

    LOGGER.info("📝 Writing /tmp/autoconf-services.yml")
    Path(sep, "tmp", "autoconf-services.yml").write_text(safe_dump(autoconf, indent=2))

for key, value in (test_config | action.config | getattr(action, ARGS.integration).config).items():
    config["core"][key.lower()] = value

LOGGER.debug(f"Final config: {config}")
LOGGER.info("📝 Writing /etc/bunkerweb/config.yml")

Path(sep, "etc", "bunkerweb", "config.yml").write_text(safe_dump(config, indent=2))
Path(sep, "tmp", "timeout.txt").write_text(str(action.timeout))

#!/usr/bin/python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from glob import glob
from json import dumps
from logging import DEBUG, ERROR, INFO, WARNING, addLevelName, basicConfig, getLogger
from os import getenv, sep
from os.path import basename, join
from pathlib import Path
from typing import List

from yaml import safe_load

basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="[%Y-%m-%d %H:%M:%S]", level=DEBUG if getenv("ACTIONS_STEP_DEBUG", False) else INFO)

# Edit the default levels of the logging module
addLevelName(DEBUG, "🐛")
addLevelName(ERROR, "❌")
addLevelName(INFO, "ℹ️ ")
addLevelName(WARNING, "⚠️ ")

LOGGER = getLogger("PARSE")

parser = ArgumentParser(prog="Tests parser", description="Parse test files and return them as a b64encoded json file.")
parser.add_argument("type", type=str, help="Type of test to parse", choices=["examples", "core", "ui"])
parser.add_argument("--dev", action="store_true", help="Run in development mode")
parser.add_argument("--category", type=str, help="Category of the test to parse actions from")
ARGS = parser.parse_args()

LOGGER.info(f"✂ Parsing {ARGS.type} tests{' in dev mode' if ARGS.dev else ''}{', only actions from category ' + ARGS.category if ARGS.category else ''}")
LOGGER.debug(f"Arguments: {ARGS}")

integrations = {}
if not ARGS.category:
    LOGGER.info("📖 Reading integrations.yml")

    integrations = safe_load(Path("tests", "integrations.yml").read_text())["dev" if ARGS.dev else "staging"]

    LOGGER.debug(f"Integrations: {integrations}")


def check_integration(entry: List[str], data: dict) -> bool:
    """Check if the integration exists in the integrations.yml file"""
    if entry:
        return data.get(entry[0], False) and check_integration(entry[1:], data[entry[0]])
    return True


tests = []
if not ARGS.category:
    LOGGER.info("📖 Reading tests")

    for file in glob(join("tests", ARGS.type, "*.yml")):
        LOGGER.debug(f"Reading {file}")
        data = safe_load(Path(file).read_text())
        if data:
            name = basename(file).split(".")[0]
            test_integrations = data.get("integrations", [])
            LOGGER.debug(f"Integrations: {test_integrations}")
            if test_integrations == "all":
                for integration, arch in integrations.items():
                    for arch, specs in arch.items():
                        if isinstance(specs, dict):
                            for spec, value in specs.items():
                                if value == "TODO":
                                    LOGGER.debug(f"Skipping {integration} / {arch} / {spec} because it's TODO")
                                    continue
                                tests.append(f"{integration};{arch};{spec};{value};{name}")
                            continue
                        elif specs == "TODO":
                            LOGGER.debug(f"Skipping {integration} / {arch} because it's TODO")
                            continue
                        tests.append(f"{integration};{arch};{specs};{name}")
            elif isinstance(test_integrations, list):
                for integration in test_integrations:
                    integration_split = integration.split(";")
                    if not check_integration(integration_split, integrations):
                        LOGGER.warning(f"Skipping integration {integration} for {name}")
                        continue
                    run_on = integrations[integration_split[0]][integration_split[1]] if len(integration_split) == 2 else integrations[integration_split[0]][integration_split[1]][integration_split[2]]
                    if run_on == "TODO":
                        LOGGER.debug(f"Skipping {integration} because it's TODO")
                        continue
                    tests.append(f"{integration};{run_on};{name}")
            else:
                LOGGER.error(f"Invalid integrations for {name}: {test_integrations}")
        else:
            LOGGER.error(f"Invalid YAML in {file}")
            LOGGER.debug(f"Data: {data}")
else:
    LOGGER.info(f"📖 Reading actions from category: {ARGS.category}")
    file_path = join("tests", ARGS.type, ARGS.category + ".yml")
    LOGGER.debug(f"Reading {file_path}")
    data = safe_load(Path(file_path).read_text())
    if data:
        for action in data.get("actions", []):
            tests.append(f"{ARGS.category};{action}")
    else:
        LOGGER.error(f"Invalid YAML in {file_path}")
        LOGGER.debug(f"Data: {data}")
        exit(1)

LOGGER.debug(f"Tests: {tests}")

LOGGER.info("📝 Writing tests files")

tmp_path = Path(sep, "tmp", "tests")
tmp_path.mkdir(parents=True, exist_ok=True)

if not ARGS.category:
    for integration in integrations:
        tmp_path.joinpath(f"{integration}_tests.json").write_text(dumps([test for test in tests if test.startswith(f"{integration};")]))
else:
    tmp_path.joinpath("actions.txt").write_text("\n".join(tests) + "\n")

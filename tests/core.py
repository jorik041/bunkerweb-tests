#!/usr/bin/python3
# -*- coding: utf-8 -*-

from argparse import ArgumentParser
from datetime import timedelta
from logging import DEBUG, ERROR, INFO, WARNING, addLevelName, basicConfig, getLogger
from os import getenv
from os.path import join
from pathlib import Path
from re import match
from socket import create_connection
from ssl import CERT_NONE, DER_cert_to_PEM_cert, create_default_context
from time import sleep
from traceback import format_exc

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from httpx import Client, Response
from pydantic import ValidationError
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait  # type: ignore
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from yaml import safe_load

basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="[%Y-%m-%d %H:%M:%S]", level=DEBUG if getenv("ACTIONS_STEP_DEBUG", False) else INFO)

# Edit the default levels of the logging module
addLevelName(DEBUG, "🐛")
addLevelName(ERROR, "❌")
addLevelName(INFO, "ℹ️ ")
addLevelName(WARNING, "⚠️ ")

LOGGER = getLogger("CORE_TEST")

parser = ArgumentParser(prog="Tests runner", description="Run a test.")
parser.add_argument("test", type=str, help="Test to run")
ARGS = parser.parse_args()

test_split = ARGS.test.split(";")
filename = test_split[0]
action_str = test_split[1]

LOGGER.info(f"🚀 Running {filename} / {action_str} test")

file_path = join("tests", "core", f"{filename}.yml")

data = safe_load(Path(file_path).read_text())

action_data = data["actions"][action_str]
action_type = action_data["type"]

try:
    class_ = getattr(__import__("models"), action_type.title())
    action = class_(**action_data)
except ValidationError:
    LOGGER.exception(f"Action {action_str} has invalid data")
    exit(1)

if action.delay > 0:
    LOGGER.info(f"⏲ Waiting {action.delay} seconds ...")
    sleep(action.delay)

LOGGER.info(f"📡 Starting {action.type} test ...")

if action.type not in ("xpath", "cookie"):
    response = None

    LOGGER.info(f"Sending {action.method} request to {action.url} ...")
    LOGGER.debug(f"Request headers: {action.headers}")
    LOGGER.debug(f"Request auth: {action.auth}")
    LOGGER.debug(f"Allowing redirects: {action.follow_redirects}")
    LOGGER.debug(f"Verifying SSL: {action.verify_ssl}")

    try:
        with Client(
            auth=action.auth,
            headers=action.headers,
            verify=action.verify_ssl,
            http1=not action.http2,
            http2=action.http2,
            timeout=10,
            follow_redirects=action.follow_redirects,
        ) as client:
            response = client.request(action.method, action.url, data="a" * action.body_length if action.body_length > 0 else None)
    except Exception:
        response = format_exc()

    if isinstance(response, Response):
        LOGGER.debug(f"Response: {response.text}")
        LOGGER.debug(f"Response URL: {response.url}")
        LOGGER.debug(f"Response status code: {response.status_code}")
        LOGGER.debug(f"Response headers: {response.headers}")

        if action.http2 and response.http_version != "HTTP/2":
            LOGGER.error(f"HTTP/2 not used, instead found {response.http_version}, exiting ...")
            exit(1)

    if action.type == "string":
        assert isinstance(response, Response), f"❌ Request failed:\n{response}"
        response.raise_for_status()
        if action.string not in response.text:
            LOGGER.error(f"String {action.string} not found in response, exiting ...")
            exit(1)
        LOGGER.info(f"String {action.string} found in response")
    elif action.type == "path":
        assert isinstance(response, Response), f"❌ Request failed:\n{response}"
        if action.path not in str(response.url):
            response.raise_for_status()
            LOGGER.error(f"Path {action.path} not found in response URL, instead found {response.url}, exiting ...")
            exit(1)
        LOGGER.info(f"Path {action.path} found in response URL")
    elif action.type == "status":
        if isinstance(response, str):
            if action.status:
                LOGGER.error(f"Request failed, expected status code {action.status}, exiting ...")
                exit(1)
            LOGGER.info("Request failed, as expected")
        else:
            if not action.status:
                LOGGER.error("Request succeeded, expected failure, exiting ...")
                exit(1)
            elif action.status != response.status_code:
                LOGGER.error(f"Status code {action.status} not found in response, instead found {response.status_code}, exiting ...")
                exit(1)
            LOGGER.info(f"Status code {action.status} found in response")
    elif action.type == "header":
        assert isinstance(response, Response), f"❌ Request failed:\n{response}"
        response.raise_for_status()
        header = response.headers.get(action.header_name, None)
        if header is not None:
            if action.header_rx is None:
                LOGGER.error(f"Header {action.header_name} found in response, exiting ...\nheaders: {response.headers}")
                exit(1)
            elif not match(action.header_rx, header):
                LOGGER.error(f"Header {action.header_name} with regex {action.header_rx} not found in response, exiting ...\nheaders: {response.headers}")
                exit(1)
            LOGGER.info(f"Header {action.header_name} with regex {action.header_rx} matched in response")
        elif action.header_rx is not None:
            LOGGER.error(f"Header {action.header_name} with regex {action.header_rx} not found in response, exiting ...\nheaders: {response.headers}")
            exit(1)
        else:
            LOGGER.info(f"Header {action.header_name} not found in response")
    elif action.type == "ssl":
        assert isinstance(response, Response), f"❌ Request failed:\n{response}"
        response.raise_for_status()
        if response.url.scheme != "https":
            LOGGER.error("Response URL scheme is not HTTPS, exiting ...")
            exit(1)

        ssl_context = create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = CERT_NONE
        with create_connection((response.url.host, 443)) as conn:
            with ssl_context.wrap_socket(conn, server_hostname=response.url.host) as ssl_socket:
                LOGGER.debug(f"Response SSL version: {ssl_socket.version()}")
                LOGGER.debug(f"Response SSL cipher: {ssl_socket.cipher()}")
                LOGGER.debug(f"Response SSL compression: {ssl_socket.compression()}")
                LOGGER.debug(f"Response SSL shared ciphers: {ssl_socket.shared_ciphers()}")
                LOGGER.debug(f"Response SSL server certificate binary: {ssl_socket.getpeercert(True)}")
                if ssl_socket.version() not in action.ssl_protocols:
                    LOGGER.error(f"SSL version {ssl_socket.version()} not found in response, exiting ...")
                    exit(1)
                pem_data = DER_cert_to_PEM_cert(ssl_socket.getpeercert(True))  # type: ignore

        certificate = x509.load_pem_x509_certificate(pem_data.encode(), default_backend())

        if certificate.not_valid_after - certificate.not_valid_before != timedelta(days=int(action.ssl_expiration)):
            LOGGER.error(f"Expiration date of SSL certificate is {certificate.not_valid_after} but should be {certificate.not_valid_before + timedelta(days=int(action.ssl_expiration))}, exiting ...")
            exit(1)

        if sorted(attribute.rfc4514_string() for attribute in certificate.subject) != sorted(v for v in action.ssl_subject.split("/") if v):
            LOGGER.error(f"SSL subject {certificate.subject} is different from the one in the configuration, exiting ...")
            exit(1)
else:
    firefox_options = Options()
    firefox_options.add_argument("--headless")

    LOGGER.info("Starting Firefox ...")
    with webdriver.Firefox(options=firefox_options) as driver:
        driver.delete_all_cookies()
        driver.maximize_window()
        driver_wait = WebDriverWait(driver, 10)

        LOGGER.info(f"Navigating to {action.url} ...")
        driver.get(action.url)

        LOGGER.debug(f"Page source: {driver.page_source}")
        LOGGER.debug(f"Page URL: {driver.current_url}")

        if action.type == "xpath":
            try:
                driver_wait.until(EC.presence_of_element_located((By.XPATH, action.xpath)))
            except TimeoutException:
                LOGGER.exception(f"Xpath {action.xpath} not found in page")
                exit(1)
        elif action.type == "cookie":
            cookie = driver.get_cookie(action.cookie_name)
            if cookie is not None:
                if action.cookie_rx is None:
                    LOGGER.error(f"Cookie {action.cookie_name} found in page, exiting ...\ncookies: {driver.get_cookies()}")
                    exit(1)
                elif not match(action.cookie_rx, cookie["value"]):
                    LOGGER.error(f"Cookie {action.cookie_name} with regex {action.cookie_rx} not found in page, exiting ...\ncookies: {driver.get_cookies()}")
                    exit(1)
                elif cookie.get("secure", False) != action.cookie_secure_flag:
                    LOGGER.error(f"Cookie {action.cookie_name} doesn't have the right secure flag, exiting ...\ncookies: {driver.get_cookies()}")
                    exit(1)
                elif cookie.get("httpOnly", False) != action.cookie_http_only_flag:
                    LOGGER.error(f"Cookie {action.cookie_name} doesn't have the right HttpOnly flag, exiting ...\ncookies: {driver.get_cookies()}")
                    exit(1)
                elif cookie.get("sameSite", None) != action.cookie_same_site_flag:
                    LOGGER.error(f"Cookie {action.cookie_name} doesn't have the right SameSite flag, exiting ...\ncookies: {driver.get_cookies()}")
                    exit(1)
                LOGGER.info(f"Cookie {action.cookie_name} with regex {action.cookie_rx} matched in page, flags are correct")
            elif action.cookie_rx is not None:
                LOGGER.error(f"Cookie {action.cookie_name} with regex {action.cookie_rx} not found in page, exiting ...\ncookies: {driver.get_cookies()}")
                exit(1)
            else:
                LOGGER.info(f"Cookie {action.cookie_name} not found in page")

LOGGER.info("✅ Test passed")

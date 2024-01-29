#!/usr/bin/python3
# -*- coding: utf-8 -*-

from re import match
from typing import Dict, Literal, Optional, Set, Tuple

from lxml.etree import XPath
from pydantic import BaseModel, field_validator


class ActionData(BaseModel):
    config: Dict[str, str] = {}
    labels: Dict[str, str] = {}
    delay: float = 30.0
    timeout: int = 120

    @field_validator("labels")
    @classmethod
    def check_labels(cls, v: Dict[str, str]) -> Dict[str, str]:
        for label in v:
            if not label.startswith("bunkerweb."):
                raise ValueError("Labels must start with bunkerweb.")
        return v


class ActionBase(ActionData):
    type: Literal["string", "path", "status", "header", "ssl"]
    url: str
    method: Literal["GET", "OPTIONS", "HEAD", "POST", "PUT", "PATCH", "DELETE"] = "GET"
    headers: Dict[str, str] = {}
    auth: Optional[Tuple[str, str]] = None
    body_length: int = 0  # ? If body_length is 0, then no body is sent Else, will send the letter "a" body_length times
    follow_redirects: bool = False
    verify_ssl: bool = True
    http2: bool = False

    @field_validator("headers")
    @classmethod
    def check_headers(cls, v: Dict[str, str]) -> Dict[str, str]:
        for header in v:
            if not match(r"^[\w-]+$", header):
                raise ValueError("header_name must be a valid HTTP header")
        return v

    @field_validator("http2")  # TODO: Remove this when HTTP/2 is supported over HTTP
    @classmethod
    def check_http2(cls, v: bool) -> bool:
        if cls.url.startswith("http://") and v:
            raise ValueError("http2 must be False if the URL is not HTTPS as HTTP/2 is not supported over HTTP yet")
        return v


class Action(ActionBase):
    Docker: ActionData = ActionData()
    Linux: ActionData = ActionData()
    Autoconf: ActionData = ActionData()
    Swarm: ActionData = ActionData()
    Kubernetes: ActionData = ActionData()


class SeleniumAction(Action):
    type: Literal["xpath", "cookie"]
    method: Literal["GET"] = "GET"
    auth: None = None
    body_length: Literal[0] = 0
    follow_redirects: Literal[True] = True
    verify_ssl: Literal[True] = True
    http2: Literal[False] = False

    @field_validator("headers")
    @classmethod
    def check_headers(cls, v: str) -> str:
        if v != "GET":
            raise ValueError("headers are not allowed as this is a Selenium action")
        return v


class String(Action):
    type: Literal["string"] = "string"
    string: str


class Path(Action):
    type: Literal["path"] = "path"
    path: str


class Xpath(SeleniumAction):
    type: Literal["xpath"] = "xpath"
    xpath: str

    @field_validator("xpath")
    @classmethod
    def check_xpath(cls, v: str) -> str:
        XPath(v)
        return v


class Status(Action):
    type: Literal["status"] = "status"
    status: Optional[int] = None  # ? If status is None, then the request must fail

    @field_validator("status")
    @classmethod
    def check_status(cls, v: int) -> int:
        if v is not None and v < 100 or v > 599:
            raise ValueError("Status code must be between 100 and 599")
        return v


class Header(Action):
    type: Literal["header"] = "header"
    header_name: str
    header_rx: Optional[str] = None  # ? If header_rx is None, then the header must not be present

    @field_validator("header_name")
    @classmethod
    def check_header_name(cls, v: str) -> str:
        if not match(r"^[\w-]+$", v):
            raise ValueError("header_name must be a valid HTTP header")
        return v

    @field_validator("header_rx")
    @classmethod
    def check_header_rx(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            match(v, "")
        return v


class Cookie(SeleniumAction):
    type: Literal["cookie"] = "cookie"
    cookie_name: str
    cookie_rx: Optional[str] = None  # ? If cookie_rx is None, then the cookie must not be present
    cookie_secure_flag: bool = False
    cookie_http_only_flag: bool = False
    cookie_same_site_flag: Optional[Literal["Strict", "Lax"]] = None

    @field_validator("cookie_name")
    @classmethod
    def check_cookie_name(cls, v: str) -> str:
        if not match(r"^[\w+]+$", v):
            raise ValueError("cookie_name must be a valid HTTP cookie")
        return v

    @field_validator("cookie_rx")
    @classmethod
    def check_cookie_rx(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            match(v, "")
        return v

    @field_validator("cookie_secure_flag")
    @classmethod
    def check_cookie_secure_flag(cls, v: bool) -> bool:
        if cls.url.startswith("http://") and v:
            raise ValueError("cookie_secure_flag must be False if the URL is not HTTPS")
        return v


class Ssl(Action):
    type: Literal["ssl"] = "ssl"
    ssl_protocols: Set[Literal["TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3"]] = {"TLSv1.2", "TLSv1.3"}
    ssl_expiration: int = 365
    ssl_subject: str = "/CN=www.example.com/"

    @field_validator("url")
    @classmethod
    def check_url(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("The URL must be HTTPS when using the ssl type")
        return v

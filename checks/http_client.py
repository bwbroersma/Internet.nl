# Copyright: 2022, ECP, NLnet Labs and the Internet.nl contributors
# SPDX-License-Identifier: Apache-2.0
import socket
from timeit import default_timer as timer
from typing import Optional

import requests
import urllib3
from dns.resolver import NXDOMAIN, NoAnswer, LifetimeTimeout
from forcediphttpsadapter.adapters import ForcedIPHTTPSAdapter

from checks.resolver import dns_resolve_aaaa, dns_resolve_a
from checks.tasks.tls_connection import DEFAULT_TIMEOUT
from checks.tasks.tls_connection_exceptions import NoIpError
from django.conf import settings
from internetnl import log

# Disable HTTPS warnings as we intentionally disable HTTPS verification
urllib3.disable_warnings()


def _do_request(args, headers, kwargs, session, url):
    """
    This small wrapper helps with handling of redirects.
    As we often connect on an explicit IP, we also set an explicit Host header
    as it can't be inferred from the URL. However, this breaks redirect following,
    causing a redirect loop (#1033). This wrapper makes sure to remove it before
    following the redirect chain, then ensures response.history is complete.
    """
    user_allow_redirects = kwargs.pop("allow_redirects", True)
    response = session.get(
        url, headers=headers, stream=True, allow_redirects=False, timeout=DEFAULT_TIMEOUT, *args, **kwargs
    )
    if response.next and user_allow_redirects:
        headers = headers.copy()
        headers.pop("Host", None)
        initial_response = response
        response = session.get(
            initial_response.next.url,
            headers=headers,
            stream=True,
            allow_redirects=True,
            timeout=DEFAULT_TIMEOUT,
            *args,
            **kwargs,
        )
        response.history.insert(0, initial_response)

    return response


def http_get(
    url: str, headers: Optional[dict] = None, session: Optional[requests.Session] = None, *args, **kwargs
) -> requests.Response:
    """
    Perform a standard HTTP GET request. If session is given, it is used.
    Other (kw)args are passed to requests.get.
    """
    start_time = timer()

    if not headers:
        headers = {}
    headers["User-Agent"] = settings.USER_AGENT
    if not session:
        session = requests.session()

    try:
        response = _do_request(args, headers, kwargs, session, url)
    except (requests.RequestException, ValueError):
        # Retry, once, then log and raise the exception
        try:
            response = _do_request(args, headers, kwargs, session, url)
        except requests.RequestException as exc:
            log.debug(f"HTTP request raised exception: {url} (headers: {headers}): {exc}")
            raise exc

    log.debug(f"HTTP request completed in {timer()-start_time:.06f}s: {url} (headers: {headers})")
    return response


def http_get_ip(
    hostname: str,
    ip: str,
    port: int,
    path: str = "/",
    https: bool = True,
    headers: Optional[dict] = None,
    *args,
    **kwargs,
) -> requests.Response:
    """
    Perform an HTTP GET with the given parameters, while forcing the destination IP
    to a particular IP that may not match the hostname.
    TLS certificate verification is always disabled.
    Other (kw)args are passed to requests.get.
    """
    path = path.lstrip("/")
    if not headers:
        headers = {}

    session = requests.session()
    session.mount(f"https://{hostname}", ForcedIPHTTPSAdapter(dest_ip=ip))
    if https:
        port_suffix = "" if port == 443 else f":{port}"
        url = f"https://{hostname}{port_suffix}/{path}"
    else:
        if ":" in ip:
            ip = f"[{ip}]"
        port_suffix = "" if port == 80 else f":{port}"
        url = f"http://{ip}{port_suffix}/{path}"
    headers["Host"] = hostname
    return http_get(url, verify=False, headers=headers, session=session, *args, **kwargs)


def http_get_af(hostname: str, port: int, af: socket.AddressFamily, *args, **kwargs) -> requests.Response:
    """
    Perform an HTTP GET request to the given hostname/port, restricting to a certain address family.
    Other (kw)args are passed to requests.get.
    """
    exc = NoIpError(f"Unable to resolve {'AAAA' if af == socket.AF_INET6 else 'A'} record for host '{hostname}'")
    try:
        if af == socket.AF_INET6:
            ips = dns_resolve_aaaa(hostname)
        else:
            ips = dns_resolve_a(hostname)
    except (NoAnswer, NXDOMAIN, LifetimeTimeout, NoIpError):
        raise exc
    for ip in ips:
        try:
            return http_get_ip(hostname, ip, port, *args, **kwargs)
        except requests.RequestException as request_exception:
            exc = request_exception
    raise exc


def response_content_chunk(response: requests.Response, max_length: int) -> bytes:
    """
    Retrieve the content from a response, up to max_length.
    Used in various HTTP requests to avoid giant responses from breaking parsers.
    """
    chunk = b""
    try:
        response_iter = response.iter_content(max_length)
        while len(chunk) < max_length:
            chunk += next(response_iter)
    except StopIteration:
        pass
    # It's possible we retrieved too much, trim to avoid inconsistency
    return chunk[:max_length]

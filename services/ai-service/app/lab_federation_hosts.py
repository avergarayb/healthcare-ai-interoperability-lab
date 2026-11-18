"""Closed federation hosts for laboratory MCP clients.

Loopback remains valid for the existing tests. The two Docker DNS names are
bound to one jurisdiction source each. An arbitrary host is denied.
See ADR-105. This list is not a jurisdiction selector.
"""

PLATFORM_FEDERATION_HOSTS = frozenset({
    "127.0.0.1",
    "localhost",
    "federation-pe",
    "federation-es",
})

PLATFORM_HOST_SOURCE = {
    "federation-pe": "pe-lab-demo",
    "federation-es": "es-lab-demo",
}


def federation_host_allowed(hostname: str, source_key: str) -> bool:
    if hostname not in PLATFORM_FEDERATION_HOSTS:
        return False
    bound = PLATFORM_HOST_SOURCE.get(hostname)
    return bound is None or bound == source_key

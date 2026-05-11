"""
app/ollama_utils.py - Small helpers for working with Ollama endpoints.

This module centralizes model discovery and request routing so the app can use
local models, cloud models, or both without duplicating host/auth logic.
"""

from __future__ import annotations

import os
from typing import Any, Sequence
from urllib.parse import urlsplit, urlunsplit

import ollama


def _normalize_host(host: str | None) -> str | None:
    if not host:
        return None

    raw = host.strip()
    if not raw:
        return None

    if "://" not in raw:
        raw = f"http://{raw}"

    parts = urlsplit(raw)
    netloc = parts.netloc.replace("0.0.0.0", "127.0.0.1").replace("[::]", "localhost")
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def _local_hosts() -> list[str]:
    hosts: list[str] = []
    env_host = _normalize_host(os.getenv("OLLAMA_HOST"))
    if env_host:
        hosts.append(env_host)
    hosts.extend(["http://127.0.0.1:11434", "http://localhost:11434"])

    deduped: list[str] = []
    for host in hosts:
        if host not in deduped:
            deduped.append(host)
    return deduped


def _cloud_host(api_key: str | None) -> tuple[str, dict[str, str]] | None:
    if not api_key:
        return None
    token = api_key.strip()
    if not token:
        return None
    return "https://ollama.com", {"Authorization": f"Bearer {token}"}


def _clients(api_key: str | None = None) -> list[ollama.Client]:
    clients = [ollama.Client(host=host) for host in _local_hosts()]
    cloud = _cloud_host(api_key)
    if cloud:
        host, headers = cloud
        clients.append(ollama.Client(host=host, headers=headers))
    return clients


def list_models(api_key: str | None = None) -> list[str]:
    """
    Return local models, and cloud models if an API key is supplied.

    Returns an empty list when no Ollama endpoint is reachable.
    """
    models: list[str] = []
    for client in _clients(api_key):
        try:
            result = client.list()
        except Exception:
            continue

        if hasattr(result, "models"):
            names = [m.model for m in result.models]
        else:
            names = [m["name"] for m in result.get("models", [])]

        for name in names:
            if name not in models:
                models.append(name)

    return models


def resolve_model(preferred: str, api_key: str | None = None) -> tuple[str, list[str]]:
    models = list_models(api_key)
    if preferred in models:
        return preferred, models
    if models:
        return models[0], models
    return preferred, models


def chat_with_ollama(model: str, api_key: str | None = None, **kwargs: Any) -> Any:
    """
    Run a chat request against an appropriate Ollama endpoint.

    Cloud-only models use ollama.com when an API key is present. Otherwise we
    try the local daemon endpoints first.
    """
    cloud = _cloud_host(api_key)
    clients: list[ollama.Client] = []

    if model.endswith("-cloud") and cloud:
        host, headers = cloud
        clients.append(ollama.Client(host=host, headers=headers))

    clients.extend(_clients(api_key))

    # De-duplicate client base URLs by host string.
    unique: list[ollama.Client] = []
    seen_hosts: set[str] = set()
    for client in clients:
        host = getattr(getattr(client, "_client", None), "base_url", None)
        host_key = str(host) if host is not None else repr(client)
        if host_key in seen_hosts:
            continue
        seen_hosts.add(host_key)
        unique.append(client)

    last_exc: Exception | None = None
    for client in unique:
        try:
            return client.chat(model=model, **kwargs)
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            continue

    if last_exc is not None:
        raise last_exc
    raise ConnectionError("No Ollama endpoints were available")

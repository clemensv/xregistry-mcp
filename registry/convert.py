#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""mcp_manifest_convert

Directory-recursive converter from **source schema** manifests to the restricted
**target schema** with the following mapping:

* `mcpversion` ──► *dropped*
* `serverversion` ──► `version_detail.version` (`0.0.0` fallback if not SemVer)
* `repository.name` ──► root‐level `repo_ref`
* If `repository.url` points to GitHub, **overwrite**/create `name`
  as `io.github.<username>/<repository>`
* `endpoints.http` ──► extra element in `remotes`
* `deployment.container|sandbox` ──► extra element in `registries`
* Registry names **node/nodejs** (any case) ► **npm**
* Underscore variants (`transport_type`, …) ► camel form
* Output contains **only** keys listed in `ROOT_KEYS`

Converted files are written next to each source file, suffixed
`.converted.json`.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

_LOGGER = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s", stream=sys.stderr)

# --------------------------------------------------------------------------- #
# Target-schema keys
# --------------------------------------------------------------------------- #
ROOT_KEYS: set[str] = {
    "name",
    "description",
    "version_detail",
    "registries",
    "remotes",
    "repo_ref",
    "serverid",
    "epoch",
    "self",
    "xid",
    "documentation",
    "labels",
    "createdat",
    "modifiedat",
    "prompts",
    "tools",
    "resources",
}
REGISTRY_KEYS = {"name", "package_name", "license", "command_arguments"}
CMDARGS_KEYS = {
    "sub_commands",
    "positional_arguments",
    "environment_variables",
    "named_arguments",
}
ENVVAR_KEYS = {"name", "description", "required"}
REMOTE_KEYS = {"transporttype", "url", "subfolder", "branch", "commit", "license"}
PROMPT_KEYS = {"name", "description", "arguments"}
ARGUMENT_KEYS = {"name", "description", "required"}
TOOL_KEYS = {"name", "description", "inputschema"}
RESOURCE_KEYS = {"uritemplate", "name", "description", "mimetype"}

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
_GITHUB_RE = re.compile(r"^https?://github\.com/(?P<user>[^/]+)/(?P<repo>[^/.]+)")

# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _filter(obj: Dict[str, Any], allowed: set[str]) -> Dict[str, Any]:
    return {k: v for k, v in obj.items() if k in allowed}


def _as_semver(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw if _SEMVER_RE.match(raw) else "0.0.0"


def _github_name(url: str | None) -> Tuple[str | None, str | None]:
    """Return (<user>, <repo>) extracted from a GitHub URL; otherwise (None, None)."""
    if not url:
        return None, None
    m = _GITHUB_RE.match(url)
    if m:
        return m.group("user"), m.group("repo")
    return None, None


def _normalise_registry_name(name: str | None) -> str | None:
    return "npm" if name and name.lower() in {"node", "nodejs"} else name


def _make_cmdargs(positional: List[str] | None, env: List[Dict[str, Any]] | None) -> Dict[str, Any]:
    return {
        "sub_commands": [],
        "positional_arguments": positional or [],
        "environment_variables": [_filter(e, ENVVAR_KEYS) for e in env or [] if isinstance(e, dict)],
        "named_arguments": None,
    }


# --------------------------------------------------------------------------- #
# Deployment → registries
# --------------------------------------------------------------------------- #
def _container_to_registry(container: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": "container",
        "package_name": container.get("image", ""),
        "license": "",
        "command_arguments": _make_cmdargs(container.get("args"), container.get("env")),
    }


def _sandbox_to_registry(sandbox: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name": sandbox.get("runtime", "sandbox"),
        "package_name": sandbox.get("package", ""),
        "license": "",
        "command_arguments": _make_cmdargs(sandbox.get("args"), sandbox.get("env")),
    }


# --------------------------------------------------------------------------- #
# Endpoints.http → remotes
# --------------------------------------------------------------------------- #
def _http_endpoint_to_remote(http_ep: Dict[str, Any]) -> Dict[str, Any]:
    uri = http_ep.get("uri")
    if not uri:
        return {}
    return {"url": uri, "transporttype": urlparse(uri).scheme or "http"}


def _coerce_remote_keys(remote: Dict[str, Any]) -> Dict[str, Any]:
    if "transport_type" in remote:
        remote["transporttype"] = remote.pop("transport_type")
    return remote


# --------------------------------------------------------------------------- #
# Sanitisation
# --------------------------------------------------------------------------- #
def _sanitize_remotes(explicit: Any, endpoints: Dict[str, Any]) -> List[Dict[str, Any]]:
    remotes: List[Dict[str, Any]] = []
    if isinstance(explicit, list):
        for r in explicit:
            if isinstance(r, dict):
                remotes.append(_filter(_coerce_remote_keys(r), REMOTE_KEYS))
    if isinstance(endpoints.get("http"), dict):
        http_remote = _filter(_http_endpoint_to_remote(endpoints["http"]), REMOTE_KEYS)
        if http_remote:
            remotes.append(http_remote)
    return remotes


def _normalize_registry(reg: Dict[str, Any]) -> Dict[str, Any]:
    if "name" in reg:
        reg["name"] = _normalise_registry_name(reg["name"])
    if isinstance(reg.get("command_arguments"), dict):
        reg["command_arguments"] = _filter(reg["command_arguments"], CMDARGS_KEYS)
    return _filter(reg, REGISTRY_KEYS)


def _sanitize_registries(explicit: Any, deployment: Dict[str, Any]) -> List[Dict[str, Any]]:
    regs: List[Dict[str, Any]] = []
    if isinstance(explicit, list):
        regs += [_normalize_registry(r) for r in explicit if isinstance(r, dict)]
    if isinstance(deployment, dict):
        if isinstance(deployment.get("container"), dict):
            regs.append(_normalize_registry(_container_to_registry(deployment["container"])))
        if isinstance(deployment.get("sandbox"), dict):
            regs.append(_normalize_registry(_sandbox_to_registry(deployment["sandbox"])))
    return regs


def _sanitize_prompts(prompts: Any) -> List[Dict[str, Any]]:
    if not isinstance(prompts, list):
        return []
    out: List[Dict[str, Any]] = []
    for p in prompts:
        if not isinstance(p, dict):
            continue
        cleaned = _filter(p, PROMPT_KEYS)
        if isinstance(cleaned.get("arguments"), list):
            cleaned["arguments"] = [
                _filter(a, ARGUMENT_KEYS) for a in cleaned["arguments"] if isinstance(a, dict)
            ]
        out.append(cleaned)
    return out


def _sanitize_tools(tools: Any) -> List[Dict[str, Any]]:
    return [_filter(t, TOOL_KEYS) for t in tools if isinstance(t, dict)] if isinstance(tools, list) else []


def _sanitize_resources(res: Any) -> List[Dict[str, Any]]:
    return [_filter(r, RESOURCE_KEYS) for r in res if isinstance(r, dict)] if isinstance(res, list) else []


def _sanitize_labels(labels: Any) -> Dict[str, str]:
    return {k: str(v) for k, v in labels.items() if isinstance(k, str)} if isinstance(labels, dict) else {}


# --------------------------------------------------------------------------- #
# Conversion
# --------------------------------------------------------------------------- #
def convert_manifest(src: Dict[str, Any]) -> Dict[str, Any]:
    tgt: Dict[str, Any] = {}

    # repo_ref & GitHub-based name construction
    if isinstance(src.get("repository"), dict):
        repo_info = src["repository"]
        if repo_info.get("name"):
            tgt["repo_ref"] = repo_info["name"]
        user, repo = _github_name(repo_info.get("url"))
        if user and repo:
            tgt["name"] = f"io.github.{user}/{repo}"

    # name fallback if not set by GitHub logic
    tgt.setdefault("name", src.get("name"))

    # description
    if "description" in src:
        tgt["description"] = src["description"]

    # version_detail
    semver = _as_semver(src.get("serverversion"))
    if semver:
        tgt["version_detail"] = {"version": semver}

    # collections
    tgt["remotes"] = _sanitize_remotes(src.get("remotes"), src.get("endpoints", {}))
    tgt["registries"] = _sanitize_registries(src.get("registries"), src.get("deployment", {}))
    tgt["prompts"] = _sanitize_prompts(src.get("prompts"))
    tgt["tools"] = _sanitize_tools(src.get("tools"))
    tgt["resources"] = _sanitize_resources(src.get("resources"))

    # misc scalars
    for key in ("serverid", "epoch", "self", "xid", "documentation", "createdat", "modifiedat"):
        if key in src:
            tgt[key] = src[key]

    if "labels" in src:
        tgt["labels"] = _sanitize_labels(src["labels"])

    return {k: v for k, v in tgt.items() if k in ROOT_KEYS}


# --------------------------------------------------------------------------- #
# File processing
# --------------------------------------------------------------------------- #
def _convert_file(path: Path) -> None:
    _LOGGER.info("Processing %s", path)
    try:
        with path.open("r", encoding="utf-8") as fh:
            source = json.load(fh)
        converted = convert_manifest(source)
        out = path.with_suffix(".json")
        with out.open("w", encoding="utf-8", newline="\r\n") as fh:
            json.dump(converted, fh, ensure_ascii=False, indent=2)
        _LOGGER.info("Wrote %s", out)
    except (json.JSONDecodeError, OSError) as err:
        _LOGGER.error("Failed %s – %s", path, err)


def _scan(root: Path) -> List[Path]:
    return list(root.rglob("*.json"))


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def _parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="mcp_manifest_convert",
        description=(
            "Convert MCP source manifests to restricted target schema "
            "(repository.name → repo_ref, GitHub URL → canonical name, "
            "endpoints.http → remotes, deployment → registries, node→npm)."
        ),
    )
    p.add_argument("directory", type=Path, help="Directory to traverse recursively.")
    return p.parse_args(argv)


def main(argv: List[str] | None = None) -> None:
    args = _parse_args(argv or sys.argv[1:])
    if not args.directory.exists():
        _LOGGER.error("Directory %s not found", args.directory)
        sys.exit(1)
    for jf in _scan(args.directory):
        _convert_file(jf)


if __name__ == "__main__":
    main()

#
# Copyright (c) 2026, Axius SDC, Inc.
# Licensed under the Apache License, Version 2.0.
#
"""
MCP stdio server for `sdccdif`: one tool, `write_cdif`, over the same function the CLI calls.

An agent that can read a published model with `sdcreader` can ask this server for its CDIF description.
The scaffold (JSON-RPC over stdio, protocol negotiation, `isError` results, the package cache) is `sdcreader.mcp`,
shared by every SDC projection server. No tool takes a URL: the catalog host is fixed at start with `--host`.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from sdcreader.mcp import PackageCache, Server, ToolError, source_properties, str_arg
from sdcreader.package import DEFAULT_HOST, fetch_package  # noqa: F401  (patched by tests)

from sdccdif import __version__
from sdccdif.cdif import load_declared, write_cdif

SERVER_NAME = "sdccdif"
ISSUES = "https://github.com/SemanticDataCharter/sdc_cdif/issues"

_HOST: str = DEFAULT_HOST
_CACHE: dict = {}

TOOLS = [
    {
        "name": "write_cdif",
        "description": (
            "Write the CODATA CDIF description (JSON-LD: Discovery, Data Description with every variable, Codelists, and the sentinel domain for the sixteen exceptional values) of one published Semantic Data Charter model. The document cites the model's schema by URL and SHA-256. Validated in this package's CI with CDIF's own framing, JSON Schema and SHACL checks from a pinned snapshot."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                **source_properties(plural=False),
                "contact_name": {"type": "string", "description": "The publisher's contact point name; the package's declared default applies when omitted."},
                "contact_email": {"type": "string", "description": "The publisher's contact e-mail; the package's declared default applies when omitted."},
                "date": {"type": "string", "description": "The catalog date, YYYY-MM-DD; today when omitted."}
            },
            "additionalProperties": False,
        },
    },
]


def _cache() -> PackageCache:
    import sdccdif.mcp_server as me

    return PackageCache(host=_HOST, storage=_CACHE, fetcher=lambda ct_id, host: me.fetch_package(ct_id, host=host))


def _date(args: dict[str, Any]) -> date | None:
    v = str_arg(args, "date")
    if v is None:
        return None
    try:
        return date.fromisoformat(v)
    except ValueError as exc:
        raise ToolError("`date` must be YYYY-MM-DD.") from exc


def _format(args: dict[str, Any]) -> str:
    fmt = str_arg(args, "format", "turtle")
    if fmt not in ("turtle", "json-ld"):
        raise ToolError("`format` must be turtle or json-ld.")
    return fmt


def _handle_write(args: dict[str, Any]) -> Any:
    pkg, model = _cache().one(args)
    today = _date(args)
    try:
        declared = load_declared(str_arg(args, "contact_name"), str_arg(args, "contact_email"))
    except Exception as exc:
        raise ToolError(str(exc)) from exc
    doc = write_cdif(model, today=today, declared=declared)
    return {
        "ct_id": model.ct_id, "title": model.title, "standard": "CDIF (CODATA Cross-Domain Interoperability Framework)",
        "schema_url_pinned": pkg.schema_url_pinned,
        "variables": len(doc["@graph"][0]["schema:variableMeasured"]), "codelists": len(doc["@graph"]) - 3,
        "document": doc,
        "note": "Validated in this package's CI against CDIF's own framing, JSON Schema and SHACL checks; the validators are not shipped in the wheel.",
    }


TOOL_HANDLERS = {"write_cdif": _handle_write}


def _server() -> Server:
    return Server(
        name=SERVER_NAME, version=__version__, tools=TOOLS, handlers=TOOL_HANDLERS, issues_url=ISSUES,
        instructions=(
            "Describe published Semantic Data Charter models in CDIF terms. `write_cdif` takes "
            + ("model identifiers (ct_ids), fetched from " if False else "a model identifier (ct_id), fetched from ")
            + f"{_HOST}, or package directories on disk, and returns the CDIF JSON-LD document under `document`. "
            "Read-only apart from the document it returns; no account; no tool takes a URL."
        ),
    )


def _handle_request(request: Any) -> dict | None:
    return _server().handle(request)


def main(argv: list[str] | None = None) -> None:
    """Entry point for `sdccdif-mcp` and `sdccdif mcp`."""
    import argparse

    global _HOST

    parser = argparse.ArgumentParser(prog="sdccdif-mcp", description="MCP stdio server: CDIF descriptions of published Semantic Data Charter models.")
    parser.add_argument("--host", default=DEFAULT_HOST,
                        help=f"The SDCStudio host whose public catalog is read, fixed here so a caller cannot redirect the server. Default {DEFAULT_HOST}.")
    args = parser.parse_args(argv)
    _HOST = args.host.rstrip("/")
    _server().run_stdio()


if __name__ == "__main__":
    main()

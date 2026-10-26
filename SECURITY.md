# Security

Report a vulnerability privately to security@axius-sdc.com. Please do not open a public issue. The organization
policy is at https://github.com/SemanticDataCharter/.github/blob/main/SECURITY.md. Expect an acknowledgement within
three business days, and a fix released before anything is made public.

## Supported versions

| version | supported |
|---|---|
| 4.1.x | yes |
| earlier | no |

## What counts as a vulnerability here

This package writes a published Semantic Data Charter model as a CDIF description. A description that states as fact
something the model package does not establish (a default published as a fact, a schema cited by a hash that does
not match its bytes), or output that claims conformance to CDIF and does not conform, is in scope.

## The MCP server, as a threat model

`sdccdif-mcp` speaks JSON-RPC over stdio. There is no authentication and no network listener: whoever can write to
the process's stdin is the caller. Package directories are read as the process's user; run it as an account that
can read only what it should. The server makes no network requests and writes no files.

Out of scope: the authenticity of a model package the caller supplies.

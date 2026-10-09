# Pinned snapshot

Copied 8 October 2026 from `Cross-Domain-Interoperability-Framework/metadataBuildingBlocks` at commit 61f24aa
(2026-10-06): the cdifCodelist building block's JSON Schema, context, rules and conformance SHACL. The codelist
nodes the writer emits are validated against these; the dataset node is validated against the validation repository
snapshot beside this directory.

Added the same day: `_sources/cdifDataType/{cdifInstanceVariable,cdifDataStructureComponent,cdifProvActivity}/rules.shacl`,
the per-class rules `detect_conformance.py` gates a profile on, so the tests' conformance check runs offline at the pin
(`CDIF_BB_DIR` points here).

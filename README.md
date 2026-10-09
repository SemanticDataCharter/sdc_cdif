# sdc_cdif

One Semantic Data Charter model, described in CDIF.

`sdccdif` reads a published SDC model's package and writes the CDIF JSON-LD that describes the collection of
Governed Data Records conforming to it: Core and Discovery for the dataset, Data Description for every leaf of the
record, a Codelist for every enumerated leaf, and one sentinel value domain for the reference model's sixteen
exceptional values. The output is checked with CDIF's own frame, JSON Schemas, SHACL and conformance validator, at a
pinned commit of their `validation` repository.

## 1. What this is, and where it came from

The sample document, `samples/nhanes-participant/cdif-dm-xy8upneajsb8vdcmnve01g6g.jsonld`, describes the records of
one published model: **NHANES Participant** (`dm-xy8upneajsb8vdcmnve01g6g`) from the FAIR Data Demo, a demographic,
examination and laboratory record of the National Health and Nutrition Examination Survey (CDC). The model is public:

- the catalog record: https://sdcstudio.axius-sdc.com/api/v1/catalog/dm/xy8upneajsb8vdcmnve01g6g/
- the schema the records conform to: https://sdcstudio.axius-sdc.com/dmlib/dm-xy8upneajsb8vdcmnve01g6g.xsd
- the Semantic Data Charter: https://semanticdatacharter.com

The writer reads the package (the model's JSON-LD and its schema), the public catalog record and the published
schema versions. It needs no account, and it refuses a model whose package was never built: the schema and the
JSON-LD are the evidence it describes, and nothing is written that they do not carry.

```
pip install -e ".[fetch]"
sdccdif write --package samples/nhanes-participant --out cdif.jsonld
sdccdif write --ct-id xy8upneajsb8vdcmnve01g6g --save-package pkg/ --out cdif.jsonld   # any published model, from the catalog
```

What the document contains, for the NHANES Participant model:

| | |
|---|---|
| `schema:Dataset` | the collection of records conforming to the model: name, description, identifier, URL, dates, language, licence from the model's rights, creator, publisher with a contact point, keywords; and, when the modeler wrote them in the model's Dublin Core, the publisher's name, subject keywords, contributors and coverage (`schema:spatialCoverage` as a named Place) |
| `schema:publishingPrinciples` | the permanence page: a published model is immutable, a change is a new model naming the one it revised |
| `dcterms:conformsTo` | the schema, by its published URL with `?sha256=` and an `spdx:Checksum` of the bytes |
| `schema:variableMeasured` | 153 `cdi:InstanceVariable`s, one per leaf of the record in document order, with the path, the library slot as `schema:propertyID`, the `skos:exactMatch` concepts as `cdif:uses`, the XSD datatype, unit, range, a substantive value domain and the shared sentinel domain |
| `cdif:role` | the respondent sequence number is the `UnitIdentifier`; the governance leaves (audit event, PROV activity and agent) are `Attribute`s qualifying it; everything else is a `Measure` |
| `cdif:hasPrimaryKey` | the unit identifier |
| 67 `skos:ConceptScheme`s | one per enumerated component, each value as `skos:notation` with its definition and the code it is defined by; a component composed three times is one codelist referenced three times |
| 1 `cdif:SentinelValueDomain` | the SDC4 exceptional values (`NI`, `MSK`, `INV`, `DER`, `UNC`, `OTH`, `NINF`, `PINF`, `UNK`, `ASKR`, `NASK`, `QS`, `TRC`, `ASKU`, `NAV`, `NA`) as a `skos:ConceptScheme`, referenced by every variable |
| `dcat:CatalogRecord` | declares `cdif/core/1.1`, `cdif/discovery/1.1` and `cdif/data_description/1.1` |

## 2. How to verify it

The tests run CDIF's validators from `data/`, where their artifacts are copied at the pinned commits (`validation`
129085c, `metadataBuildingBlocks` 61f24aa; `build/snapshot_cdif.py` verifies the pins before copying):

```
pip install -e ".[dev]"
python -m pytest tests -q
```

Or run their conformance validator directly on the sample:

```
cd data/cdif-129085c
python ConformanceValidate.py ../../samples/nhanes-participant/cdif-dm-xy8upneajsb8vdcmnve01g6g.jsonld --source local --frame CDIF-frame-2026.jsonld
```

Result at the pin: Core SHACL passed; Discovery JSON Schema and SHACL passed; Data Description JSON Schema and SHACL
passed; 0 violations; the three declared profiles consistent with the profiles the detector finds in the content.
Every codelist node passes the cdifCodelist building block's JSON Schema, `rules.shacl` and `conformance.shacl`.

## 3. What the projection could not say

Left out rather than filled in, because the package does not carry it: a distribution of the records (the records
are not public; the model is), temporal coverage, statistics. CDIF marks all of these recommended, not required.
The model's own Dublin Core (subject, coverage, publisher, contributors, relation) is read from the schema header
and published when the modeler wrote it; SDCStudio's field defaults ("Universal" for coverage, "None" for relation,
blanks) read as unset, which is why the NHANES document carries none of them: its modeler left them at the defaults. One recommended item is declared rather than read from the package, and said so here: the publisher's
contact point (`contact@axius-sdc.com` on the sample, in `src/sdccdif/data/declared.json`; `--contact-name` and
`--contact-email` override it, and an empty address omits it).

And in the other direction, what the record carries that the description has no place for, stated so a reader knows
where to look rather than as a shortcoming of either side:

- **The governance envelope is data in every record.** Each Governed Data Record carries its own audit event, PROV
  activity and PROV agent as leaves, validated with the rest. CDIF's provenance is a property of the dataset. The
  writer lists those leaves as variables with the `Attribute` role, so a reader can see they are there; the per-record
  values live in the records.
- **The schema is bound to each record, not only to the collection.** Every record names the schema it was validated
  against, and the schema never changes after publication. The description can say that once, on the dataset, which
  is what `dcterms:conformsTo` with the SHA-256 and `schema:publishingPrinciples` do.
- **The reason a value is missing is typed in the record.** A leaf may carry one of the sixteen exceptional values in
  place of its value, so a refusal, a value not asked for, and a value masked for privacy are different facts. CDIF's
  sentinel value domain describes the set; which reason applies, and where, is in the record.

## 4. What we learned about the CDIF profiles

Implementer's notes from building this against the artifacts at the pins above. They describe how the artifacts
behave, so the next implementer spends the day on their own document rather than on these.

- **The frame embeds every referenced node.** `CDIF-frame-2026.jsonld` carries `@embed: @always` throughout, so a
  node referenced from many places (here, one sentinel domain referenced by 153 variables) is repeated at every
  reference in the framed tree. Harmless for validation; the framed document is many times the size of the source.
  Sibling `@graph` nodes that are not a `schema:Dataset` (the codelists) do not appear in the framed output and are
  validated separately against the codelist building block.
- **`cdif:role: Attribute` requires `cdif:qualifies`.** The Data Description SHACL asks every attribute to name the
  variable it qualifies, following DDI-CDI. A record-level attribute has the record's unit identifier to point at,
  which is what this writer does.
- **The conformance detector gates Data Description on the instance-variable rules.** `detect_conformance.py` reports
  a profile as present only when its per-class SHACL passes, so a document that declares Data Description and fails
  those rules is reported as over-claiming the profile rather than as failing it. Reading the SHACL section first
  explains the conformance section.
- **The local conformance map has JSON Schemas for Discovery, Data Description and Complete.** Core is checked by
  SHACL only (`no schema mapped` is the expected line), and the Codelist profile has no entry, so a codelist cannot
  be declared on the catalog record and checked through `ConformanceValidate.py`; the building block's own schema and
  rules check it directly.
- **`cdif:physicalDataType` takes a string or a reference**, and CDIF's own examples use both (`"xsd:integer"` and a
  full XML Schema URL). The string form is used here.
- **IRI-shaped values must be IRI references.** `schema:propertyID` and `schema:additionalType` written as strings
  that look like IRIs or CURIEs are SHACL violations; `{"@id": ...}` is the accepted form. Plain labels remain
  strings.
- **The SKOS prefix is not in the frame's context**, so framed output shows full SKOS IRIs until the validator's
  compaction step adds it. Expected; noted so the intermediate output does not alarm anyone.

## Layout

- `src/sdccdif/`: `package.py` (a model's package, from a directory or the public catalog), `model.py` (the record
  tree, and the definitions and codes behind each enumerated value, read from the schema), `cdif.py` (the JSON-LD),
  `cli.py`, `data/sdc4-exceptional-values.json` (the sixteen exceptional values, extracted from the SDC4 reference
  model schema).
- `data/cdif-129085c/`: CDIF's context, frame, JSON Schemas, SHACL, conformance map and validators.
  `data/mbb-61f24aa/`: the cdifCodelist building block and the three per-class rules the detector gates on.
- `samples/nhanes-participant/`: the model's package as fetched and the document written from it.
- `build/snapshot_cdif.py`: re-creates `data/` from read-only clones of the CDIF repositories at the pinned commits.

## Licences

Apache-2.0 (see `LICENSE`, `NOTICE`). The CDIF artifacts in `data/` keep their own licences: the `validation`
repository is CC0; the building blocks are CC BY 4.0, CODATA and the Cross-Domain Interoperability Framework.

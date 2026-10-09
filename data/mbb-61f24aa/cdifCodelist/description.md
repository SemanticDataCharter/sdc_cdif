# CDIF Codelist

A controlled-vocabulary **codelist** modeled as a `skos:ConceptScheme` constrained for CDIF use.

The scheme carries a resolvable `@id`, CDIF metadata (`schema:identifier`, `schema:dateModified`, `schema:license` or `schema:conditionsOfAccess`), and identifies its top concepts via `skos:hasTopConcept`. Each member concept is a `CdifCodelistConcept`:

- **Required:** `@id`, `skos:inScheme`, `skos:prefLabel`, `skos:notation`
- **Optional:** `skos:definition` and any other SKOS properties (JSON-LD is open-world)
- **Hierarchy:** where it exists, both `skos:narrower` (for JSON tree traversal) and `skos:broader` (for upward navigation) must be explicit; an inline narrower concept must declare `skos:broader` back to its parent.

CDIF `schema:` metadata properties take precedence over the equivalent `dcterms:` properties from the base `skos:ConceptScheme`.

## Consumers

- **`CDIFCodelistProfile`** — the codelist profile composes this building block.
- **`cdifEnumerationDomain`** — references a codelist (by value or by `@id`) via `cdif:references` to define the allowed values of an enumerated value domain.

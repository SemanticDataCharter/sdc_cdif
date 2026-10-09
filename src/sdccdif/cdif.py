"""Emit the CDIF JSON-LD for one model: a schema:Dataset for its governed data records, an InstanceVariable per leaf,
a codelist per enumerated leaf, one sentinel value domain for the reference model's exceptional values.

Everything written here is read from the package or the reference model; nothing is invented. Where CDIF asks for
what the package does not carry (a contact e-mail, a distribution of the records), the property is left out rather
than filled in, and the document declares only the profiles it satisfies: Core, Discovery and Data Description 1.1.
"""
from __future__ import annotations

import json
import re
from datetime import date
from importlib import resources
from urllib.parse import quote

from .model import CLOSE, EXACT, HAS_UNIT, IDENTIFIER, NUMERIC_TYPES, QUANTIFIED_TYPES, SOURCE, Code, Leaf, Model, enumeration_iri

CONTEXT = {
    "schema": "http://schema.org/",
    "dcterms": "http://purl.org/dc/terms/",
    "dcat": "http://www.w3.org/ns/dcat#",
    "prov": "http://www.w3.org/ns/prov#",
    "spdx": "http://spdx.org/rdf/terms#",
    "skos": "http://www.w3.org/2004/02/skos/core#",
    "xsd": "http://www.w3.org/2001/XMLSchema#",
    "cdi": "http://ddialliance.org/Specification/DDI-CDI/1.0/RDF/",
    "cdif": "https://w3id.org/cdif/",
    "sdc4": "https://semanticdatacharter.com/ns/sdc4/",
}
PROFILES = ["https://w3id.org/cdif/core/1.1", "https://w3id.org/cdif/discovery/1.1", "https://w3id.org/cdif/data_description/1.1"]
PUBLISHER = {"@id": "https://axius-sdc.com", "@type": ["schema:Organization"], "schema:name": "Axius SDC, Inc.", "schema:url": "https://axius-sdc.com"}


def load_declared(contact_name: str | None = None, contact_email: str | None = None) -> dict:
    """The declared input: the package's default, with command-line overrides. An empty e-mail means no contact point."""
    d = json.loads(resources.files("sdccdif").joinpath("data/declared.json").read_text(encoding="utf-8"))
    contact = dict(d.get("contact") or {})
    if contact_name is not None:
        contact["name"] = contact_name
    if contact_email is not None:
        contact["email"] = contact_email
    d["contact"] = contact
    return d


def _publisher(declared: dict | None) -> dict:
    p = dict(PUBLISHER)
    contact = (declared or {}).get("contact") or {}
    email = (contact.get("email") or "").strip()
    if email:
        p["schema:contactPoint"] = {"@type": ["schema:ContactPoint"], "schema:name": contact.get("name") or p["schema:name"], "schema:email": email}
    return p
PERMANENCE = {
    "@id": "https://semanticdatacharter.com/permanence.html",
    "@type": ["schema:CreativeWork"],
    "schema:name": "Permanence Architecture",
    "schema:description": "A published Semantic Data Charter model is immutable: its schema never changes after publication, a change is a "
                          "new model that records what it revised, and every record names the schema it was validated against.",
    "schema:url": "https://semanticdatacharter.com/permanence.html",
}
PROVGOV_SLOT = "https://axius-sdc.com/library/provgov/"
UNIT_IDENTIFIER_KEYS = ("sequence-number", "-identifier", "-id", "-number")


def write_cdif(model: Model, today: date | None = None, declared: dict | None = None) -> dict:
    today = today or date.today()
    declared = load_declared() if declared is None else declared
    publisher = _publisher(declared)
    pkg = model.package
    ds_id = pkg.catalog_url
    date_modified = (model.metadata.get("dc:date") or "")[:10] or today.isoformat()
    license_iri = _license(model.metadata.get("dc:rights") or "")
    graph: list[dict] = []
    schemes: dict[str, dict] = {}
    sentinel_id = f"{ds_id}#sentinel-values"
    ev_scheme = _exceptional_values_scheme(today)

    variables = []
    seen_slugs: dict[str, int] = {}
    for leaf in model.leaves:
        slug = leaf.slug
        n = seen_slugs.get(slug, 0)
        seen_slugs[slug] = n + 1
        if n:
            slug = f"{slug}-{n + 1}"
        variables.append(_variable(model, leaf, f"{ds_id}#{slug}", sentinel_id, schemes, date_modified, license_iri))
    # An attribute qualifies a variable (DDI-CDI): the record's governance leaves (audit event, PROV activity and agent)
    # qualify the record, which the unit identifier names. A model with no unit identifier has no attributes, only measures.
    unit_ids = [v["@id"] for v in variables if v["cdif:role"] == "UnitIdentifier"]
    for v in variables:
        if v["cdif:role"] == "Attribute":
            if unit_ids:
                v["cdif:qualifies"] = {"@id": unit_ids[0]}
            else:
                v["cdif:role"] = "Measure"
    primary_key = None
    if unit_ids:
        primary_key = {"@id": f"{ds_id}#primary-key", "@type": ["cdif:Key"],
                       "cdif:isComposedOf": [{"@type": ["cdi:ComponentPosition"], "cdi:indexes": {"@id": u}, "cdi:value": i + 1}
                                             for i, u in enumerate(unit_ids)]}

    dataset = {
        "@id": ds_id,
        "@type": ["schema:Dataset"],
        "schema:name": f"{model.title} governed data records",
        "schema:description": _dataset_description(model, date_modified),
        "schema:identifier": {"@type": ["schema:PropertyValue"], "schema:propertyID": "SDC4 model identifier",
                              "schema:value": f"dm-{model.ct_id}", "schema:url": ds_id},
        "schema:sameAs": [{"@id": f"{CONTEXT['sdc4']}dm-{model.ct_id}"}],
        "schema:url": ds_id,
        "schema:dateModified": date_modified,
        "schema:datePublished": date_modified,
        "schema:inLanguage": model.metadata.get("dc:language") or "en-US",
        "schema:keywords": _keywords(model),
        "schema:publisher": publisher,
        "schema:publishingPrinciples": PERMANENCE,
        "dcterms:conformsTo": [_schema_citation(model)],
        "schema:variableMeasured": variables,
        "schema:subjectOf": {
            "@id": f"{ds_id}#cdif-record",
            "@type": ["schema:Dataset"],
            "schema:additionalType": [{"@id": "dcat:CatalogRecord"}],
            "schema:name": f"CDIF description of {model.title}",
            "schema:about": {"@id": ds_id},
            "schema:sdDatePublished": today.isoformat(),
            "schema:maintainer": publisher,
            "dcterms:conformsTo": [{"@id": p} for p in PROFILES],
        },
    }
    if primary_key:
        dataset["cdif:hasPrimaryKey"] = primary_key
    if license_iri:
        dataset["schema:license"] = [{"@id": license_iri}]
    else:
        dataset["schema:conditionsOfAccess"] = [model.metadata.get("dc:rights") or "Not stated in the package."]
    creator = model.metadata.get("dc:creator")
    if creator:
        dataset["schema:creator"] = [{"@type": ["schema:Person"], "schema:name": creator}]

    graph.append(dataset)
    graph.append({
        "@id": sentinel_id,
        "@type": ["cdif:SentinelValueDomain"],
        "cdif:displayLabel": "SDC4 exceptional values",
        "cdif:recommendedDataType": ["xsd:string"],
        "cdif:takesValuesFrom": {
            "@id": f"{sentinel_id}/enumeration",
            "@type": ["cdif:EnumerationDomain"],
            "schema:name": "SDC4 exceptional values",
            "cdif:purpose": "Why a value is missing or outside its measurable range. Every leaf of an SDC4 record may carry one "
                            "exceptional value in place of its value; the sixteen are defined by the reference model.",
            "cdif:references": {"@id": ev_scheme["@id"]},
        },
    })
    graph.append(ev_scheme)
    graph.extend(schemes.values())
    return {"@context": CONTEXT, "@graph": graph}


def _variable(model: Model, leaf: Leaf, var_id: str, sentinel_id: str, schemes: dict, date_modified: str, license_iri: str) -> dict:
    c = leaf.component
    slot = c.link(IDENTIFIER)
    v = {
        "@id": var_id,
        "@type": ["schema:PropertyValue", "cdi:InstanceVariable"],
        "schema:name": c.label,
        "schema:alternateName": [leaf.slug],
        "schema:description": c.description if len(c.description) >= 10 else f"{c.label}: an {c.sdc_type} of the {model.title} record.",
        "schema:propertyID": [{"@id": slot or c.iri}],
        "schema:url": c.iri,
        "cdif:name": [f"ms-{c.ct_id}"],
        "cdif:displayLabel": [c.label],
        "cdif:physicalDataType": c.data_type or "xsd:string",
        "cdif:role": _role(c, slot),
        "cdi:takesSentinelValuesFrom": [{"@id": sentinel_id}],
    }
    concepts = [{"@id": o} for p in (EXACT, CLOSE) for o in c.links.get(p, [])]
    if concepts:
        v["cdif:uses"] = concepts
    if c.sdc_type in QUANTIFIED_TYPES:
        units = _units(model, c)
        if units:
            v["schema:unitText"] = " | ".join(units)
            if len(units) == 1:
                v["cdif:simpleUnitOfMeasure"] = units[0]
    if c.sdc_type in NUMERIC_TYPES:
        for src, dst in (("minInclusive", "schema:minValue"), ("maxInclusive", "schema:maxValue")):
            if src in c.constraints:
                v[dst] = c.constraints[src]
    v["cdi:takesSubstantiveValuesFrom"] = _substantive(model, leaf, var_id, schemes, date_modified, license_iri)
    return v


def _substantive(model: Model, leaf: Leaf, var_id: str, schemes: dict, date_modified: str, license_iri: str) -> dict:
    c = leaf.component
    codes = model.codes.get(c.ct_id)
    dom = {"@id": f"{var_id}/substantive-values", "@type": ["cdif:SubstantiveValueDomain"], "cdif:displayLabel": f"Values of {c.label}"}
    if codes and c.sdc_type in ("XdToken", "XdString", "XdTokenList", "XdStringList"):
        scheme_id = enumeration_iri(c, codes)
        if scheme_id not in schemes:
            schemes[scheme_id] = _scheme(model, c, codes, scheme_id, date_modified, license_iri)
        dom["cdif:takesValuesFrom"] = {"@id": f"{var_id}/enumeration", "@type": ["cdif:EnumerationDomain"],
                                       "schema:name": f"{c.label} values", "cdif:references": {"@id": scheme_id}}
        return dom
    dom["cdif:recommendedDataType"] = [c.data_type or "xsd:string"]
    desc = {}
    if c.constraints.get("pattern"):
        desc["cdi:regularExpression"] = c.constraints["pattern"]
    for src, dst in (("minInclusive", "cdi:minimumValueInclusive"), ("maxInclusive", "cdi:maximumValueInclusive"),
                     ("minExclusive", "cdi:minimumValueExclusive"), ("maxExclusive", "cdi:maximumValueExclusive")):
        if src in c.constraints:
            desc[dst] = str(c.constraints[src])
    if desc:
        desc["@type"] = ["cdi:ValueAndConceptDescription"]
        dom["cdi:isDescribedBy"] = desc
    return dom


def _scheme(model: Model, c, codes: list[Code], scheme_id: str, date_modified: str, license_iri: str) -> dict:
    s = {
        "@id": scheme_id,
        "@type": ["skos:ConceptScheme"],
        "skos:prefLabel": f"{c.label} values",
        "skos:definition": c.description or f"The values {c.label} takes in the {model.title} record.",
        "schema:identifier": scheme_id,
        "schema:dateModified": date_modified,
        "schema:url": model.package.schema_url_pinned,
        "skos:hasTopConcept": [],
    }
    if license_iri:
        s["schema:license"] = [{"@id": license_iri}]
    else:
        s["schema:conditionsOfAccess"] = ["As the model it belongs to."]
    sources = c.links.get(SOURCE, [])
    if sources:
        s["dcterms:source"] = [{"@id": x} for x in sources]
    for code in codes:
        concept = {
            "@id": code.iri or f"{scheme_id}/{quote(code.value, safe='')}",
            "@type": ["skos:Concept"],
            "skos:prefLabel": code.value,
            "skos:notation": code.value,
            "skos:inScheme": [{"@id": scheme_id}],
        }
        if code.definition:
            concept["skos:definition"] = code.definition
        if code.defined_by:
            concept["skos:exactMatch"] = [{"@id": code.defined_by}]
        s["skos:hasTopConcept"].append(concept)
    return s


def _exceptional_values_scheme(today: date) -> dict:
    snap = json.loads(resources.files("sdccdif").joinpath("data/sdc4-exceptional-values.json").read_text(encoding="utf-8"))
    scheme_id = f"{snap['base']}ExceptionalValueType"
    return {
        "@id": scheme_id,
        "@type": ["skos:ConceptScheme"],
        "skos:prefLabel": "SDC4 exceptional values",
        "skos:definition": "The sixteen reasons the SDC4 reference model gives for a value being missing or outside its measurable "
                           "range, each a restriction of ExceptionalValueType.",
        "schema:identifier": scheme_id,
        "schema:dateModified": snap["fetched"],
        "schema:url": snap["source"],
        "schema:conditionsOfAccess": [f"Defined in the SDC4 reference model schema {snap['source']} (SHA-256 {snap['sha256']})."],
        "skos:hasTopConcept": [{
            "@id": f"{snap['base']}{v['type']}",
            "@type": ["skos:Concept"],
            "skos:prefLabel": v["name"],
            "skos:notation": v["code"],
            "skos:definition": v["definition"],
            "skos:inScheme": [{"@id": scheme_id}],
        } for v in snap["values"]],
    }


def _schema_citation(model: Model) -> dict:
    pkg = model.package
    return {
        "@id": pkg.schema_url_pinned,
        "@type": ["schema:CreativeWork"],
        "schema:name": f"SDC4 schema dm-{model.ct_id} ({model.title})",
        "schema:url": pkg.schema_url_pinned,
        "schema:encodingFormat": ["application/xml"],
        "schema:version": pkg.sha256,
        "dcterms:isVersionOf": {"@id": pkg.schema_url},
        "spdx:checksum": {"@type": ["spdx:Checksum"], "spdx:algorithm": "checksumAlgorithm_sha256", "spdx:checksumValue": pkg.sha256},
    }


def _dataset_description(model: Model, date_modified: str) -> str:
    base = model.description.strip().rstrip(".")
    return (f"{base}. Each record is a governed data record conforming to the SDC4 model {model.title} (dm-{model.ct_id}), published "
            f"{date_modified}. The schema is immutable and cited by URL and SHA-256 in dcterms:conformsTo; every leaf of a record may carry "
            f"one of the reference model's exceptional values in place of its value, the sentinel domain shared by all variables.")


def _keywords(model: Model) -> list[str]:
    words = ["Semantic Data Charter", "SDC4", "governed data record"]
    project = model.package.catalog.get("project_name")
    if project:
        words.insert(0, project)
    return words


def _role(c, slot: str | None) -> str:
    if slot and slot.startswith(PROVGOV_SLOT):
        return "Attribute"
    key = (slot or "").rsplit("/", 1)[-1]
    if key and key.endswith(UNIT_IDENTIFIER_KEYS) and c.sdc_type in ("XdString", "XdToken", "XdCount"):
        return "UnitIdentifier"
    return "Measure"


def _units(model: Model, c) -> list[str]:
    u = (c.constraints.get("units") or {}).get("@id") or c.link(HAS_UNIT)
    if not u:
        return []
    uc = model.components.get(u.split("mc-", 1)[1])
    if not uc:
        return []
    return list(uc.constraints.get("enumeration") or [])


def _license(rights: str) -> str:
    m = re.search(r"https?://\S+", rights)
    return m.group(0).rstrip(".,;") if m else ""

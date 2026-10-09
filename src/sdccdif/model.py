"""Read a model package into the shape the CDIF emitter needs: the record tree, its leaves in document order with
their path, the enumerations with the definitions and codes the schema carries, the units each quantity takes.

The JSON-LD package carries every component once, with `contains` references; a component composed in several
places (three blood pressure readings sharing one Blood Pressure cluster) is one component with several positions.
The schema carries what the JSON-LD does not: the definition and the code behind each enumerated value.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import unquote

from lxml import etree

from .package import ModelPackage

XSD_NS = "http://www.w3.org/2001/XMLSchema"
RDFS_NS = "http://www.w3.org/2000/01/rdf-schema#"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
SDC4 = "https://semanticdatacharter.com/ns/sdc4/"
NS = {"xsd": XSD_NS, "rdfs": RDFS_NS, "rdf": RDF_NS}

LEAF_TYPES = {"XdString", "XdToken", "XdBoolean", "XdLink", "XdFile", "XdOrdinal", "XdCount", "XdQuantity", "XdFloat", "XdDouble",
              "XdTemporal", "XdInterval", "XdStringList", "XdTokenList", "XdDecimalList", "XdIntegerList"}
NUMERIC_TYPES = {"XdCount", "XdQuantity", "XdFloat", "XdDouble", "XdOrdinal"}
QUANTIFIED_TYPES = {"XdCount", "XdQuantity", "XdFloat", "XdDouble"}

IDENTIFIER = "http://purl.org/dc/terms/identifier"
SOURCE = "http://purl.org/dc/terms/source"
PUBLISHER = "http://purl.org/dc/terms/publisher"
EXACT = "http://www.w3.org/2004/02/skos/core#exactMatch"
CLOSE = "http://www.w3.org/2004/02/skos/core#closeMatch"
SEE_ALSO = "http://www.w3.org/2000/01/rdf-schema#seeAlso"
HAS_UNIT = "https://semanticdatacharter.com/ontology/sdc4-meta/hasUnit"


@dataclass
class Code:
    value: str
    iri: str
    definition: str = ""
    defined_by: str = ""


@dataclass
class Component:
    ct_id: str
    sdc_type: str
    label: str
    description: str
    data_type: str
    constraints: dict
    links: dict[str, list[str]]
    contains: list[str] = field(default_factory=list)

    @property
    def iri(self) -> str:
        return f"{SDC4}mc-{self.ct_id}"

    def link(self, predicate: str) -> str | None:
        v = self.links.get(predicate)
        return v[0] if v else None


@dataclass
class Leaf:
    component: Component
    path: list[Component]          # the clusters above it, root first
    position: int                  # document order, 0-based

    @property
    def slug(self) -> str:
        return "/".join(_slug(c.label) for c in self.path[1:] + [self.component])


@dataclass
class Model:
    package: ModelPackage
    title: str
    description: str
    metadata: dict
    root: Component
    components: dict[str, Component]
    leaves: list[Leaf]
    codes: dict[str, list[Code]]   # component ct_id -> enumerated values with their definitions and codes

    @property
    def ct_id(self) -> str:
        return self.package.ct_id


def read_model(pkg: ModelPackage) -> Model:
    d = pkg.jsonld
    comps: dict[str, Component] = {}
    for n in d["components"]:
        ct = n["@id"].split("mc-", 1)[1]
        links: dict[str, list[str]] = {}
        for l in n.get("semanticLinks") or []:
            links.setdefault(l["predicate"], []).append(l["object"])
        comps[ct] = Component(ct_id=ct, sdc_type=n["@type"][:-4] if n["@type"].endswith("Type") else n["@type"], label=n["label"],
                              description=n.get("description") or "", data_type=n.get("dataType") or "", constraints=n.get("constraints") or {},
                              links=links, contains=[m["@id"].split("mc-", 1)[1] for m in n.get("contains") or []])
    root = _root(comps)
    leaves: list[Leaf] = []

    def walk(c: Component, path: list[Component]):
        for m in c.contains:
            child = comps[m]
            if child.sdc_type == "Cluster":
                walk(child, path + [child])
            elif child.sdc_type in LEAF_TYPES:
                leaves.append(Leaf(component=child, path=path + [c] if c is not path[-1] else path, position=len(leaves)))

    walk(root, [root])
    return Model(package=pkg, title=d.get("label") or d["metadata"].get("dc:title", ""), description=d.get("description") or "",
                 metadata=d.get("metadata") or {}, root=root, components=comps, leaves=leaves, codes=_codes(pkg.xsd_bytes))


def _root(comps: dict[str, Component]) -> Component:
    contained = {m for c in comps.values() for m in c.contains}
    roots = [c for c in comps.values() if c.sdc_type == "Cluster" and c.ct_id not in contained and c.contains]
    # the governed record is the cluster that contains the others; a party or audit detail cluster also sits uncontained
    roots.sort(key=lambda c: -_size(c, comps))
    if not roots:
        raise ValueError("no root cluster in the package")
    return roots[0]


def _size(c: Component, comps: dict[str, Component]) -> int:
    return 1 + sum(_size(comps[m], comps) for m in c.contains)


def _codes(xsd_bytes: bytes) -> dict[str, list[Code]]:
    """The enumerated values of every component, with the definition and the code the schema annotates them with."""
    tree = etree.fromstring(xsd_bytes)
    out: dict[str, list[Code]] = {}
    for ct in tree.iterfind(f"{{{XSD_NS}}}complexType"):
        name = ct.get("name") or ""
        if not name.startswith("mc-"):
            continue
        codes: list[Code] = []
        for enum in ct.iterfind(f".//{{{XSD_NS}}}enumeration"):
            value = enum.get("value")
            doc = enum.find(f"{{{XSD_NS}}}annotation/{{{XSD_NS}}}documentation")
            cls = enum.find(f"{{{XSD_NS}}}annotation/{{{XSD_NS}}}appinfo/{{{RDFS_NS}}}Class")
            iri = cls.get(f"{{{RDF_NS}}}about") if cls is not None else ""
            defined_by = ""
            if cls is not None:
                db = cls.find(f"{{{RDFS_NS}}}isDefinedBy")
                if db is not None:
                    defined_by = (db.get(f"{{{RDF_NS}}}resource") or (db.text or "")).strip()
            codes.append(Code(value=value, iri=iri or "", definition=" ".join((doc.text or "").split()) if doc is not None else "", defined_by=defined_by))
        if codes:
            out[name[3:]] = codes
    return out


def _slug(label: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")
    return s or "x"


def enumeration_iri(component: Component, codes: list[Code]) -> str:
    """The IRI of a component's value set: the parent of the per-value class IRIs the schema declares."""
    for c in codes:
        if c.iri:
            return c.iri.rsplit("/", 1)[0]
    return f"{component.iri}/{component.sdc_type.lower()}-value"

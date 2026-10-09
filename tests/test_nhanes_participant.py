"""The NHANES Participant document passes CDIF's own checks at the pinned commits: their frame, their JSON Schemas,
their SHACL and their conformance validator for the three profiles it declares; its codelists pass the codelist building
block's schema and rules; and it says only what the package says."""
import hashlib
import importlib.util
import json
import os
import sys
from datetime import date
from pathlib import Path

import pytest

from sdccdif import load_package, read_model, write_cdif

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "samples" / "nhanes-participant"
VALIDATION = ROOT / "data" / "cdif-129085c"         # Cross-Domain-Interoperability-Framework/validation at 129085c
CODELIST = ROOT / "data" / "mbb-61f24aa" / "cdifCodelist"   # metadataBuildingBlocks at 61f24aa
BB_SOURCES = ROOT / "data" / "mbb-61f24aa" / "_sources"     # the per-class rules the conformance detector gates on
CT = "xy8upneajsb8vdcmnve01g6g"
DAY = date(2026, 10, 8)


@pytest.fixture(scope="module")
def model():
    return read_model(load_package(PACKAGE))


@pytest.fixture(scope="module")
def doc(model):
    return write_cdif(model, today=DAY)


@pytest.fixture(scope="module")
def cv():
    """CDIF's ConformanceValidate module, imported from the pinned snapshot."""
    pytest.importorskip("pyld")
    pytest.importorskip("pyshacl")
    if BB_SOURCES.is_dir():
        os.environ["CDIF_BB_DIR"] = str(BB_SOURCES)
    sys.path.insert(0, str(VALIDATION))
    spec = importlib.util.spec_from_file_location("ConformanceValidate", VALIDATION / "ConformanceValidate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_document_passes_cdif_conformance_validation_for_every_profile_it_declares(doc, cv):
    frame = json.loads((VALIDATION / "CDIF-frame-2026.jsonld").read_text())
    resolver = cv.build_resolver("local", schema_map=str(VALIDATION / "conformance-schema-map.json"))
    result = cv.run_conformance(doc, resolver, frame=frame)
    assert [p["uri"] for p in result["profiles"]] == ["https://w3id.org/cdif/core/1.1", "https://w3id.org/cdif/discovery/1.1",
                                                      "https://w3id.org/cdif/data_description/1.1"]
    for prof in result["profiles"]:
        assert prof["schema"]["status"] in ("passed", "no_schema"), (prof["uri"], prof["schema"]["errors"][:5])
        assert prof["shacl"]["status"] == "passed", (prof["uri"], prof["shacl"]["errors"][:5])
    assert result["total_violations"] == 0
    check = result.get("conformance_check") or {}
    assert check.get("status") == "consistent", check


def test_the_framed_dataset_satisfies_the_data_description_schema(doc, cv):
    from jsonschema import Draft202012Validator
    frame = json.loads((VALIDATION / "CDIF-frame-2026.jsonld").read_text())
    framed = cv.frame_doc(doc, frame)
    for name in ("CDIFDiscoverySchema.json", "CDIFDataDescriptionSchema.json"):
        schema = json.loads((VALIDATION / name).read_text())
        errors = [e.message for e in Draft202012Validator(schema).iter_errors(framed)]
        assert not errors, (name, errors[:5])
    assert len(framed["schema:variableMeasured"]) == len(doc["@graph"][0]["schema:variableMeasured"])


def test_every_codelist_passes_the_codelist_building_block(doc):
    from jsonschema import Draft202012Validator
    pyshacl = pytest.importorskip("pyshacl")
    from rdflib import Graph
    schema = json.loads((CODELIST / "cdifCodelistSchema.json").read_text())
    ctx = json.loads((CODELIST / "context.jsonld").read_text())["@context"]
    schemes = [n for n in doc["@graph"] if "skos:ConceptScheme" in n["@type"]]
    assert len(schemes) >= 60
    for s in schemes:
        errors = [e.message for e in Draft202012Validator(schema).iter_errors({"@context": ctx, **s})]
        assert not errors, (s["@id"], errors[:3])
    g = Graph().parse(data=json.dumps(doc), format="json-ld")
    for shapes in ("rules.shacl", "conformance.shacl"):
        ok, _, text = pyshacl.validate(g, shacl_graph=Graph().parse(CODELIST / shapes, format="turtle"), inference="none")
        assert ok, (shapes, text[:2000])


def test_the_schema_is_cited_by_its_published_url_and_sha256(doc, model):
    pkg = model.package
    sha = hashlib.sha256((PACKAGE / f"dm-{CT}.xsd").read_bytes()).hexdigest()
    assert pkg.sha256 == sha == pkg.versions["current_sha256"]
    cite = doc["@graph"][0]["dcterms:conformsTo"][0]
    assert cite["@id"] == f"https://sdcstudio.axius-sdc.com/dmlib/dm-{CT}.xsd?sha256={sha}"
    assert cite["spdx:checksum"]["spdx:checksumValue"] == sha
    assert doc["@graph"][0]["schema:publishingPrinciples"]["@id"] == "https://semanticdatacharter.com/permanence.html"


def test_one_variable_per_leaf_with_a_sentinel_domain_and_a_substantive_domain(doc, model):
    ds = doc["@graph"][0]
    vs = ds["schema:variableMeasured"]
    assert len(vs) == len(model.leaves) == 153
    ids = [v["@id"] for v in vs]
    assert len(set(ids)) == len(ids)
    graph_ids = {n["@id"] for n in doc["@graph"]}
    sentinel = f"{ds['@id']}#sentinel-values"
    assert sentinel in graph_ids
    for v in vs:
        assert v["cdi:takesSentinelValuesFrom"] == [{"@id": sentinel}]
        assert "cdi:takesSubstantiveValuesFrom" in v and v["cdif:role"] in ("UnitIdentifier", "Measure", "Attribute")
        ref = v["cdi:takesSubstantiveValuesFrom"].get("cdif:takesValuesFrom", {}).get("cdif:references")
        if ref:
            assert ref["@id"] in graph_ids, ref
        if v["cdif:role"] == "Attribute":
            assert v["cdif:qualifies"]["@id"] in ids
    roles = {v["cdif:role"] for v in vs}
    assert roles == {"UnitIdentifier", "Measure", "Attribute"}
    assert [v["schema:name"] for v in vs if v["cdif:role"] == "UnitIdentifier"] == ["Respondent Sequence Number (SEQN)"]
    # the sixteen reasons a value is missing come from the reference model, once, shared by every variable
    ev = next(n for n in doc["@graph"] if n["@id"].endswith("#ExceptionalValueType"))
    assert [c["skos:notation"] for c in ev["skos:hasTopConcept"]][:3] == ["NI", "MSK", "INV"] and len(ev["skos:hasTopConcept"]) == 16


def test_enumerated_values_keep_their_definitions_and_codes(doc):
    vs = doc["@graph"][0]["schema:variableMeasured"]
    marital = next(v for v in vs if v["schema:name"] == "Marital Status (DMDMARTL)")
    scheme_id = marital["cdi:takesSubstantiveValuesFrom"]["cdif:takesValuesFrom"]["cdif:references"]["@id"]
    scheme = next(n for n in doc["@graph"] if n["@id"] == scheme_id)
    by_notation = {c["skos:notation"]: c for c in scheme["skos:hasTopConcept"]}
    assert by_notation["Married"]["skos:exactMatch"] == [{"@id": "http://purl.obolibrary.org/obo/NCIT_C51773"}]
    assert all(c["skos:inScheme"] == [{"@id": scheme_id}] for c in scheme["skos:hasTopConcept"])
    # a component composed three times (the blood pressure readings) is one codelist referenced three times
    status = [v for v in vs if v["schema:name"] == "Observation Status"]
    assert len(status) == 3 and len({v["cdi:takesSubstantiveValuesFrom"]["cdif:takesValuesFrom"]["cdif:references"]["@id"] for v in status}) == 1
    # a quantity names its unit; a quantity whose units component allows several lists them and claims no single unit
    hr = next(v for v in vs if v["schema:name"] == "Heart Rate")
    assert "cdif:simpleUnitOfMeasure" in hr or " | " in hr["schema:unitText"]
    sbp = next(v for v in vs if v["schema:name"] == "Systolic Blood Pressure")
    assert sbp["schema:unitText"] == "mmHg | kPa | atm | psi" and "cdif:simpleUnitOfMeasure" not in sbp


def test_the_writer_refuses_a_model_without_its_package(tmp_path):
    from sdccdif.package import PackageError
    (tmp_path / "dm-abc.xsd").write_bytes(b"<xsd:schema/>")
    with pytest.raises(PackageError, match="missing"):
        load_package(tmp_path)

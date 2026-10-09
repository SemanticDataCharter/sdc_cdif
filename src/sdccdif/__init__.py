"""Describe a published Semantic Data Charter model's governed data records in CDIF JSON-LD.

One model in, one JSON-LD document out: a schema:Dataset for the collection of governed data records that conform to
the model (CDIF Core and Discovery), one cdi:InstanceVariable per leaf of the record (Data Description), a
skos:ConceptScheme per enumerated leaf (Codelist), and one sentinel value domain for the reference model's exceptional
values. The schema the records conform to is cited by its published URL and SHA-256.
"""
from sdcreader import ModelPackage, load_package, fetch_package, read_model
from .cdif import write_cdif

__version__ = "4.0.0"
__all__ = ["ModelPackage", "load_package", "fetch_package", "read_model", "write_cdif", "__version__"]

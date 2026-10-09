"""sdccdif: describe a published SDC model's governed data records in CDIF JSON-LD.

    sdccdif write --package DIR [--out FILE]
    sdccdif write --ct-id ID [--save-package DIR] [--host URL] [--out FILE]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date

from .cdif import load_declared, write_cdif
from sdcreader import read_model
from sdcreader import DEFAULT_HOST, PackageError, fetch_package, load_package


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="sdccdif", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("write", help="write the CDIF JSON-LD for one model")
    src = w.add_mutually_exclusive_group(required=True)
    src.add_argument("--package", help="directory holding dm-<ct>.jsonld and dm-<ct>.xsd (and catalog.json, versions.json)")
    src.add_argument("--ct-id", help="published model identifier to fetch from the public catalog")
    w.add_argument("--save-package", help="with --ct-id: save the fetched package here")
    w.add_argument("--host", default=DEFAULT_HOST)
    w.add_argument("--out", help="output file (default stdout)")
    w.add_argument("--date", help="the catalog record's publication date, YYYY-MM-DD (default today)")
    w.add_argument("--contact-name", help="the publisher's contact point name (default: the package's declared.json)")
    w.add_argument("--contact-email", help="the publisher's contact e-mail; empty omits the contact point")
    a = p.parse_args(argv)
    try:
        pkg = load_package(a.package, host=a.host) if a.package else fetch_package(a.ct_id, save_to=a.save_package, host=a.host)
    except PackageError as e:
        print(f"sdccdif: {e}", file=sys.stderr)
        return 2
    doc = write_cdif(read_model(pkg), today=date.fromisoformat(a.date) if a.date else None, declared=load_declared(a.contact_name, a.contact_email))
    text = json.dumps(doc, indent=1, ensure_ascii=False)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"wrote {a.out}: {len(doc['@graph'][0]['schema:variableMeasured'])} variables, {len(doc['@graph']) - 3} codelists", file=sys.stderr)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

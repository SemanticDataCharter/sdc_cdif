#!/usr/bin/env python3
"""Copy the CDIF validation artifacts the writer's tests run against from the read-only clones in source/ into data/,
named by the pinned commit (cdif-library-PRD.md, section 1). Refuses a clone that is not at its pinned commit, so the
snapshot always says which CDIF it is.

    python build/snapshot_cdif.py                     # verify the pins and copy (clones under source/)
    python build/snapshot_cdif.py --source DIR        # clones elsewhere
    python build/snapshot_cdif.py --check             # verify only
"""
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PINS = {"cdifbook": "d987108", "metadataBuildingBlocks": "61f24aa", "validation": "129085c", "cdif-umlmodel": "6409827"}
VALIDATION_FILES = ["CDIF-context-2026.jsonld", "CDIF-frame-2026.jsonld", "CDIFCompleteSchema.json", "CDIFDataDescriptionSchema.json",
                    "CDIFDiscoverySchema.json", "conformance-schema-map.json", "ConformanceValidate.py", "detect_conformance.py"]
CODELIST_FILES = ["cdifCodelistSchema.json", "context.jsonld", "rules.shacl", "conformance.shacl", "description.md"]
#: The per-class rules detect_conformance.py gates a profile on; snapshotted so the tests run offline at the pin.
DETECTOR_RULES = ["cdifDataType/cdifInstanceVariable/rules.shacl", "cdifDataType/cdifDataStructureComponent/rules.shacl",
                  "cdifDataType/cdifProvActivity/rules.shacl"]


def head(repo: Path) -> str:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--short=7", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def main(check_only: bool, source: Path) -> int:
    for name, pin in PINS.items():
        repo = source / name
        if not repo.is_dir():
            print(f"{name}: not cloned (git clone --quiet https://github.com/Cross-Domain-Interoperability-Framework/{name} source/{name}; git -C source/{name} checkout {pin})")
            return 1
        at = head(repo)
        if at != pin:
            print(f"{name}: at {at}, pinned {pin}; re-pinning is a deliberate step (PRD section 1)")
            return 1
        print(f"{name}: {pin} ok")
    if check_only:
        return 0
    v = source / "validation"
    out = ROOT / "data" / f"cdif-{PINS['validation']}"
    out.mkdir(parents=True, exist_ok=True)
    for f in VALIDATION_FILES:
        shutil.copy2(v / f, out / f)
    if (out / "ShaclValidation").exists():
        shutil.rmtree(out / "ShaclValidation")
    shutil.copytree(v / "ShaclValidation", out / "ShaclValidation", ignore=shutil.ignore_patterns("__pycache__"))
    bb = source / "metadataBuildingBlocks" / "_sources"
    cl = bb / "profiles" / "cdifProfile" / "cdifCodelist"
    out2 = ROOT / "data" / f"mbb-{PINS['metadataBuildingBlocks']}" / "cdifCodelist"
    out2.mkdir(parents=True, exist_ok=True)
    for f in CODELIST_FILES:
        shutil.copy2(cl / f, out2 / f)
    for rel in DETECTOR_RULES:
        dst = ROOT / "data" / f"mbb-{PINS['metadataBuildingBlocks']}" / "_sources" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bb / rel, dst)
    print(f"snapshot: {out.relative_to(ROOT)}, {out2.relative_to(ROOT)} and the detector rules")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    src = Path(args[args.index("--source") + 1]) if "--source" in args else ROOT / "source"
    sys.exit(main("--check" in args, src))

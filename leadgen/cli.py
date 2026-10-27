import argparse
import json
import os
import platform
import shutil
import sys
import time

from . import evaluate as ev
from . import export, schema, validate
from .config import Config
from .generator import Generator


def build(cfg, out, formats=("csv", "json", "sql"), run_validate=True):
    shutil.rmtree(out, ignore_errors=True)
    t = time.time()
    tables, gt = Generator(cfg).run()
    export.write_dataset(out, tables, gt, cfg, formats)
    with open(os.path.join(out, "SOURCE_MANIFEST.md"), "w") as f:
        f.write("# Source manifest\n\nNo external or public datasets were used. All records are synthetic, generated from a fixed seed "
                f"({cfg.seed}) by this repository's code. Names, domains (`.example`, RFC 2606) and phone numbers (`555`) are fictional; "
                "no personal or confidential data was collected. Nothing was scraped; no licensing obligations apply.\n")
    summ = ev_rep = None
    if run_validate:
        summ = validate.validate(out)
        ev_rep = ev.evaluate(out)
    with open(os.path.join(out, "run_env.json"), "w") as f:
        json.dump({"python": sys.version, "platform": platform.platform(), "seconds": round(time.time() - t, 1)}, f, indent=1)
    export.write_manifest(out)
    return summ, ev_rep


def main(argv=None):
    p = argparse.ArgumentParser(prog="python -m leadgen", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("generate", help="generate + validate + evaluate a dataset")
    g.add_argument("--out", default="output/full")
    g.add_argument("--seed", type=int, default=20261022)
    g.add_argument("--scale", type=float, default=None, help="scale all volumes (0.05 = starter set)")
    g.add_argument("--leads", type=int); g.add_argument("--contacts", type=int)
    g.add_argument("--companies", type=int); g.add_argument("--opportunities", type=int)
    g.add_argument("--formats", default="csv,json,sql")
    g.add_argument("--no-validate", action="store_true")
    v = sub.add_parser("validate"); v.add_argument("--dir", required=True)
    e = sub.add_parser("evaluate"); e.add_argument("--dir", required=True)
    r = sub.add_parser("repro", help="generate twice with the same seed and compare row counts + checksums")
    r.add_argument("--scale", type=float, default=0.05); r.add_argument("--seed", type=int, default=20261022)
    r.add_argument("--out", default="output/repro")
    d = sub.add_parser("dictionary", help="write the data dictionary markdown"); d.add_argument("--out", default="docs/DATA_DICTIONARY.md")
    a = p.parse_args(argv)

    if a.cmd == "generate":
        cfg = Config.scaled(a.scale if a.scale is not None else 1.0, seed=a.seed)
        for k, v_ in (("n_leads", a.leads), ("n_contacts", a.contacts), ("n_companies", a.companies), ("n_opportunities", a.opportunities)):
            if v_:
                setattr(cfg, k, v_)
        s, e_ = build(cfg, a.out, tuple(a.formats.split(",")), not a.no_validate)
        print(f"wrote {a.out}")
        if s:
            print(f"validation: {s['overall']} ({s['invariants_passed']}/{s['invariants_total']} invariants, "
                  f"{s['detectors_matching_ground_truth']}/{s['detectors_total']} detectors match ground truth)")
            print(f"held-out AUC: {e_['auc_test_heldout']}  top-decile lift: {e_['top_decile_lift_test']}x")
            return 0 if s["overall"] == "PASS" else 1
    elif a.cmd == "validate":
        s = validate.validate(a.dir)
        print(s["overall"], f"{s['invariants_passed']}/{s['invariants_total']}")
        return 0 if s["overall"] == "PASS" else 1
    elif a.cmd == "evaluate":
        print(json.dumps(ev.evaluate(a.dir), indent=1))
    elif a.cmd == "dictionary":
        os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
        open(a.out, "w").write(schema.data_dictionary_md())
        print("wrote", a.out)
    elif a.cmd == "repro":
        cfg = Config.scaled(a.scale, seed=a.seed)
        ms = []
        for run in (1, 2):
            out = f"{a.out}_{run}"
            build(cfg, out)
            ms.append(json.load(open(os.path.join(out, "MANIFEST.json")))["files"])
        same = ms[0] == ms[1]
        print(f"{'file':45s} {'rows':>8s}  sha256 run1 == run2")
        for f_, m in ms[0].items():
            print(f"{f_:45s} {str(m['rows'] if m['rows'] is not None else '-'):>8s}  {m['sha256'][:16]}  {'OK' if m == ms[1].get(f_) else 'DIFF'}")
        print("REPRODUCIBLE" if same else "NOT REPRODUCIBLE")
        for run in (1, 2):
            shutil.rmtree(f"{a.out}_{run}", ignore_errors=True)
        return 0 if same else 1
    return 0

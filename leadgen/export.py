import csv
import hashlib
import json
import os
import sqlite3

from . import schema
from .schema import SCHEMA, TABLES

GT_FILES = {"anomalies": ["anomaly_id", "issue_type", "table", "record_id", "related_ids", "description"],
            "lead_labels": ["lead_id", "is_duplicate", "converted", "opportunity_id", "eventual_outcome", "observed_status",
                            "hidden_blocker", "initial_tier", "is_high_score_non_converter", "is_stale", "holdout_split"]}


def _cell(v, typ):
    if v is None:
        return ""
    if typ == "real":
        return f"{float(v):.2f}"
    return str(v)


def write_csv(path, cols, rows, types=None):
    types = types or {}
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(cols)
        for r in rows:
            w.writerow([_cell(r.get(c), types.get(c)) for c in cols])


def write_json(path, cols, rows):
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{c: r.get(c) for c in cols} for r in rows], f, ensure_ascii=False, separators=(",", ":"))


def write_dataset(out, tables, gt, cfg, formats=("csv", "json", "sql")):
    for d in ("csv", "json", "sql", "schema", "ground_truth"):
        os.makedirs(os.path.join(out, d), exist_ok=True)
    for t in TABLES:
        rows = tables[t.name]
        types = {c.name: c.type for c in t.cols}
        if "csv" in formats:
            write_csv(os.path.join(out, "csv", t.filename + ".csv"), t.col_names, rows, types)
        if "json" in formats:
            write_json(os.path.join(out, "json", t.filename + ".json"), t.col_names, rows)
    for name, cols in GT_FILES.items():
        write_csv(os.path.join(out, "ground_truth", name + ".csv"), cols, gt[name])
        write_json(os.path.join(out, "ground_truth", name + ".json"), cols, gt[name])
    with open(os.path.join(out, "schema", "schema.sql"), "w") as f:
        f.write(schema.ddl())
    with open(os.path.join(out, "schema", "data_dictionary.md"), "w") as f:
        f.write(schema.data_dictionary_md())
    with open(os.path.join(out, "schema", "data_dictionary.json"), "w") as f:
        json.dump([dict(table=t.name, pk=t.pk, description=t.description, lifecycle=t.lifecycle,
                        columns=[c.__dict__ for c in t.cols]) for t in TABLES], f, indent=1)
    with open(os.path.join(out, "run_metadata.json"), "w") as f:
        json.dump({"generator": "leadgen 1.0.0", "config": cfg.to_dict(),
                   "command": f"python -m leadgen generate --seed {cfg.seed} --leads {cfg.n_leads} --contacts {cfg.n_contacts} "
                              f"--companies {cfg.n_companies} --opportunities {cfg.n_opportunities}"}, f, indent=1, sort_keys=True)
    if "sql" in formats:
        build_sql(os.path.join(out, "sql", "seed.sql"), tables)


def build_sql(path, tables):
    """Load into SQLite with FK enforcement OFF during load, then assert PRAGMA foreign_key_check is empty; dump as seed.sql."""
    con = sqlite3.connect(":memory:")
    con.executescript(schema.ddl())
    for t in TABLES:
        cols = t.col_names
        con.executemany(f"INSERT INTO {t.name} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                        ([r.get(c) for c in cols] for r in tables[t.name]))
    bad = con.execute("PRAGMA foreign_key_check").fetchall()
    assert not bad, f"SQL foreign-key violations: {bad[:5]}"
    with open(path, "w", encoding="utf-8") as f:
        for line in con.iterdump():
            f.write(line + "\n")
    con.close()


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(out):
    files = {}
    for root, _, names in os.walk(out):
        for n in sorted(names):
            p = os.path.join(root, n)
            rel = os.path.relpath(p, out).replace(os.sep, "/")
            if rel in ("MANIFEST.json", "run_env.json"):
                continue
            rows = None
            if rel.endswith(".csv"):
                with open(p, encoding="utf-8") as f:
                    rows = sum(1 for _ in f) - 1
            files[rel] = {"rows": rows, "sha256": sha256(p), "bytes": os.path.getsize(p)}
    manifest = {"files": dict(sorted(files.items()))}
    with open(os.path.join(out, "MANIFEST.json"), "w") as f:
        json.dump(manifest, f, indent=1)
    return manifest

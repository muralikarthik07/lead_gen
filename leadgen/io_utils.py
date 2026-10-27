import csv
import os
from .schema import SCHEMA, TABLES


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_tables(out):
    return {t.name: read_csv(os.path.join(out, "csv", t.filename + ".csv")) for t in TABLES}

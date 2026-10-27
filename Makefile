PY ?= python3
test:        ; $(PY) -m pytest -q
starter:     ; $(PY) -m leadgen generate --scale 0.05 --out data/starter --formats csv,sql
full:        ; $(PY) -m leadgen generate --out output/full
repro:       ; $(PY) -m leadgen repro --scale 1.0 --out output/repro
ui:          ; $(PY) -m leadgen serve --open
ui-full:     ; $(PY) -m leadgen serve --dir output/full --open
audit-full:  ; LEADGEN_AUDIT_DIR=output/full $(PY) -m pytest tests/test_brief_compliance.py -q

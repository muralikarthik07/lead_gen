import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from leadgen.cli import build
from leadgen.config import Config


@pytest.fixture(scope="session")
def ds(tmp_path_factory):
    out = str(tmp_path_factory.mktemp("ds") / "d")
    cfg = Config.scaled(0.05)
    summ, ev = build(cfg, out)
    return dict(out=out, cfg=cfg, summary=summ, eval=ev)

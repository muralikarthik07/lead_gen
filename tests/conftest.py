import os, sys, threading
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


@pytest.fixture(scope="session")
def store(ds):
    from leadgen.store import Store
    return Store(ds["out"])


@pytest.fixture(scope="session")
def server(ds):
    """Real HTTP server (port 0 = free port) running in a background thread."""
    from leadgen import server as srv
    httpd = srv.serve(ds["out"], port=0, quiet=True)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()

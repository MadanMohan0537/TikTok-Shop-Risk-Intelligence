from __future__ import annotations

import duckdb
import pytest

from shop_risk.data.simulate import TEST_SCALE, simulate
from shop_risk.data.warehouse import load_frames
from shop_risk.features.pipeline import run_features
from shop_risk.rules.engine import score_rules


@pytest.fixture(scope="session")
def warehouse(tmp_path_factory):
    db = tmp_path_factory.mktemp("wh") / "shop.duckdb"
    frames = simulate(seed=7, scale=TEST_SCALE)
    con = load_frames(frames, db)
    run_features(con)
    con.close()
    return db


@pytest.fixture
def con(warehouse):
    conn = duckdb.connect(str(warehouse))
    yield conn
    conn.close()


@pytest.fixture
def hits(con):
    return score_rules(con)

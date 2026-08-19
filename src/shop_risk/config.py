from __future__ import annotations

from functools import lru_cache
from typing import Any

import yaml

from shop_risk.paths import CONFIGS


def _load(name: str) -> dict[str, Any]:
    path = CONFIGS / name
    with path.open() as fh:
        return yaml.safe_load(fh)


@lru_cache(maxsize=8)
def markets() -> dict[str, Any]:
    return _load("markets.yaml")


@lru_cache(maxsize=8)
def typologies() -> dict[str, Any]:
    return _load("fraud_typology.yaml")["typologies"]


@lru_cache(maxsize=8)
def enforcement() -> dict[str, Any]:
    return _load("enforcement.yaml")


@lru_cache(maxsize=8)
def rules_pack() -> dict[str, Any]:
    return _load("rules.yaml")


def market_ids() -> list[str]:
    return list(markets()["markets"].keys())


def market_weights() -> list[float]:
    cfg = markets()["markets"]
    return [float(cfg[m]["gmv_share"]) for m in cfg]

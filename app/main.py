from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.analytics import cases, overview, ring_candidates, simulate_policy, top_rules, trends
from app.db import init_db, rows
from app.rules import score_order

app = FastAPI(title="ShopGuard Risk Intelligence API", version="1.0.0",
              description="Independent portfolio project using synthetic marketplace data.")


class OrderPayload(BaseModel):
    amount: float = Field(ge=0)
    account_age_days: int = Field(ge=0)
    device_account_count: int = Field(ge=1)
    orders_last_hour: int = Field(ge=0)
    promo_uses_24h: int = Field(ge=0)
    home_state: str = Field(min_length=2, max_length=30)
    transaction_state: str = Field(min_length=2, max_length=30)
    distance_miles: float = Field(ge=0)
    seller_refund_rate: float = Field(ge=0, le=1)
    failed_payments: int = Field(ge=0)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "data": "synthetic"}


@app.post("/score")
def score(payload: OrderPayload) -> dict[str, Any]:
    return score_order(payload.model_dump())


@app.get("/analytics/overview")
def get_overview() -> dict: return overview()


@app.get("/analytics/trends")
def get_trends() -> list[dict]: return trends()


@app.get("/analytics/rules")
def get_rules() -> list[dict]: return top_rules()


@app.get("/cases")
def get_cases(limit: int = 100) -> list[dict]: return cases(min(limit, 500))


@app.get("/rings")
def get_rings() -> list[dict]: return ring_candidates()


@app.get("/policy/simulate")
def policy_simulation(min_score: int = 60) -> dict:
    if not 0 <= min_score <= 100:
        raise HTTPException(400, "min_score must be between 0 and 100")
    return simulate_policy(min_score)


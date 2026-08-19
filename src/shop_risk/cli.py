from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from shop_risk.data.simulate import Scale, simulate
from shop_risk.data.warehouse import load_frames, persist_parquet
from shop_risk.features.pipeline import run_features
from shop_risk.investigation.briefing import brief_case, render_prompt
from shop_risk.investigation.cases import build_cases
from shop_risk.monitoring.kpis import hits_by_typology, rule_ops_kpis
from shop_risk.paths import DEFAULT_DB, EXPORTS_DIR, RAW_DIR, ROOT, ensure_data_dirs
from shop_risk.rules.engine import persist_hits, score_rules
from shop_risk.rules.evaluate import evaluate, persist_evaluation, threshold_curve


def main(argv: list[str] | None = None) -> int:
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument("--db", default=str(DEFAULT_DB), help="DuckDB warehouse path")

    parser = argparse.ArgumentParser(
        prog="shop-risk",
        description="Marketplace risk intelligence: generate, score, investigate, evaluate.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", parents=[shared], help="Full pipeline: generate → features → score → evaluate")
    p_run.add_argument("--seed", type=int, default=42)
    p_run.add_argument("--demo", action="store_true", help="Smaller cohort for a fast local run")

    p_gen = sub.add_parser("generate", parents=[shared], help="Write synthetic parquet + load DuckDB")
    p_gen.add_argument("--seed", type=int, default=42)
    p_gen.add_argument("--demo", action="store_true")

    sub.add_parser("features", parents=[shared], help="Rebuild SQL feature marts")
    sub.add_parser("score", parents=[shared], help="Execute YAML rules")
    sub.add_parser("evaluate", parents=[shared], help="Precision / recall vs injected labels")
    sub.add_parser("policy", parents=[shared], help="Score-threshold tradeoff table")

    p_inv = sub.add_parser("investigate", parents=[shared], help="Print top case briefs")
    p_inv.add_argument("--top", type=int, default=3)
    p_inv.add_argument("--prompt", action="store_true", help="Emit the LLM prompt instead of the memo")

    sub.add_parser("dashboard", help="Launch the Streamlit analyst console")

    args = parser.parse_args(argv)
    db = Path(getattr(args, "db", DEFAULT_DB))

    if args.cmd == "generate":
        _generate(db, seed=args.seed, demo=args.demo)
    elif args.cmd == "features":
        _features(db)
    elif args.cmd == "score":
        _score(db)
    elif args.cmd == "evaluate":
        _evaluate(db)
    elif args.cmd == "policy":
        _policy(db)
    elif args.cmd == "investigate":
        _investigate(db, top=args.top, prompt=args.prompt)
    elif args.cmd == "dashboard":
        _dashboard()
    elif args.cmd == "run":
        _generate(db, seed=args.seed, demo=args.demo)
        _features(db)
        hits = _score(db)
        _evaluate(db, hits=hits)
        _policy(db, hits=hits)
        _investigate(db, top=3, prompt=False, hits=hits)
    else:
        parser.error("unknown command")
        return 2
    return 0


def _scale(demo: bool) -> Scale:
    if demo:
        from shop_risk.data.simulate import TEST_SCALE

        return TEST_SCALE
    return Scale()


def _generate(db: Path, seed: int, demo: bool) -> None:
    ensure_data_dirs()
    frames = simulate(seed=seed, scale=_scale(demo))
    persist_parquet(frames, RAW_DIR)
    con = load_frames(frames, db)
    n_orders = int(con.execute("SELECT COUNT(*) FROM orders").fetchone()[0])
    n_labels = int(con.execute("SELECT COUNT(*) FROM labels").fetchone()[0])
    con.close()
    print(f"warehouse {db}  orders={n_orders}  labels={n_labels}")


def _con(db: Path):
    import duckdb

    return duckdb.connect(str(db))


def _features(db: Path) -> None:
    con = _con(db)
    ran = run_features(con)
    con.close()
    print("features:", ", ".join(ran))


def _score(db: Path):
    con = _con(db)
    hits = score_rules(con)
    persist_hits(con, hits)
    con.close()
    print(f"rule hits: {len(hits)}")
    print(hits_by_typology(hits).to_string(index=False))
    return hits


def _evaluate(db: Path, hits=None) -> None:
    con = _con(db)
    if hits is None:
        hits = score_rules(con)
    ev = evaluate(con, hits)
    persist_evaluation(con, ev)
    con.close()
    frame = ev.to_frame()
    ensure_data_dirs()
    frame.to_csv(EXPORTS_DIR / "evaluation.csv", index=False)
    print(frame.to_string(index=False, float_format=lambda x: f"{x:0.3f}"))
    print(f"GMV on hit orders: {ev.gmv_on_hit_orders:,.2f}")


def _policy(db: Path, hits=None) -> None:
    con = _con(db)
    if hits is None:
        hits = score_rules(con)
    curve = threshold_curve(con, hits)
    con.close()
    print(curve.to_string(index=False, float_format=lambda x: f"{x:0.3f}"))


def _investigate(db: Path, top: int, prompt: bool, hits=None) -> None:
    con = _con(db)
    if hits is None:
        hits = score_rules(con)
    cases = build_cases(con, hits, limit=top)
    kpis = rule_ops_kpis(hits, evaluate(con, hits).to_frame())
    print("ops:", json.dumps(kpis, indent=2))
    print()
    for case in cases:
        print(render_prompt(case) if prompt else brief_case(case))
        print("\n" + "-" * 72 + "\n")
    if cases:
        (EXPORTS_DIR / "top_case.md").write_text(brief_case(cases[0]))
    con.close()


def _dashboard() -> None:
    import subprocess

    app = ROOT / "dashboards" / "app.py"
    raise SystemExit(subprocess.call([sys.executable, "-m", "streamlit", "run", str(app)]))


if __name__ == "__main__":
    raise SystemExit(main())

from shop_risk.cli import main
from shop_risk.monitoring.kpis import hits_by_typology, rule_ops_kpis
from shop_risk.rules.evaluate import evaluate


def test_ops_kpis(con, hits):
    ev = evaluate(con, hits)
    kpis = rule_ops_kpis(hits, ev.to_frame())
    assert kpis["hits"] == len(hits)
    assert kpis["precision"] >= 0.75
    by = hits_by_typology(hits)
    assert len(by) >= 6


def test_cli_help(capsys):
    try:
        main(["--help"])
    except SystemExit as exc:
        assert exc.code == 0
    out = capsys.readouterr().out
    assert "investigate" in out
    assert "evaluate" in out

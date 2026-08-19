from shop_risk.investigation.briefing import brief_case, render_prompt
from shop_risk.investigation.cases import build_cases
from shop_risk.investigation.prompts import CASE_BRIEF_PROMPT, RCA_PROMPT


def test_case_queue_and_brief(con, hits):
    cases = build_cases(con, hits, limit=8)
    assert cases
    top = cases[0]
    assert top.case_id.startswith("CASE-")
    assert top.action
    assert top.typology
    memo = brief_case(top)
    assert top.entity_id in memo
    assert "UX guardrail" in memo
    prompt = render_prompt(top)
    assert top.entity_id in prompt
    assert "EVIDENCE" in prompt


def test_prompt_contracts_exist():
    assert "UX_GUARDRAIL" in CASE_BRIEF_PROMPT
    assert "Detection idea" in RCA_PROMPT

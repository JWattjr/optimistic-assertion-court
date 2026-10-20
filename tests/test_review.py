"""Adversarial review: execute real captured callbacks and inspect all storage."""
import copy
import json
import sys

import pytest

from test_court import (
    ALTERNATIVE, BODY, CLAIM, QUOTE, URL, case, check, disputed, invoke,
    judged, mocks, rejected, warp,
)


def stage(case, appeal):
    c, vm, a, b, third, row = judged(case)
    if appeal:
        vm.sender = b
        mocks(vm)
        row = invoke(c, "appeal", "C-000001", 20)
        assert vm.run_validator()
    return c, vm, row["final_result" if appeal else "first_result"]


@pytest.mark.parametrize("appeal", [False, True], ids=["first", "appeal"])
@pytest.mark.parametrize("mutation", [
    "missing-verdict", "missing-cited_text", "missing-evidence_digest", "missing-available",
    "payout", "payer", "status", "int-available", "string-available", "digest-type",
    "quote-type", "oversized-quote", "undetermined-with-quote", "false-verdict",
    "empty-determinate-quote", "different-digest",
])
def test_whole_consensus_result_is_bound_in_both_callbacks(case, appeal, mutation):
    c, vm, original = stage(case, appeal)
    forged = copy.deepcopy(original)
    if mutation.startswith("missing-"):
        del forged[mutation[8:]]
    elif mutation in ("payout", "payer", "status"):
        forged[mutation] = "attacker-controlled"
    else:
        changes = {
            "int-available": ("available", 1),
            "string-available": ("available", "true"),
            "digest-type": ("evidence_digest", 7),
            "quote-type": ("cited_text", 7),
            "oversized-quote": ("cited_text", "x" * 601),
            "undetermined-with-quote": ("verdict", "UNDETERMINED"),
            "false-verdict": ("verdict", "FALSE"),
            "empty-determinate-quote": ("cited_text", ""),
            "different-digest": ("evidence_digest", "sha256:" + "0" * 64),
        }
        field, value = changes[mutation]
        forged[field] = value
    before = copy.deepcopy(c.get_claim("C-000001"))
    assert vm.run_validator(leader_result=forged) is False
    assert c.get_claim("C-000001") == before
    check(c)


@pytest.mark.parametrize("appeal", [False, True], ids=["first", "appeal"])
def test_alternative_quote_verification_receives_and_retains_exact_leader_excerpt(case, appeal, monkeypatch):
    c, vm, original = stage(case, appeal)
    mocks(vm, quote=ALTERNATIVE)
    module = sys.modules["_contract_optimistic_assertion_court"]
    original_prompt = module.gl.nondet.exec_prompt
    seen = []

    def prompt(text, **kwargs):
        seen.append(text)
        return original_prompt(text, **kwargs)

    monkeypatch.setattr(module.gl.nondet, "exec_prompt", prompt)
    assert vm.run_validator() is True
    verification = [text for text in seen if text.startswith("COURT_VERIFY_CITATION")]
    assert len(verification) == 1
    data = json.loads(verification[0].split("DATA=", 1)[1])
    assert data == {"claim": CLAIM, "evidence": BODY.decode(), "verdict": "TRUE", "excerpt": QUOTE}
    assert c.get_claim("C-000001")["final_result" if appeal else "first_result"] == original


@pytest.mark.parametrize("appeal", [False, True], ids=["first", "appeal"])
@pytest.mark.parametrize("failure", ["unsupported", "malformed", "model-error", "false-string"])
def test_citation_confirmation_failure_always_disagrees(case, appeal, failure, monkeypatch):
    c, vm, original = stage(case, appeal)
    module = sys.modules["_contract_optimistic_assertion_court"]
    prompt = module.gl.nondet.exec_prompt

    def failing_verify(text, **kwargs):
        if text.startswith("COURT_VERIFY_CITATION"):
            if failure == "model-error":
                raise module.gl.nondet.NondetException("verification failed")
            return {"supports": False} if failure == "unsupported" else (
                {"supports": "false"} if failure == "false-string" else {"supports": True, "payout": 1000})
        return prompt(text, **kwargs)

    monkeypatch.setattr(module.gl.nondet, "exec_prompt", failing_verify)
    assert vm.run_validator(leader_result=original) is False


@pytest.mark.parametrize("appeal", [False, True], ids=["first", "appeal"])
def test_consensus_disagreement_prevents_all_transaction_storage_writes(case, appeal, monkeypatch):
    if appeal:
        c, vm, a, b, third, row = judged(case)
        vm.sender = b
    else:
        c, vm, a, b, third = disputed(case)
    mocks(vm)
    module = sys.modules["_contract_optimistic_assertion_court"]
    run = module.gl.vm.run_nondet_unsafe
    calls = []

    def disagree(leader_fn, validator_fn):
        honest = run(leader_fn, validator_fn)
        forged = {**honest, "evidence_digest": "sha256:" + "0" * 64}
        # Execute the actual validator callback captured by the direct VM;
        # emulate the protocol refusing to return a rejected leader result.
        calls.append(vm.run_validator(leader_result=forged))
        assert calls[-1] is False
        raise module.gl.vm.UserError("[EXPECTED] simulated consensus disagreement")

    monkeypatch.setattr(module.gl.vm, "run_nondet_unsafe", disagree)
    rejected(vm, c, "appeal" if appeal else "adjudicate", "C-000001", *([20] if appeal else []),
             message="simulated consensus disagreement")
    assert calls == [False]


def test_cross_claim_replay_is_checked_against_new_frozen_claim(case):
    c, vm, a, b, third = case
    for text in (CLAIM, "The approved bridge length is two hundred metres."):
        vm.sender = a
        row = invoke(c, "assert_claim", text, URL, 10)
        vm.sender = b
        invoke(c, "challenge", row["claim_id"], 10)
    warp(vm, 60)
    mocks(vm, "TRUE")
    first = invoke(c, "adjudicate", "C-000001")["first_result"]
    assert vm.run_validator()
    mocks(vm, "FALSE")
    second = invoke(c, "adjudicate", "C-000002")["first_result"]
    assert vm.run_validator(leader_result=first) is False
    assert vm.run_validator(leader_result=second) is True
    assert c.get_claim("C-000001")["verdict"] == "TRUE"
    assert c.get_claim("C-000002")["verdict"] == "FALSE"


def test_first_stage_short_quote_cannot_replay_under_appeal_rubric(case):
    c, vm, a, b, third = disputed(case)
    mocks(vm, quote="one hundred metres.")
    first = invoke(c, "adjudicate", "C-000001")["first_result"]
    assert vm.run_validator()
    vm.sender = b
    mocks(vm)
    invoke(c, "appeal", "C-000001", 20)
    assert vm.run_validator(leader_result=first) is False


@pytest.mark.parametrize("appeal", [False, True], ids=["first", "appeal"])
def test_old_result_cannot_replay_after_evidence_bytes_change(case, appeal):
    c, vm, original = stage(case, appeal)
    mocks(vm, body=BODY + b"\nAdditional context.")
    assert vm.run_validator(leader_result=original) is False


def test_wrong_caller_cannot_withdraw_another_accounts_available_units(case):
    c, vm, a, b, third = case
    vm.sender = third
    rejected(vm, c, "withdraw_units", 1, message="insufficient available balance")
    assert c.get_balance(a) == c.get_balance(b) == 100


@pytest.mark.parametrize("extra", ["payout", "payer", "status", "recipient"])
def test_llm_cannot_supply_settlement_fields(case, extra):
    c, vm, a, b, third = disputed(case)
    mocks(vm)
    vm._llm_mocks.clear()
    from test_court import llm
    vm.mock_llm(r"COURT_JUDGE", llm({"verdict": "TRUE", "cited_text": QUOTE, extra: "attacker"}))
    rejected(vm, c, "adjudicate", "C-000001", message="invalid JSON schema")

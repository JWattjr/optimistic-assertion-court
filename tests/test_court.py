"""Direct-mode storage/ledger tests plus explicitly invoked validator callbacks."""
import copy
import hashlib
import json
from datetime import datetime, timedelta

import pytest

URL = "https://raw.githubusercontent.com/JWattjr/genlayer-demo-evidence/0123456789abcdef0123456789abcdef01234567/court.txt"
CLAIM = "The approved bridge length is one hundred metres."
QUOTE = "The approved bridge length is one hundred metres."
ALTERNATIVE = "The approved span measures exactly one hundred metres."
IRRELEVANT = "The bridge paint colour is blue and the rails are steel."
BODY = (QUOTE + "\n" + ALTERNATIVE + "\n" + IRRELEVANT).encode()
START = "2030-01-01T00:00:00Z"


def llm(value):
    # The legacy SDK expects JSON text after the direct mock decodes its envelope.
    return json.dumps(json.dumps(value))


def key(account):
    return "0x" + account.hex() if isinstance(account, bytes) else str(account).lower()


def warp(vm, seconds):
    vm.warp((datetime.fromisoformat(START.replace("Z", "+00:00")) + timedelta(seconds=seconds)).isoformat())


def check(court):
    account = court.get_accounting()
    assert account["conserved"]
    assert account["total_deposited"] == account["available_total"] + account["locked_total"] + account["paid_out"]
    assert all(value >= 0 for value in account.values())
    return account


def invoke(court, method, *args):
    result = getattr(court, method)(*args)
    check(court)
    return result


def rejected(vm, court, method, *args, message=None):
    before = (check(court), court.get_history())
    with vm.expect_revert(message):
        getattr(court, method)(*args)
    assert (check(court), court.get_history()) == before


@pytest.fixture
def case(direct_vm, direct_deploy, direct_alice, direct_bob, direct_charlie):
    direct_vm.sender = direct_alice
    direct_vm.warp(START)
    court = direct_deploy("contracts/optimistic_assertion_court.py", "Court tests", 60, 60, 300, sdk_version="v0.6.0-rc5")
    check(court)
    for actor in (direct_alice, direct_bob):
        with direct_vm.prank(actor):
            invoke(court, "deposit_units", 100)
    direct_vm.sender = direct_alice
    return court, direct_vm, direct_alice, direct_bob, direct_charlie


def mocks(vm, verdict="TRUE", quote=QUOTE, body=BODY, status=200, supports=True, headers=None):
    vm.clear_mocks()
    vm.mock_web(r".*", {"response": {"status": status, "body": body, "headers": headers or {}}, "method": "GET"})
    vm.mock_llm(r"COURT_JUDGE", llm({"verdict": verdict, "cited_text": "" if verdict == "UNDETERMINED" else quote}))
    vm.mock_llm(r"COURT_VERIFY_CITATION", llm({"supports": supports}))


def disputed(case, bond=10):
    c, vm, a, b, third = case
    vm.sender = a
    invoke(c, "assert_claim", CLAIM, URL, bond)
    vm.sender = b
    invoke(c, "challenge", "C-000001", bond)
    warp(vm, 60)
    vm.sender = third
    return c, vm, a, b, third


def judged(case, verdict="TRUE", bond=10):
    c, vm, a, b, third = disputed(case, bond)
    mocks(vm, verdict)
    row = invoke(c, "adjudicate", "C-000001")
    assert vm.run_validator()
    return c, vm, a, b, third, row


def forbid_external(monkeypatch):
    import sys
    module = sys.modules["_contract_optimistic_assertion_court"]
    def forbidden(*args, **kwargs):
        raise AssertionError("deterministic path invoked web/LLM")
    monkeypatch.setattr(module.gl.nondet.web, "get", forbidden)
    monkeypatch.setattr(module.gl.nondet, "exec_prompt", forbidden)


def test_unchallenged_zero_web_llm_or_consensus(case, monkeypatch):
    c, vm, a, b, third = case
    mocks(vm)
    forbid_external(monkeypatch)
    invoke(c, "assert_claim", CLAIM, URL, 10)
    rejected(vm, c, "finalize", "C-000001", message="challenge window has not closed")
    warp(vm, 60)
    vm.sender = third
    row = invoke(c, "finalize", "C-000001")
    assert row["status"] == "ACCEPTED" and row["settlement_count"] == 1 and row["settled_units"] == 10
    assert c.get_balance(a) == 100
    assert not vm._web_mocks_hit and not vm._llm_mocks_hit and not vm._captured_validators


@pytest.mark.parametrize("verdict,winner_index", [("TRUE", 0), ("FALSE", 1), ("UNDETERMINED", None)])
def test_first_judgment_settlement(case, verdict, winner_index):
    c, vm, a, b, third, row = judged(case, verdict)
    if winner_index is None:
        assert row["status"] == "VOID"
        assert c.get_balance(a) == c.get_balance(b) == 100
        rejected(vm, c, "appeal", "C-000001", 20, message="terminal")
    else:
        assert row["status"] == "PROVISIONAL" and row["escrow_units"] == 20
        assert c.get_balance(a) == c.get_balance(b) == 90
        rejected(vm, c, "finalize", "C-000001", message="appeal window has not closed")
        warp(vm, 120)
        row = invoke(c, "finalize", "C-000001")
        winner = (a, b)[winner_index]
        assert row["status"] == "FINAL" and c.get_balance(winner) == 110
        assert row["settlement_count"] == 1 and row["settled_units"] == 20


@pytest.mark.parametrize("offset", [60, 61])
def test_late_challenge_exact_boundary(case, offset):
    c, vm, a, b, third = case
    invoke(c, "assert_claim", CLAIM, URL, 10)
    vm.sender = b
    warp(vm, offset)
    rejected(vm, c, "challenge", "C-000001", 10, message="challenge window has closed")


@pytest.mark.parametrize("bond", [0, 9, 11, True, -1, 10**12 + 1])
def test_wrong_challenge_bond(case, bond):
    c, vm, a, b, third = case
    invoke(c, "assert_claim", CLAIM, URL, 10)
    vm.sender = b
    rejected(vm, c, "challenge", "C-000001", bond)


def test_challenge_guards_and_first_judgment_once(case):
    c, vm, a, b, third = case
    invoke(c, "assert_claim", CLAIM, URL, 10)
    rejected(vm, c, "challenge", "C-000001", 10, message="own claim")
    rejected(vm, c, "adjudicate", "C-000001")
    vm.sender = b
    invoke(c, "challenge", "C-000001", 10)
    rejected(vm, c, "challenge", "C-000001", 10)
    rejected(vm, c, "adjudicate", "C-000001", message="challenge window has not closed")
    warp(vm, 60)
    mocks(vm)
    invoke(c, "adjudicate", "C-000001")
    rejected(vm, c, "adjudicate", "C-000001")


@pytest.mark.parametrize("first,final", [("TRUE", "TRUE"), ("TRUE", "FALSE"), ("FALSE", "TRUE"), ("FALSE", "FALSE"), ("TRUE", "UNDETERMINED"), ("FALSE", "UNDETERMINED")])
def test_appeal_once_uphold_flip_or_refund(case, first, final):
    c, vm, a, b, third, row = judged(case, first)
    appellant = b if first == "TRUE" else a
    vm.sender = appellant
    mocks(vm, final)
    row = invoke(c, "appeal", "C-000001", 20)
    assert vm.run_validator()
    assert row["appeal_used"] and row["settlement_count"] == 1 and row["settled_units"] == 40
    assert row["first_result"]["verdict"] == first and row["final_result"]["verdict"] == final
    if final == "UNDETERMINED":
        assert row["status"] == "VOID" and c.get_balance(a) == c.get_balance(b) == 100
    else:
        winner = a if final == "TRUE" else b
        loser = b if final == "TRUE" else a
        assert row["status"] == "FINAL"
        assert c.get_balance(winner) == (110 if key(winner) == key(appellant) else 130)
        assert c.get_balance(loser) == (70 if key(loser) == key(appellant) else 90)
    rejected(vm, c, "appeal", "C-000001", 20, message="terminal")


@pytest.mark.parametrize("bond", [0, 10, 19, 21, True, 2 * 10**12 + 1])
def test_wrong_appeal_bond(case, bond):
    c, vm, a, b, third, row = judged(case)
    vm.sender = b
    rejected(vm, c, "appeal", "C-000001", bond)


def test_appeal_actor_and_deadline_guards(case):
    c, vm, a, b, third, row = judged(case)
    for actor in (a, third):
        vm.sender = actor
        rejected(vm, c, "appeal", "C-000001", 20, message="only the provisional loser")
    vm.sender = b
    warp(vm, 120)
    rejected(vm, c, "appeal", "C-000001", 20, message="appeal window has closed")


def test_failed_appeal_leaves_original_bonds_and_appeal_unused(case):
    c, vm, a, b, third, original = judged(case)
    vm.sender = b
    mocks(vm, "TRUE", "short")
    rejected(vm, c, "appeal", "C-000001", 20, message="invalid citation")
    assert c.get_claim("C-000001") == original
    mocks(vm)
    assert invoke(c, "appeal", "C-000001", 20)["status"] == "FINAL"


@pytest.mark.parametrize("provisional", [False, True])
@pytest.mark.parametrize("stale_time", [300, 301])
def test_void_stale_before_at_and_after_deadline_no_consensus(case, provisional, stale_time, monkeypatch):
    if provisional:
        c, vm, a, b, third, row = judged(case)
    else:
        c, vm, a, b, third = disputed(case)
    vm.sender = third
    forbid_external(monkeypatch)
    warp(vm, 299)
    rejected(vm, c, "void_stale", "C-000001", message="dispute deadline has not been reached")
    web_hits = set(vm._web_mocks_hit)
    llm_hits = set(vm._llm_mocks_hit)
    count = len(vm._captured_validators)
    warp(vm, stale_time)
    rejected(vm, c, "adjudicate" if not provisional else "finalize", "C-000001")
    row = invoke(c, "void_stale", "C-000001")
    assert row["status"] == "VOID" and row["void_reason"] == "STALE_DISPUTE"
    assert row["verdict"] == "" and row["final_result"] == {}
    assert c.get_balance(a) == c.get_balance(b) == 100
    assert vm._web_mocks_hit == web_hits and vm._llm_mocks_hit == llm_hits and len(vm._captured_validators) == count
    rejected(vm, c, "void_stale", "C-000001", message="terminal")


def test_void_stale_open_or_already_settled_rejected(case):
    c, vm, a, b, third = case
    invoke(c, "assert_claim", CLAIM, URL, 10)
    warp(vm, 300)
    rejected(vm, c, "void_stale", "C-000001")
    invoke(c, "finalize", "C-000001")
    rejected(vm, c, "void_stale", "C-000001", message="terminal")


def test_valid_alternative_citation_is_verified_and_leader_quote_retained(case):
    c, vm, a, b, third, row = judged(case)
    mocks(vm, quote=ALTERNATIVE)
    assert vm.run_validator()  # Validator chooses a different quote; verifies original leader's quote.
    assert c.get_claim("C-000001")["first_result"]["cited_text"] == QUOTE
    leader = copy.deepcopy(row["first_result"])
    leader["cited_text"] = ALTERNATIVE
    assert vm.run_validator(leader_result=leader)


@pytest.mark.parametrize("kind", ["digest", "verdict", "availability", "non-substring", "empty", "non-supporting", "extra-key", "bool-verdict", "string-supports"])
def test_forged_or_unsupported_leader_rejected(case, kind):
    c, vm, a, b, third, row = judged(case)
    leader = copy.deepcopy(row["first_result"])
    if kind == "digest":
        leader["evidence_digest"] = "sha256:" + "0" * 64
    elif kind == "verdict":
        leader["verdict"] = "FALSE"
    elif kind == "availability":
        leader = {"verdict": "UNDETERMINED", "available": False, "evidence_digest": "", "cited_text": ""}
    elif kind == "non-substring":
        leader["cited_text"] = "This invented excerpt is absent from the document."
    elif kind == "empty":
        leader["cited_text"] = ""
    elif kind == "non-supporting":
        leader["cited_text"] = IRRELEVANT
        mocks(vm, supports=False)
    elif kind == "extra-key":
        leader["payout"] = 999
    elif kind == "bool-verdict":
        leader["verdict"] = True
    else:
        mocks(vm, supports="true")
    assert not vm.run_validator(leader_result=leader)
    assert not vm.run_validator(leader_error="failed leader")


def test_too_short_appeal_citation_rejected_by_validator(case):
    c, vm, a, b, third, row = judged(case)
    vm.sender = b
    mocks(vm)
    row = invoke(c, "appeal", "C-000001", 20)
    leader = copy.deepcopy(row["final_result"])
    leader["cited_text"] = "The approved"
    assert not vm.run_validator(leader_result=leader)


@pytest.mark.parametrize("body,status,headers", [(BODY, 404, {}), (b"", 200, {}), (b" \n", 200, {}), (b"x" * 15001, 200, {}), (b"\xff", 200, {}), (BODY, 302, {}), (BODY, 200, {"content-length": b"1"}), (BODY, 200, {"content-encoding": b"gzip"})])
def test_unavailable_evidence_void_and_refund_without_llm(case, body, status, headers):
    c, vm, a, b, third = disputed(case)
    mocks(vm, body=body, status=status, headers=headers)
    row = invoke(c, "adjudicate", "C-000001")
    assert row["status"] == "VOID" and row["first_result"] == {"available": False, "cited_text": "", "evidence_digest": "", "verdict": "UNDETERMINED"}
    assert vm.run_validator()
    assert c.get_balance(a) == c.get_balance(b) == 100
    assert not vm._llm_mocks_hit


def test_exactly_15000_raw_bytes_and_digest(case):
    c, vm, a, b, third = disputed(case)
    body = BODY + b" " * (15000 - len(BODY))
    mocks(vm, body=body)
    row = invoke(c, "adjudicate", "C-000001")
    assert row["first_result"]["available"]
    assert row["first_result"]["evidence_digest"] == "sha256:" + hashlib.sha256(body).hexdigest()
    assert vm.run_validator()


def test_unavailable_appeal_refunds_all_three_bonds(case):
    c, vm, a, b, third, row = judged(case)
    vm.sender = b
    mocks(vm, body=b"\xff")
    row = invoke(c, "appeal", "C-000001", 20)
    assert row["status"] == "VOID" and row["settled_units"] == 40
    assert c.get_balance(a) == c.get_balance(b) == 100
    assert vm.run_validator()


def test_withdrawal_only_available_no_double_withdrawal_and_terminal_actions(case):
    c, vm, a, b, third = case
    invoke(c, "assert_claim", CLAIM, URL, 10)
    rejected(vm, c, "withdraw_units", 100, message="insufficient available balance")
    invoke(c, "withdraw_units", 90)
    rejected(vm, c, "withdraw_units", 90, message="insufficient available balance")
    warp(vm, 60)
    invoke(c, "finalize", "C-000001")
    invoke(c, "withdraw_units", 10)
    for method, args in [("challenge", [10]), ("adjudicate", []), ("appeal", [20]), ("finalize", []), ("void_stale", [])]:
        rejected(vm, c, method, "C-000001", *args, message="terminal")


@pytest.mark.parametrize("text,url,bond", [("short", URL, 10), ("x" * 801, URL, 10), (" " * 801 + CLAIM, URL, 10), (CLAIM, "http://example.org/x", 10), (CLAIM, "https://localhost/x", 10), (CLAIM, "https://127.0.0.1/x", 10), (CLAIM, "https://user@example.org/x", 10), (CLAIM, "https://example.org/x#fragment", 10), (CLAIM, "https://example.org:444/x", 10), (CLAIM, "https://example.org/" + "x" * 501, 10), (CLAIM, URL, 0), (CLAIM, URL, True), (CLAIM, URL, 101)])
def test_claim_input_bounds_and_balance(case, text, url, bond):
    c, vm, a, b, third = case
    rejected(vm, c, "assert_claim", text, url, bond)
    assert c.get_config()["claim_count"] == 0


@pytest.mark.parametrize("windows", [(59, 60, 300), (60, 59, 300), (60, 60, 179), (True, 60, 300), (60, 60, 7776001), (2592001, 60, 7776000)])
def test_constructor_window_bounds(direct_vm, direct_deploy, windows):
    direct_vm.warp(START)
    with direct_vm.expect_revert():
        direct_deploy("contracts/optimistic_assertion_court.py", "Court", *windows, sdk_version="v0.6.0-rc5")


def test_claim_count_limit_and_history(case):
    c, vm, a, b, third = case
    for _ in range(32):
        invoke(c, "assert_claim", CLAIM, URL, 1)
    rejected(vm, c, "assert_claim", CLAIM, URL, 1, message="claim limit")
    warp(vm, 60)
    for i in range(1, 33):
        invoke(c, "finalize", f"C-{i:06d}")
    history = c.get_history()
    assert len(history) == 64 <= 256
    assert [row["seq"] for row in history] == list(range(1, 65))


def test_maximum_original_bond_allows_twice_bond_appeal(case):
    c, vm, a, b, third = case
    for actor in (a, b):
        vm.sender = actor
        for _ in range(3):
            invoke(c, "deposit_units", 10**12)
    c, vm, a, b, third, row = judged(case, bond=10**12)
    vm.sender = b
    mocks(vm, "FALSE")
    row = invoke(c, "appeal", "C-000001", 2 * 10**12)
    assert row["settled_units"] == 4 * 10**12 and row["final_winner"] == key(b)
    assert vm.run_validator()


@pytest.mark.parametrize("amount", [0, -1, True, 10**12 + 1])
def test_deposit_bounds(case, amount):
    c, vm, a, b, third = case
    rejected(vm, c, "deposit_units", amount)


def test_unknown_id_and_unfunded_address(case):
    c, vm, a, b, third = case
    rejected(vm, c, "finalize", "C-999999", message="unknown claim")
    assert c.get_balance(third) == 0
    vm.sender = third
    rejected(vm, c, "assert_claim", CLAIM, URL, 1, message="insufficient available balance")


def test_lifetime_account_bound_preserves_existing_accounts(case):
    c, vm, a, b, third = case
    for i in range(126):
        vm.sender = (i + 1).to_bytes(20, "big")
        invoke(c, "deposit_units", 1)
    vm.sender = third
    rejected(vm, c, "deposit_units", 1, message="account limit")
    assert c.get_balance(third) == 0
    vm.sender = a
    invoke(c, "deposit_units", 1)
    invoke(c, "withdraw_units", 1)


def test_cumulative_deposit_cap_rejects_before_registering_account(case, monkeypatch):
    import sys
    c, vm, a, b, third = case
    # Scale only this test's global cap instead of issuing a million deposits.
    module = sys.modules["_contract_optimistic_assertion_court"]
    monkeypatch.setattr(module, "MAX_LEDGER", 201)
    vm.sender = third
    rejected(vm, c, "deposit_units", 2, message="cumulative deposit limit")
    invoke(c, "deposit_units", 1)
    rejected(vm, c, "deposit_units", 1, message="cumulative deposit limit")


@pytest.mark.parametrize("response", ['not json', '{"verdict":"TRUE","verdict":"FALSE","cited_text":""}', '{"verdict":"MAYBE","cited_text":""}', '{"verdict":"TRUE","cited_text":7}', '"' + 'x' * 4097 + '"'])
def test_malformed_model_result_cannot_settle(case, response):
    c, vm, a, b, third = disputed(case)
    mocks(vm)
    vm._llm_mocks.clear()
    vm.mock_llm(r"COURT_JUDGE", json.dumps(response))
    before = c.get_claim("C-000001")
    rejected(vm, c, "adjudicate", "C-000001")
    assert c.get_claim("C-000001") == before


def test_unavailable_disagreement_cannot_accept_leader(case):
    c, vm, a, b, third, row = judged(case)
    mocks(vm, status=503)
    assert not vm.run_validator(leader_result=row["first_result"])


def test_transport_failure_is_unavailable_but_programming_error_is_not(case, monkeypatch):
    import sys
    c, vm, a, b, third = disputed(case)
    module = sys.modules["_contract_optimistic_assertion_court"]
    def transport(*args, **kwargs):
        raise module.gl.nondet.NondetException("transport unavailable")
    monkeypatch.setattr(module.gl.nondet.web, "get", transport)
    row = invoke(c, "adjudicate", "C-000001")
    assert row["status"] == "VOID" and not row["first_result"]["available"]
    assert vm.run_validator()


def test_fetch_programming_error_does_not_void_dispute(case, monkeypatch):
    import sys
    c, vm, a, b, third = disputed(case)
    module = sys.modules["_contract_optimistic_assertion_court"]
    before = c.get_claim("C-000001")
    def broken(*args, **kwargs):
        raise TypeError("implementation error")
    monkeypatch.setattr(module.gl.nondet.web, "get", broken)
    with pytest.raises(TypeError, match="implementation error"):
        c.adjudicate("C-000001")
    assert c.get_claim("C-000001") == before
    check(c)


def test_appeal_minimum_four_tokens_is_enforced(case):
    c, vm, a, b, third, row = judged(case)
    vm.sender = b
    body = b"A verylongsinglecompoundwordthatexceedstwentyfourcharacters"
    mocks(vm, quote=body.decode(), body=body)
    rejected(vm, c, "appeal", "C-000001", 20, message="invalid citation")


def test_late_first_judgment_does_not_extend_stale_deadline(case):
    c, vm, a, b, third = disputed(case)
    warp(vm, 290)
    mocks(vm)
    row = invoke(c, "adjudicate", "C-000001")
    assert row["appeal_deadline"] == row["stale_deadline"]
    warp(vm, 300)
    vm.sender = b
    rejected(vm, c, "appeal", "C-000001", 20, message="dispute deadline reached")
    invoke(c, "void_stale", "C-000001")


@pytest.mark.parametrize("url", ["https://8.8.8.8/doc", "https://example.org:443/data?a=1"])
def test_valid_public_url_shapes(case, url):
    c, vm, a, b, third = case
    assert invoke(c, "assert_claim", CLAIM, url, 1)["evidence_url"] == url


@pytest.mark.parametrize("host", ["10.0.0.1", "169.254.1.1", "100.64.0.1", "192.0.2.1", "224.0.0.1", "240.0.0.1", "999.1.1.1", "example.local", "bad..example.org", "-bad.example.org", "[::1]"])
def test_invalid_public_url_hosts(case, host):
    c, vm, a, b, third = case
    rejected(vm, c, "assert_claim", CLAIM, "https://" + host + "/x", 1)


@pytest.mark.parametrize("path", ["x y", "x\\y", "x\ny", "\x7f", "é"])
def test_invalid_url_characters(case, path):
    c, vm, a, b, third = case
    rejected(vm, c, "assert_claim", CLAIM, "https://example.org/" + path, 1)


@pytest.mark.parametrize("terminal", ["FINAL", "VOID"])
def test_all_claim_actions_rejected_after_other_terminal_states(case, terminal):
    c, vm, a, b, third, row = judged(case, "UNDETERMINED" if terminal == "VOID" else "TRUE")
    if terminal == "FINAL":
        warp(vm, 120)
        invoke(c, "finalize", "C-000001")
    for method, args in [("challenge", [10]), ("adjudicate", []), ("appeal", [20]), ("finalize", []), ("void_stale", [])]:
        rejected(vm, c, method, "C-000001", *args, message="terminal")


def test_title_and_config_are_bounded_and_frozen(case, direct_deploy):
    c, vm, a, b, third = case
    config = c.get_config()
    assert config["max_claims"] == 32 and config["max_accounts"] == 128
    assert config["challenge_window_seconds"] == 60 and config["appeal_window_seconds"] == 60
    assert config["dispute_deadline_seconds"] == 300
    invoke(c, "assert_claim", CLAIM, URL, 10)
    assert {k: v for k, v in c.get_config().items() if k != "claim_count"} == {k: v for k, v in config.items() if k != "claim_count"}
    for title in ("", "x" * 121):
        with vm.expect_revert():
            direct_deploy("contracts/optimistic_assertion_court.py", title, 60, 60, 300, sdk_version="v0.6.0-rc5")

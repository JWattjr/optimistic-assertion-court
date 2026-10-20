"""Append one live appeal to the existing deployment; never redeploy or retry a write."""
import base64
import copy
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from eth_account import Account
from genlayer_py import create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionHashVariant

import studionet_release as run

ADDRESS = "0xC59715a21e2cac8e8978F4D3098087930399fCF2"
SOURCE_COMMIT = "3b0ce9c68628538431942bc6d8db00773ab716cf"
EVIDENCE_COMMIT = "24cf4f229fc811b65df86f0c9593dccde2cd35a9"
FILENAME = "appeal-raven-bridge.txt"
URL = f"https://raw.githubusercontent.com/JWattjr/genlayer-demo-evidence/{EVIDENCE_COMMIT}/optimistic-assertion-court/{FILENAME}"
SENTENCE = "The certified length of the fictional Raven Bridge is exactly 100 metres."
CLAIM = "The certified length of the fictional Raven Bridge is exactly 200 metres."
BOND = 10
prior = None
claim_id = None
fixture = None
BASE_TX_COUNT = 0
BASE_READ_COUNT = 0


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()


def originals_unchanged():
    assert run.record["transactions"][:BASE_TX_COUNT] == prior["transactions"]
    assert run.record["readbacks"][:BASE_READ_COUNT] == prior["readbacks"]
    assert all(run.record["receipts"][key] == value for key, value in prior["receipts"].items())
    assert run.record["final_history"] == prior["final_history"]


def append_save():
    originals_unchanged()
    run.save()


def connect():
    run.record = json.loads(run.OUTPUT.read_text(encoding="utf-8"))
    run.address = ADDRESS
    credential = subprocess.run(["node", r"C:\Users\User\Desktop\Intelligent Contracts\release\credential_key.mjs",
                                 "moment-grid-studionet"], capture_output=True, text=True)
    if credential.returncode:
        raise RuntimeError("Credential helper failed; key output suppressed")
    asserter = Account.from_key(credential.stdout.strip())
    challenger = Account.from_key(hashlib.sha256(bytes(asserter.key) + b"optimistic-court/challenger/2026-10-20").digest())
    relayer = Account.from_key(hashlib.sha256(bytes(asserter.key) + b"optimistic-court/relayer/2026-10-20").digest())
    del credential
    run.clients = {name: create_client(chain=studionet, account=account) for name, account in
                   {"asserter": asserter, "challenger": challenger, "relayer": relayer}.items()}
    assert {name: client.local_account.address for name, client in run.clients.items()} == run.record["participants"]


def view(method, args, *, final=False):
    return run.clients["asserter"].read_contract(address=ADDRESS, function_name=method, args=args,
        transaction_hash_variant=TransactionHashVariant.LATEST_FINAL if final else TransactionHashVariant.LATEST_NONFINAL)


def source_check():
    expected = run.git("show", SOURCE_COMMIT + ":" + run.SOURCE)
    assert expected == (run.ROOT / run.SOURCE).read_bytes()
    deployed = base64.b64decode(run.rpc("gen_getContractCode", [ADDRESS]))
    assert expected == deployed
    assert hashlib.sha256(expected).hexdigest() == run.record["source_sha256"]
    assert int(run.rpc("eth_chainId", []), 16) == 61999
    visibility = json.loads(run.command(["gh", "repo", "view", "JWattjr/optimistic-assertion-court", "--json", "visibility"]))
    assert visibility["visibility"] == "PRIVATE"
    return {"source_commit": SOURCE_COMMIT, "source_blob": run.record["source_blob"],
            "bytes": len(expected), "sha256": hashlib.sha256(expected).hexdigest(), "deployed_match": True}


def measure_fixture():
    folder = run.ROOT / "artifacts"
    folder.mkdir(exist_ok=True)
    dest = folder / FILENAME
    result = subprocess.run(["curl.exe", "--fail", "--silent", "--show-error", "--proto", "=https",
        "--max-redirs", "0", "--connect-timeout", "15", "--max-time", "60", "-H", "Accept-Encoding: identity",
        "-D", str(folder / "appeal-fixture-headers.txt"), "-o", str(dest), "-w",
        "%{http_code} %{size_download} %{url_effective}", URL], capture_output=True, text=True, check=True)
    raw = dest.read_bytes()
    fields = result.stdout.split()
    assert fields[0] == "200" and int(fields[1]) == len(raw) and fields[2] == URL
    assert 0 < len(raw) <= 15000
    assert SENTENCE in raw.decode("utf-8") and len(SENTENCE) >= 24 and len(SENTENCE.split()) >= 4
    report = {"repository": "https://github.com/JWattjr/genlayer-demo-evidence", "visibility": "PUBLIC",
              "commit": EVIDENCE_COMMIT, "file": "optimistic-assertion-court/" + FILENAME,
              "url": URL, "raw_bytes": len(raw), "curl_size_download": int(fields[1]),
              "curl_http_status": 200, "sha256": hashlib.sha256(raw).hexdigest(),
              "curl_output": result.stdout, "claim_level_sentence": SENTENCE,
              "sentence_characters": len(SENTENCE), "sentence_words": len(SENTENCE.split())}
    (run.ROOT / "docs/APPEAL_EVIDENCE.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n")
    return report


def snapshot(label, tx_hash, *, final=False, full=False):
    # Two reads on the deadline-critical path. Full actor/old-claim audits are
    # done before the new claim and after the appeal has been submitted.
    row = view("get_claim", [claim_id], final=final) if claim_id else None
    ledger = view("get_accounting", [], final=final)
    assert ledger["conserved"] and ledger["total_deposited"] == ledger["available_total"] + ledger["locked_total"] + ledger["paid_out"]
    assert all(value >= 0 for value in ledger.values())
    result = {"after": label, "transaction_hash": tx_hash, "state": "LATEST_FINAL" if final else "LATEST_NONFINAL",
              "accounting": ledger, "claims": {claim_id: row} if row else {}, "conserved": True,
              "appeal_extension": True, "recorded_at": datetime.now(timezone.utc).isoformat()}
    if full:
        result["balances"] = {name: view("get_balance", [client.local_account.address], final=final)
                              for name, client in run.clients.items()}
        assert sum(result["balances"].values()) == ledger["available_total"]
        assert all(value >= 0 for value in result["balances"].values())
        result["earlier_claims"] = {key: view("get_claim", [key], final=final)
                                      for key in prior["readbacks"][-1]["claims"]}
        assert result["earlier_claims"] == prior["readbacks"][-1]["claims"]
    run.record["readbacks"].append(result)
    append_save()
    run.emit(readback=label, state=result["state"], claim_status=row["status"] if row else None,
             verdict=row["verdict"] if row else None, ledger=ledger)
    return result


def poll(entry, *, finalized):
    for _ in range(240):
        raw = run.rpc("eth_getTransactionByHash", [entry["hash"]])
        state = raw.get("status_name") or raw.get("status") if raw else None
        observations = entry["lifecycle_observations"]
        if not observations or observations[-1]["status"] != state:
            observations.append({"status": state, "at": datetime.now(timezone.utc).isoformat()})
            run.emit(operation=entry["operation"], lifecycle=state, hash=entry["hash"])
        entry["accepted_observed"] = any(item["status"] == "ACCEPTED" for item in observations)
        entry["finality_status"] = state
        append_save()
        if state == "FINALIZED" or (not finalized and state == "ACCEPTED"):
            receipt = run.clients["asserter"].get_transaction(transaction_hash=entry["hash"])
            run.receipt_summary(entry, receipt)
            entry["vote_counts"] = dict(Counter(entry["votes"].values()))
            append_save()
            assert entry["leader_execution"] == ("ERROR" if entry["expected_failure"] else "SUCCESS"), entry
            assert entry["execution_result_code"] == ("rollback" if entry["expected_failure"] else "return"), entry
            if entry["expected_failure"]:
                assert entry["expected_failure"] in json.dumps(entry["execution_payload"]), entry
            return
        if state in ("CANCELED", "UNDETERMINED"):
            raise RuntimeError("Transaction terminated unexpectedly; never resubmit")
        time.sleep(3 if not finalized else 5)
    raise RuntimeError("Receipt timeout; hash recorded, no write retry")


def submit(label, actor, method, args, *, failure=None, critical=False):
    before = copy.deepcopy(run.record["readbacks"][-1])
    run.record["submitting_operation"] = label
    append_save()
    tx = run.clients[actor].write_contract(address=ADDRESS, function_name=method, args=args, leader_only=False)
    entry = {"operation": label, "actor": actor, "method": method, "args": args, "hash": str(tx),
             "expected_failure": failure, "lifecycle_observations": [], "appeal_extension": True,
             "explorer": "https://explorer-studio.genlayer.com/tx/" + str(tx)}
    run.record["transactions"].append(entry)
    append_save()
    poll(entry, finalized=not critical)
    after = snapshot(label, entry["hash"], final=not critical)
    if failure:
        assert before["claims"] == after["claims"] and before["accounting"] == after["accounting"]
    return entry, after


def remaining(row):
    return datetime.fromisoformat(row["appeal_deadline"]).timestamp() - time.time()


def require_time(row, minimum):
    seconds = remaining(row)
    run.emit(appeal_seconds_remaining=round(seconds, 2))
    if seconds < minimum:
        raise RuntimeError(f"Frozen appeal window has only {seconds:.2f}s remaining; cannot safely perform the next required step")


def judgment(row, *, appeal):
    result = row["final_result" if appeal else "first_result"]
    expected_status = "FINAL" if appeal else "PROVISIONAL"
    if row["status"] != expected_status or result.get("verdict") != "FALSE" or result.get("available") is not True:
        run.record["appeal_demo"]["unexpected_full_claim_readback"] = row
        append_save()
        raise run.UnexpectedJudgment("Appeal demonstration expected FALSE; full read-back recorded; STOP, no retry")
    assert result["evidence_digest"] == "sha256:" + fixture["sha256"]
    body = (run.ROOT / "artifacts" / FILENAME).read_text(encoding="utf-8")
    assert result["cited_text"] in body
    if appeal:
        assert len(result["cited_text"]) >= 24 and len(result["cited_text"].split()) >= 4


def prepare():
    connect()
    with run.pinned_runner_calldata(chain_id=61999, runner=run.RUNNER):
        proof = source_check()
        config = view("get_config", [], final=True)
        ledger = view("get_accounting", [], final=True)
        assert config["challenge_window_seconds"] == 120 and config["appeal_window_seconds"] == 60
        assert config["claim_count"] == 4 and ledger["locked_total"] == 0
        evidence = measure_fixture()
        run.emit(preflight="PASS", source=proof, config=config, ledger=ledger, evidence=evidence)


def main():
    global prior, claim_id, fixture, BASE_TX_COUNT, BASE_READ_COUNT
    connect()
    assert "appeal_demo" not in run.record, "Refuse duplicate extension; inspect existing record"
    prior = copy.deepcopy(run.record)
    BASE_TX_COUNT = len(prior["transactions"])
    BASE_READ_COUNT = len(prior["readbacks"])
    assert BASE_TX_COUNT == BASE_READ_COUNT == 18
    (run.ROOT / "artifacts/pre-appeal-release-manifest.json").write_bytes(run.OUTPUT.read_bytes())
    fixture = json.loads((run.ROOT / "docs/APPEAL_EVIDENCE.json").read_text(encoding="utf-8"))
    assert fixture["commit"] == EVIDENCE_COMMIT and fixture["url"] == URL
    run.record["appeal_demo"] = {"status": "IN_PROGRESS", "bond_units": BOND, "evidence": fixture,
        "prior_release_commit": run.git("rev-parse", "HEAD").decode().strip(),
        "prior_transactions_sha256": hashlib.sha256(canonical(prior["transactions"])).hexdigest(),
        "prior_readbacks_sha256": hashlib.sha256(canonical(prior["readbacks"])).hexdigest(),
        "timing_policy": "Use ACCEPTED-state read-backs during c/d/e/f to fit the frozen 60-second appeal window; later collect FINALIZED receipts and re-read final state.",
        "deployed_source_unchanged": True}
    run.record["status"] = "APPEAL_IN_PROGRESS"
    run.install_rpc_guards()
    append_save()
    with run.pinned_runner_calldata(chain_id=61999, runner=run.RUNNER):
        run.record["appeal_demo"]["source_before"] = source_check()
        config = view("get_config", [], final=True)
        assert config["claim_count"] == 4
        initial = snapshot("appeal-initial", None, final=True, full=True)
        assert initial["balances"] == {"asserter": 0, "challenger": 100, "relayer": 0}
        submit("appeal-fund-asserter", "asserter", "deposit_units", [40])
        funded = snapshot("appeal-funded-baseline", None, final=True, full=True)
        run.record["appeal_demo"]["funded_baseline"] = funded
        claim_id = "C-000005"
        run.record["appeal_demo"]["claim_id"] = claim_id
        a, state = submit("appeal-a-assert-false", "asserter", "assert_claim", [CLAIM, URL, BOND])
        b, state = submit("appeal-b-challenge", "challenger", "challenge", [claim_id, BOND])
        assert state["claims"][claim_id]["status"] == "DISPUTED"
        run.until(state["claims"][claim_id]["challenge_deadline"])
        c, state = submit("appeal-c-adjudicate-FALSE", "relayer", "adjudicate", [claim_id], critical=True)
        row = state["claims"][claim_id]
        judgment(row, appeal=False)
        assert row["provisional_winner"] == run.record["participants"]["challenger"].lower()
        require_time(row, 18)
        d, state = submit("appeal-d-EXPECTED-FAILURE-winner", "challenger", "appeal", [claim_id, 2 * BOND],
                          failure="only the provisional loser may appeal once", critical=True)
        require_time(row, 10)
        e, state = submit("appeal-e-EXPECTED-FAILURE-wrong-bond", "asserter", "appeal", [claim_id, 2 * BOND - 1],
                          failure="appeal bond must equal twice the original bond", critical=True)
        require_time(row, 4)
        f, state = submit("appeal-f-loser-confirms-FALSE-4B", "asserter", "appeal", [claim_id, 2 * BOND], critical=True)
        row = state["claims"][claim_id]
        judgment(row, appeal=True)
        assert row["settled_units"] == 4 * BOND and row["settlement_count"] == 1 and row["appeal_used"] is True
        assert row["final_winner"] == run.record["participants"]["challenger"].lower()
        for entry in (c, d, e, f):
            poll(entry, finalized=True)
        settled = snapshot("appeal-f-finalized-verification", f["hash"], final=True, full=True)
        judgment(settled["claims"][claim_id], appeal=True)
        g, state = submit("appeal-g-EXPECTED-FAILURE-second-appeal", "asserter", "appeal", [claim_id, 2 * BOND],
                          failure="claim is already terminal")
        final = snapshot("appeal-h-final-accounting", g["hash"], final=True, full=True)
        assert final["claims"][claim_id]["escrow_units"] == final["accounting"]["locked_total"] == 0
        assert final["accounting"] == {"total_deposited": 240, "available_total": 140, "locked_total": 0, "paid_out": 100, "conserved": True}
        assert final["balances"] == {"asserter": 10, "challenger": 130, "relayer": 0}
        run.record["appeal_demo"].update(status="PASS", final_claim=final["claims"][claim_id],
            final_accounting=final["accounting"], final_balances=final["balances"],
            asserter_net_from_funded_baseline=-30, challenger_net_from_funded_baseline=30,
            original_entries_unchanged=True, source_after=source_check(),
            transaction_hashes={entry["operation"]: entry["hash"] for entry in run.record["transactions"][BASE_TX_COUNT:]})
        run.record["appeal_history"] = view("get_history", [], final=True)
        run.record["status"] = "COMPLETE_WITH_LIVE_APPEAL"
        append_save()
        run.emit(status="PASS", claim=final["claims"][claim_id], ledger=final["accounting"], balances=final["balances"])


if __name__ == "__main__":
    try:
        prepare() if "--prepare" in sys.argv else main()
    except Exception as error:
        if run.record.get("appeal_demo"):
            run.record["appeal_demo"]["status"] = "STOP_UNEXPECTED_JUDGMENT" if isinstance(error, run.UnexpectedJudgment) else "STOP_BLOCKER"
            run.record["appeal_demo"]["stop_reason"] = str(error)
            run.record["status"] = run.record["appeal_demo"]["status"]
            append_save()
        run.emit(status="STOP", error=str(error))
        sys.exit(1)

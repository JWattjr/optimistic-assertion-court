"""One gasless StudioNet run; persist every hash, never retry a write/judgment."""
from __future__ import annotations

import base64
import hashlib
import importlib.metadata
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from eth_account import Account
from genlayer_py import create_client
from genlayer_py.chains import studionet
from genlayer_py.types import TransactionHashVariant

from studionet_compat import RUNNER, pinned_runner_calldata
from rpc_guard import guarded_request

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-10-20"
OUTPUT = ROOT / "deployments" / f"studionet-release-{DATE}.json"
RPC_LOG = ROOT / "deployments" / f"studionet-release-{DATE}-rpc.jsonl"
ENDPOINT = "https://studio.genlayer.com/api"
SOURCE = "contracts/optimistic_assertion_court.py"
CONSTRUCTOR = ["Optimistic Assertion Court", 120, 60, 1800]
TRUE_CLAIM = "The approved bridge length is exactly one hundred metres."
FALSE_CLAIM = "The approved bridge length is exactly two hundred metres."
record = {}
clients = {}
address = None
known_claims = []


def install_rpc_guards():
    for actor, client in clients.items():
        request = client.provider.make_request

        def guarded(method, params, _request=request, _actor=actor):
            def broadcast(native_hash):
                record.setdefault("broadcasts", []).append({"actor": _actor, "evm_hash": native_hash,
                    "operation": record.get("submitting_operation"), "at": datetime.now(timezone.utc).isoformat()})
                save()

            def transient(method, attempt, error):
                record.setdefault("transport_incidents", []).append({"method": method, "attempt": attempt, "error": error})
                save()
                emit(readonly_rpc_retry=method, attempt=attempt)

            return guarded_request(_request, method, params, broadcast=broadcast, transient=transient)

        client.provider.make_request = guarded


class UnexpectedJudgment(RuntimeError):
    pass


def save():
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(record, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")


def emit(**values):
    print(json.dumps(values, default=str), flush=True)


def redact(value):
    if isinstance(value, dict):
        return {key: "[REDACTED]" if str(key).lower() in
                ("api_key", "private_key", "password", "secret", "token", "authorization") else redact(item)
                for key, item in value.items()}
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


def command(args):
    result = subprocess.run(args, capture_output=True, check=True)
    return result.stdout


def git(*args):
    return command(["git", "-C", str(ROOT), *args])


def rpc(method, params):
    def request(method, params):
        response = requests.post(ENDPOINT, json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
                                 timeout=(15, 60))
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            raise RuntimeError("invalid JSON RPC response")

    def transient(method, attempt, error):
        record.setdefault("transport_incidents", []).append({"method": method, "attempt": attempt, "error": error})
        save()
        emit(readonly_rpc_retry=method, attempt=attempt)

    result = guarded_request(request, method, params, broadcast=lambda _: None, transient=transient)
    with RPC_LOG.open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"at": datetime.now(timezone.utc).isoformat(), "method": method,
                                 "params": params, "response": redact(result)}) + "\n")
    if "error" in result:
        raise RuntimeError(f"{method} failed: {result['error']}")
    return result["result"]


def leaders(receipt):
    value = (receipt.get("consensus_data") or {}).get("leader_receipt") or []
    return value if isinstance(value, list) else [value]


def receipt_summary(entry, receipt):
    leader_list = leaders(receipt)
    leader = leader_list[0] if leader_list else {}
    result = leader.get("result") or {}
    entry.update(leader_execution=leader.get("execution_result"),
                 execution_result_code=result.get("status") if isinstance(result, dict) else None,
                 execution_payload=result.get("payload") if isinstance(result, dict) else result,
                 consensus_result=receipt.get("result_name"),
                 votes=(receipt.get("consensus_data") or {}).get("votes", {}),
                 leader_call_counts=(leader.get("execution_stats") or {}).get("call_counts", {}))
    record["receipts"][entry["hash"]] = redact(receipt)


def wait(entry):
    last = None
    for _ in range(240):
        raw = rpc("eth_getTransactionByHash", [entry["hash"]])
        state = raw.get("status_name") or raw.get("status") if raw else None
        if isinstance(state, int):
            raise RuntimeError("Unexpected numeric lifecycle status; inspect RPC log")
        if state != last:
            entry["lifecycle_observations"].append({"status": state, "at": datetime.now(timezone.utc).isoformat()})
            emit(operation=entry["operation"], lifecycle=state, hash=entry["hash"])
            last = state
        entry["accepted_observed"] = any(item["status"] == "ACCEPTED" for item in entry["lifecycle_observations"])
        entry["finality_status"] = state
        save()
        if state == "FINALIZED":
            receipt = clients["asserter"].get_transaction(transaction_hash=entry["hash"])
            receipt_summary(entry, receipt)
            save()
            expected = "ERROR" if entry["expected_failure"] else "SUCCESS"
            if entry["leader_execution"] != expected:
                raise RuntimeError(f"Unexpected execution for {entry['operation']}: {entry['leader_execution']}")
            if entry["expected_failure"] and entry["execution_result_code"] != "rollback":
                raise RuntimeError("Expected a business-rule rollback, not a runtime/dispatch failure")
            emit(operation=entry["operation"], finality=state, execution=entry["leader_execution"],
                 code=entry["execution_result_code"], votes=entry["votes"])
            return receipt
        if state in ("CANCELED", "UNDETERMINED"):
            raise RuntimeError(f"Transaction terminated unexpectedly: {state}")
        time.sleep(5)
    raise RuntimeError("Finality timeout; transaction hash recorded, no resubmission")


def submit(label, actor, method, args, *, expected_failure=None):
    record["submitting_operation"] = label
    save()
    tx = clients[actor].write_contract(address=address, function_name=method, args=args, leader_only=False)
    entry = {"operation": label, "actor": actor, "method": method, "args": args, "hash": str(tx),
             "expected_failure": expected_failure, "lifecycle_observations": [],
             "explorer": "https://explorer-studio.genlayer.com/tx/" + str(tx)}
    record["transactions"].append(entry)
    save()  # Persist the write hash before any polling. No retry path exists.
    wait(entry)
    if expected_failure and expected_failure not in json.dumps(entry["execution_payload"]):
        raise RuntimeError("Expected failure message differs")
    snapshot(label, entry["hash"])
    return entry


def view(method, args):
    return clients["asserter"].read_contract(address=address, function_name=method, args=args,
                         transaction_hash_variant=TransactionHashVariant.LATEST_FINAL)


def snapshot(label, tx_hash):
    ledger = view("get_accounting", [])
    balances = {name: view("get_balance", [client.local_account.address]) for name, client in clients.items()}
    claims = {claim: view("get_claim", [claim]) for claim in known_claims}
    entry = {"after": label, "transaction_hash": tx_hash, "state": "LATEST_FINAL",
             "accounting": ledger, "balances": balances, "claims": claims}
    entry["conserved"] = (ledger["conserved"] and ledger["total_deposited"] ==
        ledger["available_total"] + ledger["locked_total"] + ledger["paid_out"] and
        sum(balances.values()) == ledger["available_total"] and
        sum(row["escrow_units"] for row in claims.values()) == ledger["locked_total"] and
        all(value >= 0 for value in balances.values()) and
        all(value >= 0 for field, value in ledger.items()) and
        all(row["settlement_count"] == (1 if row["status"] in ("ACCEPTED", "FINAL", "VOID") else 0)
            for row in claims.values()))
    record["readbacks"].append(entry)
    save()
    if not entry["conserved"]:
        raise RuntimeError("Accounting or settlement invariant failed on read-back")
    emit(readback=label, balances=balances, ledger=ledger,
         claims={claim: row["status"] for claim, row in claims.items()})
    return entry


def until(timestamp):
    target = datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp() + 3
    while time.time() < target:
        emit(waiting_for=timestamp, seconds_remaining=round(target - time.time()))
        time.sleep(min(20, max(0.1, target - time.time())))


def judge(claim, expected, fixture):
    submit(claim + "-adjudicate", "relayer", "adjudicate", [claim])
    row = record["readbacks"][-1]["claims"][claim]
    actual = row["first_result"]
    if row["status"] != "PROVISIONAL" or actual.get("verdict") != expected or not actual.get("available"):
        raise UnexpectedJudgment(f"{claim}: expected available {expected}, observed {actual}; STOP, no retry")
    if actual["evidence_digest"] != "sha256:" + fixture["sha256"]:
        raise UnexpectedJudgment(f"{claim}: live digest differs from curl fixture; STOP, no retry")
    until(row["appeal_deadline"])
    submit(claim + "-finalize", "relayer", "finalize", [claim])
    row = record["readbacks"][-1]["claims"][claim]
    winner = record["participants"]["asserter" if expected == "TRUE" else "challenger"].lower()
    assert row["status"] == "FINAL" and row["final_winner"] == winner and row["settled_units"] == 20


def run_demo(fixtures, commit):
    known_claims.append("C-000001")
    submit("a-assert-true-unchallenged", "asserter", "assert_claim", [TRUE_CLAIM, fixtures["unchallenged.txt"]["url"], 10])
    row = record["readbacks"][-1]["claims"]["C-000001"]
    until(row["challenge_deadline"])
    entry = submit("a-finalize-unchallenged", "relayer", "finalize", ["C-000001"])
    row = record["readbacks"][-1]["claims"]["C-000001"]
    assert row["status"] == "ACCEPTED" and row["settled_units"] == 10 and row["first_result"] == {}
    assert record["readbacks"][-1]["balances"]["asserter"] == 100
    nondet = {key: value for key, value in entry["leader_call_counts"].items()
              if any(token in key.upper() for token in ("NONDET", "PROMPT", "WEB", "SPAWN"))}
    record["unchallenged_no_application_nondeterminism"] = {"source_path_proves_no_judge_call": True,
                  "receipt_call_counts": entry["leader_call_counts"], "nondet_call_counts": nondet}
    assert not any(nondet.values())

    for claim_id, text, fixture_name, expected in [
        ("C-000002", FALSE_CLAIM, "false-assertion.txt", "FALSE"),
        ("C-000003", TRUE_CLAIM, "frivolous-challenge.txt", "TRUE")]:
        known_claims.append(claim_id)
        submit(claim_id + "-assert", "asserter", "assert_claim", [text, fixtures[fixture_name]["url"], 10])
        submit(claim_id + "-challenge", "challenger", "challenge", [claim_id, 10])
        until(record["readbacks"][-1]["claims"][claim_id]["challenge_deadline"])
        judge(claim_id, expected, fixtures[fixture_name])

    known_claims.append("C-000004")
    submit("d-assert-for-late-challenge", "asserter", "assert_claim", [TRUE_CLAIM, fixtures["unchallenged.txt"]["url"], 10])
    until(record["readbacks"][-1]["claims"]["C-000004"]["challenge_deadline"])
    before = record["readbacks"][-1]
    submit("d-EXPECTED-FAILURE-late-challenge", "challenger", "challenge", ["C-000004", 10],
           expected_failure="challenge window has closed")
    after = record["readbacks"][-1]
    assert all(before[field] == after[field] for field in ("accounting", "balances", "claims"))
    submit("d-finalize-after-rejected-challenge", "relayer", "finalize", ["C-000004"])

    balance = record["readbacks"][-1]["balances"]["asserter"]
    assert balance == 100
    submit("e-first-withdrawal", "asserter", "withdraw_units", [balance])
    before = record["readbacks"][-1]
    submit("e-EXPECTED-FAILURE-second-withdrawal", "asserter", "withdraw_units", [balance],
           expected_failure="insufficient available balance")
    after = record["readbacks"][-1]
    assert all(before[field] == after[field] for field in ("accounting", "balances", "claims"))
    record["final_history"] = view("get_history", [])
    record["gates"] = {"technical": "PASS", "distinctiveness": "PASS", "evidence": "PASS_PENDING_FINAL_PUSH"}
    record["status"] = "LIVE_DEMO_PASS_PENDING_FINAL_PUSH"
    save()
    emit(status=record["status"], address=address, source_commit=commit,
         transactions=len(record["transactions"]))


def main():
    global address, clients, record
    if OUTPUT.exists():
        raise RuntimeError("Manifest already exists; refuse duplicate live run")
    if git("status", "--porcelain").strip():
        raise RuntimeError("Deploy only from a clean local commit")
    commit = git("rev-parse", "HEAD").decode().strip()
    source = git("show", f"{commit}:{SOURCE}")
    assert source == (ROOT / SOURCE).read_bytes()
    assert source.splitlines()[0] == ('# { "Depends": "' + RUNNER + '" }').encode()
    visibility = json.loads(command(["gh", "repo", "view", "JWattjr/optimistic-assertion-court", "--json", "visibility"]))
    assert visibility["visibility"] == "PRIVATE"
    evidence = json.loads((ROOT / "docs/EVIDENCE.json").read_text(encoding="utf-8"))
    fixtures = {entry["file"]: entry for entry in evidence["fixtures"]}
    record = {"release_date": DATE, "status": "IN_PROGRESS", "network": "StudioNet", "chain_id": 61999,
              "rpc": ENDPOINT, "source_commit": commit, "source_path": SOURCE,
              "source_blob": git("rev-parse", f"{commit}:{SOURCE}").decode().strip(),
              "source_bytes": len(source), "source_sha256": hashlib.sha256(source).hexdigest(),
              "runner": RUNNER, "constructor_args": CONSTRUCTOR,
              "toolchain": {name: importlib.metadata.version(name) for name in
                            ("genlayer-test", "genvm-linter", "genlayer-py")},
              "python_executable": sys.executable, "python_version": sys.version,
              "client_adapter": "scripts/studionet_compat.py (license-bundle adapter)",
              "repository": "https://github.com/JWattjr/optimistic-assertion-court",
              "repository_visibility": "PRIVATE", "evidence": evidence, "portal_submitted": False,
              "transactions": [], "readbacks": [], "receipts": {}, "gates": {}}
    save()
    assert int(rpc("eth_chainId", []), 16) == 61999
    credential = subprocess.run(["node", r"C:\Users\User\Desktop\Intelligent Contracts\release\credential_key.mjs",
                                 "moment-grid-studionet"], capture_output=True, text=True)
    if credential.returncode:
        raise RuntimeError("Credential helper failed; key output is suppressed")
    asserter = Account.from_key(credential.stdout.strip())
    # Deterministic isolated demo actors; only public addresses enter artifacts.
    challenger = Account.from_key(hashlib.sha256(bytes(asserter.key) + b"optimistic-court/challenger/2026-10-20").digest())
    relayer = Account.from_key(hashlib.sha256(bytes(asserter.key) + b"optimistic-court/relayer/2026-10-20").digest())
    del credential
    clients = {name: create_client(chain=studionet, account=account) for name, account in
               {"asserter": asserter, "challenger": challenger, "relayer": relayer}.items()}
    install_rpc_guards()
    record["participants"] = {name: client.local_account.address for name, client in clients.items()}
    save()
    with pinned_runner_calldata(chain_id=61999, runner=RUNNER):
        tx = clients["asserter"].deploy_contract(code=source, args=CONSTRUCTOR, leader_only=False)
        deployment = {"operation": "deploy", "hash": str(tx), "actor": "asserter", "method": "__init__",
                      "args": CONSTRUCTOR, "expected_failure": None, "lifecycle_observations": []}
        record["transactions"].append(deployment)
        save()
        receipt = wait(deployment)
        address = (receipt.get("data") or {}).get("contract_address") or (receipt.get("tx_data_decoded") or {}).get("contract_address")
        if not address:
            raise RuntimeError("Successful deployment lacks an address")
        record["contract_address"] = address
        deployed = base64.b64decode(rpc("gen_getContractCode", [address]))
        record["onchain_source_matches_git_blob"] = deployed == source
        record["deployed_source_sha256"] = hashlib.sha256(deployed).hexdigest()
        save()
        assert deployed == source
        record["deployed_config"] = view("get_config", [])
        snapshot("deploy", str(tx))
        submit("deposit-asserter", "asserter", "deposit_units", [100])
        submit("deposit-challenger", "challenger", "deposit_units", [100])

        run_demo(fixtures, commit)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        if record:
            record["status"] = "STOP_UNEXPECTED_JUDGMENT" if isinstance(error, UnexpectedJudgment) else "STOP_BLOCKER"
            record["stop_reason"] = str(error)
            save()
        emit(status=record.get("status", "PREFLIGHT_BLOCKER"), error=str(error))
        sys.exit(1)

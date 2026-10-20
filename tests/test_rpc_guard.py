"""Release-control tests: a flaky receipt endpoint must never duplicate writes."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location("court_rpc_guard", Path(__file__).parents[1] / "scripts/rpc_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


def test_readonly_receipt_retry_does_not_repeat_broadcast():
    calls, broadcasts, retries = [], [], []
    def request(method, params):
        calls.append(method)
        if len(calls) == 1:
            raise RuntimeError("502 invalid JSON")
        return {"result": {"status": "0x1"}}
    assert guard.guarded_request(request, "eth_getTransactionReceipt", ["known-hash"],
            broadcast=broadcasts.append, transient=lambda *args: retries.append(args), sleep=lambda _: None)
    assert calls == ["eth_getTransactionReceipt", "eth_getTransactionReceipt"]
    assert not broadcasts and len(retries) == 1


def test_broadcast_hash_is_captured_before_any_receipt_read():
    broadcasts = []
    result = guard.guarded_request(lambda method, params: {"result": "native-hash"},
                "eth_sendRawTransaction", ["not-logged"], broadcast=broadcasts.append,
                transient=lambda *args: pytest.fail("write retry"))
    assert result == {"result": "native-hash"} and broadcasts == ["native-hash"]


def test_ambiguous_write_failure_is_never_retried():
    calls = []
    def request(method, params):
        calls.append(method)
        raise RuntimeError("502 after possible broadcast")
    with pytest.raises(RuntimeError, match="502"):
        guard.guarded_request(request, "eth_sendRawTransaction", [],
                              broadcast=lambda _: None, transient=lambda *args: pytest.fail("write retried"))
    assert calls == ["eth_sendRawTransaction"]


def test_nontransient_read_failure_is_not_retried():
    calls = []
    def request(method, params):
        calls.append(method)
        raise ValueError("invalid method argument")
    with pytest.raises(ValueError, match="invalid method"):
        guard.guarded_request(request, "eth_call", [], broadcast=lambda _: None,
                              transient=lambda *args: pytest.fail("nontransient read retried"))
    assert calls == ["eth_call"]

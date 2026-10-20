"""Scoped adapter from the reviewed license-bundle release; no SDK upgrades."""
from contextlib import contextmanager
from importlib.metadata import version

from genlayer_py.contracts import actions
from genlayer_py.contracts.utils import make_calldata_object

RUNNER = "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6"


def legacy_calldata_object(method=None, args=None, kwargs=None):
    envelope = make_calldata_object(method=method, args=args, kwargs=kwargs)
    if "" in envelope:
        envelope["method"] = envelope.pop("")
    return envelope


@contextmanager
def pinned_runner_calldata(*, chain_id, runner):
    if chain_id != 61999 or runner != RUNNER or version("genlayer-py") != "0.19.0rc2":
        raise RuntimeError("Adapter restricted to StudioNet, approved runner, and pinned SDK")
    original = actions.make_calldata_object
    actions.make_calldata_object = legacy_calldata_object
    try:
        yield
    finally:
        actions.make_calldata_object = original

# Pre-live review — 2026-10-20

Reviewed `DESIGN.md`, `PHASE2_HANDOFF.md`, the complete contract, the Windows
direct-mode fixture, and the original 113 tests before authorizing any live
transaction. The reviewed Phase 2 head is
`37603174bf145d8b5fd4dc3571d6ce5781c37cc2`.

## Findings and changes

No production-code defect was found in consensus binding, deterministic
settlement, account conservation, or the one-settlement state machine. The
contract source is unchanged by this review. There were verification gaps:

- Rejection tests compared only aggregate accounting and history, which could
  miss a change to a claim or a pair of cancelling balance changes. `rejected`
  now compares all nonzero direct-VM storage bytes before and after every
  rejected operation. Zero-only read-allocation slots are normalized out.
- Existing forgeries called the actual captured validator, but did not cover
  both stages comprehensively or explicit replay contexts. Added 53 cases in
  `tests/test_review.py`: all four missing fields; payout/payer/status injection;
  availability/digest/citation type and content forgeries; malformed, failed
  and false citation confirmation; exact leader excerpt delivery/preservation;
  cross-claim replay; first-stage-to-appeal replay; changed-evidence replay;
  wrong-caller withdrawal; and LLM settlement-field injection.
- Added transaction tests that execute the actual captured callback against a
  forged digest and emulate the protocol refusing a rejected leader result.
  These prove that the contract does not write before `_judge` returns. This
  is a controlled direct-mode test, not a simulation of network quorum.

## Safety conclusions

The only stored nondeterministic object has exactly `verdict`, `cited_text`,
`evidence_digest`, and `available`. Unknown keys fail. Availability and digest
are independently derived and exactly matched. Verdict is independently
classified and exactly matched. The leader citation must be an exact substring
of the validator's own body under the current stage bounds, then its own model
must return a genuine boolean support confirmation. Canonical unavailable and
UNDETERMINED results bind the empty citation as well. No unbound reasoning,
recipient, amount, or model-selected status is persisted.

Only deterministic contract code maps TRUE/FALSE to asserter/challenger,
computes B/2B/4B, chooses lifecycle transitions, and releases funds. Every public
write invokes `_invariant`; u256 storage, pre-debit checks, an independent sum
of accounts and escrows, and one guarded `_settle` preserve conservation and
prevent negative balances, double settlement, and withdrawal reuse. The appeal
path runs consensus before mutating the ledger. Stale resolution has no web,
model or nondeterministic call and blocks the competing award entrypoints at
the deadline.

## Re-run results

- Pinned venv: `intelligent-contracts-v2/.venv`; no package upgrades.
- `genvm-lint check`: PASS, 3 AST checks and SDK semantic validation;
  13 methods (8 writes, 5 views), 4 constructor parameters. Advisory I200
  reports a newer runner; the approved runner stays pinned.
- `python -m pytest -q --junitxml=artifacts/review-junit.xml`:
  **166 passed, 0 failed, 0 errors, 0 skipped** in 42.21 seconds.
- Direct-mode web/model results are mocks. Callback execution proves the
  validation code path, not model correctness or live votes/finality.

## Remaining limits and live checks

The SDK supplies a complete response body without a prefix-length option.
The code rejects oversized, invalid UTF-8, non-200, compressed or visibly
length-mismatched responses. SDK redirect handling and resolved-IP enforcement
are runtime properties; lexical URL validation cannot establish them. The
live demo uses direct commit-pinned raw GitHub URLs and must compare the stored
digest to bytes downloaded by curl. Model error, shared model bias, and prompt
injection remain possible. Units are synthetic, so there is no real economic
deterrence or asset custody. These are disclosed limitations, not live claims.

The user has now authorized Phase 3. The older phase-boundary wording in the
Phase 2 handoff is historical. The contract GitHub repo must be PRIVATE; the
separate evidence repo is PUBLIC and contains fixture text only. No Portal
submission is authorized. Stop on an unexpected live judgment.

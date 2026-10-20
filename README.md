# Optimistic Assertion Court

A bonded assertion is accepted after an unchallenged window without a web or
LLM call. A matched-bond challenge opens semantic adjudication. GenLayer
validators independently read the same frozen URL, agree on verdict, byte digest
and availability, and verify the leader's exact supporting citation. Contract
code settles the synthetic ledger. Only the loser may fund one stricter appeal.

This is a Phase 2 local implementation. No deployment or live consensus is
claimed. See [design](docs/DESIGN.md), [test matrix](docs/TEST_MATRIX.md) and
[handoff](docs/PHASE2_HANDOFF.md).

## Settlement

Let the original bond be `B`; the challenger posts exactly `B`. A determinate
first judgment leaves `2B` locked through the appeal window. TRUE selects the
asserter, FALSE the challenger. If no appeal is made, `finalize` after that
window and before the stale deadline credits `2B` to that winner. UNDETERMINED
or agreed unavailable evidence immediately voids and refunds `B` to each side.

Only the provisional loser may appeal, once, with exactly `2B`. A fresh stricter
judgment settles atomically: the final TRUE/FALSE winner gets the full `4B` pot;
otherwise the original `B` contributions and appellant's `2B` are refunded.
An appeal that flips the verdict changes who receives the pot. A failed appeal
transaction consumes no bond or appeal allowance.

`stale_deadline = challenged_at + dispute_deadline_seconds` is frozen per claim.
At or after it, anyone may `void_stale` a DISPUTED or PROVISIONAL claim, refunding
all locked bonds without inference. Other dispute resolution actions reject at
this boundary. The deadline does not extend when a first judgment is late.

`total_deposited = available_total + locked_total + paid_out` after every write.
Settlement credits available balances; only withdrawals increase `paid_out`.
The contract independently sums bounded accounts and claim escrows and requires
one settlement per terminal claim. Reusing an exhausted withdrawal balance fails.

## Local verification

Use the existing pinned environment, without upgrading it:

```powershell
$py = 'C:\Users\User\Desktop\Genlayer apps\intelligent-contracts-v2\.venv\Scripts\python.exe'
$lint = 'C:\Users\User\Desktop\Genlayer apps\intelligent-contracts-v2\.venv\Scripts\genvm-lint.exe'
& $lint check contracts/optimistic_assertion_court.py --json
& $py -m pytest -q
```

The runner header pins
`py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`.
Requirements are `genlayer-test==0.30.0rc2` and `genvm-linter==0.11.1rc2`.
Tests use the cached legacy `v0.6.0-rc5` SDK and a Windows compatibility fixture
copied from the local accepted auction project. They explicitly exercise
captured validator callbacks as well as leader execution; this is mocked local
verification, not network consensus or proof of runner byte identity.

## Limits

Units are permissionlessly minted synthetic demo balances; no real assets are
custodied or transferred. Evidence is one complete returned HTTP-200 UTF-8 body
of 1-15,000 bytes. No rendering, prefix classification, link following, publisher
authentication or external transfers occur in contract code. The pinned SDK
does not expose redirect controls; runtime redirects and transport completeness
need live review. Model error and prompt injection remain risks. Storage is
bounded to 32 claims, 128 ledger accounts and 256 history records.

Unchallenged acceptance is acceptance by this mechanism, not an independently
verified truth finding. Court `ACCEPTED`/`FINAL` are distinct from protocol
transaction `ACCEPTED`/`FINALIZED`. The five local comparators do not gate their
semantic judgments on a matched-bond economic dispute; see the source-backed
comparison table in the design.

# Optimistic Assertion Court

A bonded assertion is accepted after an unchallenged window without a web or
LLM call. A matched-bond challenge opens semantic adjudication. GenLayer
validators independently read the same frozen URL, agree on verdict, byte digest
and availability, and verify the leader's exact supporting citation. Contract
code settles the synthetic ledger. Only the loser may fund one stricter appeal.

The implementation passed pre-live review: 166 direct contract cases plus
4 release RPC guard tests, 170 local tests in total.
See [design](docs/DESIGN.md), [test matrix](docs/TEST_MATRIX.md),
[review](docs/REVIEW.md), and [Phase 2 handoff](docs/PHASE2_HANDOFF.md).
Pinned fixture measurements are in [EVIDENCE.json](docs/EVIDENCE.json).
Live execution is recorded separately in the dated deployment manifest.

## StudioNet release — 2026-10-20

Contract: `0xC59715a21e2cac8e8978F4D3098087930399fCF2`. All 18 demo transactions reached FINALIZED;
16 executed successfully and the two deliberate failures reverted as expected.
The three gates — technical, local distinctiveness and evidence — pass.

Deployed-source commit: `3b0ce9c68628538431942bc6d8db00773ab716cf`. Contract Git blob: `f90a574586da2012fd5206161835bb04b4a00dc7`.
The deployed source matches all 23,139 Git blob bytes exactly.
The final repository HEAD adds documentation and the manifest while retaining that source blob.

[Manifest](deployments/studionet-release-2026-10-20.json) records constructor arguments, every
transaction lifecycle, execution result, votes, read-backs and accounting checks.
[Live report](docs/LIVE_RELEASE.md) and [Portal draft](SUBMISSION_DRAFT.md) are review artifacts;
nothing was submitted. The contract repository remains PRIVATE. The public
[fixture repository](https://github.com/JWattjr/genlayer-demo-evidence) contains fictional text only.

| Required live case | Outcome | FINALIZED transaction |
|---|---|---|
| a. True, unchallenged | ACCEPTED; B refunded; no application nondeterminism | [`0x7e7ef28fe8…`](https://explorer-studio.genlayer.com/tx/0x7e7ef28fe87f011991c605c816fde8b3f4b0f355c02ba4185f91d2e19d59800e) |
| b. False, challenged | FALSE; challenger provisional winner | [`0x688502f0ef…`](https://explorer-studio.genlayer.com/tx/0x688502f0ef5512244fa7f4922f93de91fc05b822da67a6b0d17a70521e6ce467) |
| b. Award released | FINAL; challenger receives 2B; asserter loses B | [`0xa7c9684e2a…`](https://explorer-studio.genlayer.com/tx/0xa7c9684e2a4958228014f85aa0cd23f60b4a0c1063531e5d1eb84e576e7f54b1) |
| c. Frivolous challenge | TRUE; asserter provisional winner | [`0x6471420043…`](https://explorer-studio.genlayer.com/tx/0x64714200430d26d74e8fd4b354ac24026fa820966d1f1581fd5919b49e0917d1) |
| c. Award released | FINAL; asserter receives 2B; challenger loses B | [`0xc6df9b659e…`](https://explorer-studio.genlayer.com/tx/0xc6df9b659ebb635d40711e140000c180db56d1c7150eb625453748eddb1e11f7) |
| d. Late challenge | Expected ERROR/rollback; state unchanged | [`0x0bc9e060bf…`](https://explorer-studio.genlayer.com/tx/0x0bc9e060bf03b71bf6dbe5cec4910cca672567a1c04d2babe3549f680cf9e30c) |
| e. Second withdrawal | Expected ERROR/rollback; state unchanged | [`0x8df4dcfb09…`](https://explorer-studio.genlayer.com/tx/0x8df4dcfb09f2df218d245bf8ccf998df9561ee4e788b87c1cc84acfe515a3593) |

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
are only verified for the pinned demo responses. Model error and prompt injection remain risks. Storage is
bounded to 32 claims, 128 ledger accounts and 256 history records.

Unchallenged acceptance is acceptance by this mechanism, not an independently
verified truth finding. Court `ACCEPTED`/`FINAL` are distinct from protocol
transaction `ACCEPTED`/`FINALIZED`. The five local comparators do not gate their
semantic judgments on a matched-bond economic dispute; see the source-backed
comparison table in the design.

All demo actors are controlled by one operator. The live demo does not exercise the appeal,
stale-refund or unavailable-evidence paths; those are covered by mocked direct tests.

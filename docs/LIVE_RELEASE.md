# Live release evidence — 2026-10-20

StudioNet contract: `0xC59715a21e2cac8e8978F4D3098087930399fCF2`; chain ID 61999.

Reviewed deployed-source commit: `3b0ce9c68628538431942bc6d8db00773ab716cf`.
Git blob: `f90a574586da2012fd5206161835bb04b4a00dc7`; 23139 raw bytes;
SHA-256: `0ec8715d499d3b87cb05c02d2b78c846df0aafee27149fe039d34bf7d588c899`. The on-chain source was fetched and compared byte-for-byte.

Frozen constructor arguments: `["Optimistic Assertion Court", 120, 60, 1800]`.

## Gates

- **technical: PASS**. 170 local tests (166 contract + 4 RPC guard); lint/SDK validation; exact deployed source bytes; 18 finalized txs with separate execution results and invariant read-backs.
- **distinctiveness: PASS**. Rechecked all five local comparator entrypoints; none gates factual consensus on a matched-bond economic dispute. DESIGN.md section 14.
- **evidence: PASS**. 3 commit-pinned public text fixtures, each 266 curl-measured raw bytes; 2 live digests match; votes, execution, failures and read-backs recorded.

## Local review changes

No contract source change was necessary. Added 53 adversarial cases and full-storage comparison
after rejected writes; corrected the get_config description; added review results, curl evidence,
and a StudioNet runner using the scoped legacy calldata adapter. Final pinned-toolchain rerun:
170 passed (166 contract + 4 RPC guard), 0 failed/errors/skipped; lint passed 3 AST checks plus SDK validation.

The SDK encountered HTTP 502 after broadcasting the challenger deposit. Read-only recovery
located its finalized transaction by sender, recipient and decoded calldata. It was not
resubmitted. The controller now captures broadcast acknowledgements before receipt reads
and retries transient reads only; the deployed contract was not changed or redeployed.

## Required demo

| Required live case | Outcome | FINALIZED transaction |
|---|---|---|
| a. True, unchallenged | ACCEPTED; B refunded; no application nondeterminism | [`0x7e7ef28fe8…`](https://explorer-studio.genlayer.com/tx/0x7e7ef28fe87f011991c605c816fde8b3f4b0f355c02ba4185f91d2e19d59800e) |
| b. False, challenged | FALSE; challenger provisional winner | [`0x688502f0ef…`](https://explorer-studio.genlayer.com/tx/0x688502f0ef5512244fa7f4922f93de91fc05b822da67a6b0d17a70521e6ce467) |
| b. Award released | FINAL; challenger receives 2B; asserter loses B | [`0xa7c9684e2a…`](https://explorer-studio.genlayer.com/tx/0xa7c9684e2a4958228014f85aa0cd23f60b4a0c1063531e5d1eb84e576e7f54b1) |
| c. Frivolous challenge | TRUE; asserter provisional winner | [`0x6471420043…`](https://explorer-studio.genlayer.com/tx/0x64714200430d26d74e8fd4b354ac24026fa820966d1f1581fd5919b49e0917d1) |
| c. Award released | FINAL; asserter receives 2B; challenger loses B | [`0xc6df9b659e…`](https://explorer-studio.genlayer.com/tx/0xc6df9b659ebb635d40711e140000c180db56d1c7150eb625453748eddb1e11f7) |
| d. Late challenge | Expected ERROR/rollback; state unchanged | [`0x0bc9e060bf…`](https://explorer-studio.genlayer.com/tx/0x0bc9e060bf03b71bf6dbe5cec4910cca672567a1c04d2babe3549f680cf9e30c) |
| e. Second withdrawal | Expected ERROR/rollback; state unchanged | [`0x8df4dcfb09…`](https://explorer-studio.genlayer.com/tx/0x8df4dcfb09f2df218d245bf8ccf998df9561ee4e788b87c1cc84acfe515a3593) |

Final totals: D=200, A=100, L=0, P=100. Asserter available=0 after withdrawing 100;
challenger available=100. Every intermediate snapshot satisfies D=A+L+P. Both challenged
claims settled once for 20 units; both unchallenged claims settled once for 10 units.

## Transaction evidence

ACCEPTED and FINALIZED lifecycle observations are stored separately from execution results.
A status skipped by polling is NOT OBSERVED, not invented; two expected failures finalized
their rollback outcomes. Court outcomes are majority results; dissent and idle votes are
retained explicitly rather than described as unanimous. Full receipts and vote addresses
are in the manifest.

| Operation | Lifecycle | Leader execution/code | Votes | Hash |
|---|---|---|---|---|
| deploy | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0x2b7ba622835f7ea48349977ced5d07964d3032fcae2fcc72fc60b0f1b3e33f78` |
| deposit-asserter | FINALIZED | SUCCESS/return | agree=4, idle=1 | `0x01ff36e7b8960b7f806437b2fc91ae0f8e7ceedd6d132c6a07a5728491987f3c` |
| deposit-challenger | FINALIZED | SUCCESS/return | agree=4, idle=1 | `0x11de8cd43870b6d867c061148c62026718b0f765290b60622f66606c644ead72` |
| a-assert-true-unchallenged | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0x5d06eb1e010329c79598f9ce4e3fb1dc2cdef92cfe6d89742d9db2526138a6dd` |
| a-finalize-unchallenged | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0x7e7ef28fe87f011991c605c816fde8b3f4b0f355c02ba4185f91d2e19d59800e` |
| C-000002-assert | FINALIZED | SUCCESS/return | agree=4, idle=1 | `0x7d6ef7d5b6791bba3b195c0a4cfdfabe5a96040a62bf9423beda73ffc5f00428` |
| C-000002-challenge | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0x3f432069ee76c7b71bc4363f03756de11a98f75b2053a5340f351e76b8eea09b` |
| C-000002-adjudicate | FINALIZED | SUCCESS/return | agree=3, disagree=1, idle=1 | `0x688502f0ef5512244fa7f4922f93de91fc05b822da67a6b0d17a70521e6ce467` |
| C-000002-finalize | FINALIZED | SUCCESS/return | agree=4, idle=1 | `0xa7c9684e2a4958228014f85aa0cd23f60b4a0c1063531e5d1eb84e576e7f54b1` |
| C-000003-assert | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0x2d92ae851982517d7da8445589ba2c50988ab245198436d8ba56b1186867379c` |
| C-000003-challenge | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0xa85cdbf66c624e6432b06bcd60fd194fbd82fb6a062a547c2db2e54f7bfc27ad` |
| C-000003-adjudicate | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0x64714200430d26d74e8fd4b354ac24026fa820966d1f1581fd5919b49e0917d1` |
| C-000003-finalize | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0xc6df9b659ebb635d40711e140000c180db56d1c7150eb625453748eddb1e11f7` |
| d-assert-for-late-challenge | FINALIZED | SUCCESS/return | agree=4, idle=1 | `0xf48ba043395c42911cd98626d73f4679b00026acbd8e6e08620183d322431869` |
| d-EXPECTED-FAILURE-late-challenge | FINALIZED | ERROR/rollback | agree=4, idle=1 | `0x0bc9e060bf03b71bf6dbe5cec4910cca672567a1c04d2babe3549f680cf9e30c` |
| d-finalize-after-rejected-challenge | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0x89969b6dd898e2d0d60671f9cd10a0cd66bf4e9b9ea41ea10dbf0626af52d762` |
| e-first-withdrawal | FINALIZED | SUCCESS/return | agree=3, idle=2 | `0x7db832387075e8aa065229060867809abedd26560de7dba19c8e9a00c143343c` |
| e-EXPECTED-FAILURE-second-withdrawal | FINALIZED | ERROR/rollback | agree=3, idle=2 | `0x8df4dcfb09f2df218d245bf8ccf998df9561ee4e788b87c1cc84acfe515a3593` |

## Fixture evidence

- [unchallenged.txt](https://raw.githubusercontent.com/JWattjr/genlayer-demo-evidence/9e2be4687ce6e52865e2dc387655764aa97dfb8c/optimistic-assertion-court/unchallenged.txt): curl HTTP 200, 266 raw bytes; SHA-256 `44afd9721f066a35fc71bffdc8ab23065aa39f0f7b60fe8545b53a0ae3a4d27a`.
- [false-assertion.txt](https://raw.githubusercontent.com/JWattjr/genlayer-demo-evidence/9e2be4687ce6e52865e2dc387655764aa97dfb8c/optimistic-assertion-court/false-assertion.txt): curl HTTP 200, 266 raw bytes; SHA-256 `5c60a04191c6568babff5170e7f5f53137e952cf5362b26e16ae8b8b4b6f9148`.
- [frivolous-challenge.txt](https://raw.githubusercontent.com/JWattjr/genlayer-demo-evidence/9e2be4687ce6e52865e2dc387655764aa97dfb8c/optimistic-assertion-court/frivolous-challenge.txt): curl HTTP 200, 266 raw bytes; SHA-256 `4d534906608e748ef5588ea2b1dbacc481d604234d6747f0f33244491b80a163`.

Both live judgment digests match the curl downloads, and their stored citations are exact substrings.

## Limits

- Synthetic permissionlessly minted units; no real asset custody or economic deterrence.
- All three demo actors are controlled by the release operator; no economic independence or Sybil resistance is proved.
- Model error, shared model bias and prompt injection remain possible; unchallenged acceptance is not verified truth.
- Direct commit-pinned HTTPS fixture responses were checked; arbitrary DNS/redirect behavior is not exhaustively proved.
- Appeal, stale refund, UNDETERMINED and evidence-failure paths passed local tests; they were not exercised live in this demo.
- Distinctiveness is against the five named local implementations, not the whole ecosystem.

## Release boundary

The contract repository stays PRIVATE. Its single final push includes the reviewed source commit
and the later evidence/docs commit. The remote history and source blob are checked after push;
the local check result is retained in artifacts/remote-release-verification.json and reported
in the final operator response. No credentials were printed or committed. No Portal submission
was made. The public evidence repository contains the three fictional .txt files only.

## Live appeal supplement — 2026-10-20

This supplement uses the existing deployment and the original three test accounts. No contract
source changed and no redeployment occurred. The on-chain source remains identical to commit
`3b0ce9c68628538431942bc6d8db00773ab716cf`, blob `f90a574586da2012fd5206161835bb04b4a00dc7`.

B=10. The asserter was funded with 40 synthetic units before posting the new FALSE claim.
The original 18 transaction entries, 18 read-backs, their receipt objects and original final
history remain unchanged. Eight transactions are appended, five successes and three expected
rollbacks. All eight reached FINALIZED, with execution and votes recorded separately.

### Timing and read-back policy

The deployed appeal window is frozen at 60 seconds. Steps c/d/e/f used ACCEPTED-state
LATEST_NONFINAL read-backs so protocol finality waits could not consume the entire window.
Each execution was checked before continuing. Their FINALIZED receipts were subsequently
collected and the final claim and full accounting were re-read at LATEST_FINAL. This is
explicitly recorded; ACCEPTED observations are not presented as finality. No write was retried.

The valid appeal's recorded timestamp precedes its frozen deadline by 6.289 seconds.

| Step | ACCEPTED observed | FINALIZED | Leader execution/code | Votes | Explorer |
|---|---|---|---|---|---|
| Funding | YES | YES | SUCCESS/return | agree=4, idle=1 | [`0x49d4f69f39…`](https://explorer-studio.genlayer.com/tx/0x49d4f69f39b821ceedbd55478bb1e528f61387ef3e922c66acd7f1f5a63230e6) |
| a. Assert FALSE | YES | YES | SUCCESS/return | agree=5 | [`0x876f9b4095…`](https://explorer-studio.genlayer.com/tx/0x876f9b409515565dbd121f4c3f7b2acdf970170fa6beb6cd3a670caba18dc993) |
| b. Challenge B | YES | YES | SUCCESS/return | agree=4, idle=1 | [`0x6fdc2a4f7d…`](https://explorer-studio.genlayer.com/tx/0x6fdc2a4f7da0c2597223c66be7d79956a429abc5f066b68fc48a2957c602646f) |
| c. Adjudicate FALSE | YES | YES | SUCCESS/return | agree=3, idle=2 | [`0x8bf578156f…`](https://explorer-studio.genlayer.com/tx/0x8bf578156f5ae58090c111afbbf2eb9d2d833e04c4b3c2369858170ce1b7edb3) |
| d. Winner appeal rejected | YES | YES | ERROR/rollback | agree=3, idle=2 | [`0x70fac984eb…`](https://explorer-studio.genlayer.com/tx/0x70fac984eba0dd615f4c6b414afe57767ce210eac9e6d80b8326a46f451eb8fa) |
| e. Wrong bond rejected | YES | YES | ERROR/rollback | agree=3, idle=2 | [`0xe986bafb1d…`](https://explorer-studio.genlayer.com/tx/0xe986bafb1dc6814067b9c17e9b9716a83a4f3c341fb0010a1ee1e4732d2aec56) |
| f. Loser appeal confirms FALSE | YES | YES | SUCCESS/return | agree=3, idle=2 | [`0xb0577b9dd6…`](https://explorer-studio.genlayer.com/tx/0xb0577b9dd6df2efc8c5491106b007038abafe4b2d15502cf1509c497ed5d63ae) |
| g. Second appeal rejected | YES | YES | ERROR/rollback | agree=5 | [`0x034330a78e…`](https://explorer-studio.genlayer.com/tx/0x034330a78ee855a2898dc77d0586a48a247d0f6c929cff227cee051c37f79bc0) |

### Final claim read-back

```json
{
  "appeal_bond_units": 20,
  "appeal_deadline": "2026-10-20T06:50:33.332574+00:00",
  "appeal_used": true,
  "appealed_at": "2026-10-20T06:50:27.043355+00:00",
  "appellant": "0xdb433ff614bdd1ece21aa97221c3e0a7ecf79c92",
  "asserted_at": "2026-10-20T06:47:25.568784+00:00",
  "asserter": "0xdb433ff614bdd1ece21aa97221c3e0a7ecf79c92",
  "bond_units": 10,
  "challenge_deadline": "2026-10-20T06:49:25.568784+00:00",
  "challenged_at": "2026-10-20T06:48:09.280139+00:00",
  "challenger": "0x331f7c1f71cab3bdb0cdb59a6f66b658acb0de00",
  "claim_id": "C-000005",
  "claim_text": "The certified length of the fictional Raven Bridge is exactly 200 metres.",
  "escrow_units": 0,
  "evidence_url": "https://raw.githubusercontent.com/JWattjr/genlayer-demo-evidence/24cf4f229fc811b65df86f0c9593dccde2cd35a9/optimistic-assertion-court/appeal-raven-bridge.txt",
  "final_result": {
    "available": true,
    "cited_text": "The certified length of the fictional Raven Bridge is exactly 100 metres.",
    "evidence_digest": "sha256:5f23d4ac8c9a36d96a5c7e5ae0e962a59c75b2892146c8a328912fed852d4c18",
    "verdict": "FALSE"
  },
  "final_winner": "0x331f7c1f71cab3bdb0cdb59a6f66b658acb0de00",
  "first_result": {
    "available": true,
    "cited_text": "The certified length of the fictional Raven Bridge is exactly 100 metres.",
    "evidence_digest": "sha256:5f23d4ac8c9a36d96a5c7e5ae0e962a59c75b2892146c8a328912fed852d4c18",
    "verdict": "FALSE"
  },
  "judged_at": "2026-10-20T06:49:33.332574+00:00",
  "provisional_winner": "0x331f7c1f71cab3bdb0cdb59a6f66b658acb0de00",
  "settled_units": 40,
  "settlement_count": 1,
  "stale_deadline": "2026-10-20T07:18:09.280139+00:00",
  "status": "FINAL",
  "terminal_at": "2026-10-20T06:50:27.043355+00:00",
  "verdict": "FALSE",
  "void_reason": ""
}
```

### Accounting

```json
{
  "available_total": 140,
  "conserved": true,
  "locked_total": 0,
  "paid_out": 100,
  "total_deposited": 240
}
```

Funded baseline: asserter=40, challenger=100. Final: asserter=10, challenger=130.
The asserter's net is -30 (-3B); the challenger receives the 40-unit (4B) pot and nets +30.
Claim escrow and total locked units are zero, and settlement_count is exactly one. The three
rejected appeal attempts left claim/accounting state unchanged. Earlier claims are unchanged.

### Appeal fixture

[optimistic-assertion-court/appeal-raven-bridge.txt](https://raw.githubusercontent.com/JWattjr/genlayer-demo-evidence/24cf4f229fc811b65df86f0c9593dccde2cd35a9/optimistic-assertion-court/appeal-raven-bridge.txt): curl HTTP 200; 313 raw bytes;
SHA-256 `5f23d4ac8c9a36d96a5c7e5ae0e962a59c75b2892146c8a328912fed852d4c18`. The direct sentence has 73 characters and 12 words.
Both judgments' digests match the curl body. The appeal's exact citation meets the stricter
24-character/four-word rule.

This live appeal supersedes the original report's local-only appeal limitation. Stale refunds,
UNDETERMINED and unavailable-evidence outcomes remain local-test evidence. Units are synthetic;
model risk remains. The repository stays PRIVATE and nothing was submitted to the Portal.

# Optimistic Assertion Court

Phase 2 implementation specification, updated 2026-10-20 after approval.
This revision incorporates verified leader citations and permissionless stale
dispute refunds. Phase 2 ends with local checks and commits; no deployment,
repository creation, push or key retrieval is authorized in this phase.

Network target: GenLayer StudioNet only.

Runner header:

```text
# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
```

## 1. One-sentence mechanism

An assertion is accepted after an unchallenged window; semantic consensus runs
only when a matched-bond challenger disputes it. The ledger locks the initial
bond when the claim is posted, before any dispute.

The court is an optimistic assertion primitive:

1. An asserter freezes a bounded natural-language claim, one public HTTPS
   evidence URL, and a bond.
2. A challenge window runs. If nobody challenges, `finalize` accepts the claim
   with no web fetch and no LLM call, and refunds the bond.
3. A challenge must match the asserter's bond and must arrive before the window
   closes. The claim moves to `DISPUTED`.
4. After the window closes, anyone may call `adjudicate`. Validators fetch the
   complete evidence body and independently judge `TRUE`, `FALSE`, or
   `UNDETERMINED` against the frozen claim text. The validator compares verdict, evidence digest and availability exactly,
   then verifies the leader's citation against independently fetched evidence
   and its own model. The leader's verified citation is stored.
5. Deterministic code maps the verdict to the bond ledger. The model never
   chooses an amount or a recipient.
6. The loser may appeal once, within a frozen window, by posting twice the
   original bond. A fresh adjudication runs under a stricter citation rubric.
   Its result is final and is settled by a fixed formula.
7. Every challenged claim has an absolute stale deadline. At or after it,
   anyone can call `void_stale` to refund still-locked bonds without any
   evidence fetch or model call.

This inverts the usual pattern in the portfolio: the intelligent contract is
not invoked to make every decision. It is invoked only to resolve an economic
dispute.

## 2. Why GenLayer is necessary

The disputed question is whether a public document supports or refutes a
bounded natural-language claim. Deterministic code can validate URL shape,
timestamps, bond arithmetic, state transitions, and byte hashes, but it cannot
read the document and decide whether it establishes the claim.

The court keeps that semantic judgment inside validator consensus, but only on
the dispute path. The unchallenged path is pure deterministic code. That is the
mechanism: optimistic finality plus a conditional consensus court.

Here, "no consensus call" means no application call to a nondeterministic
judgment, web fetch, or LLM. All writes still execute through the GenLayer
protocol. Court status `ACCEPTED` is separate from transaction status `ACCEPTED`
or `FINALIZED`; neither a court label nor a successful leader execution alone
establishes protocol finality. Silence is acceptance under this mechanism, not
independent verification that the assertion is true.

The UI/client owns transaction submission, views, timers and evidence previews.
The contract owns frozen inputs, deadlines, judgments and settlement. A source
publisher owns the document bytes; fetching them does not authenticate the
publisher or establish facts beyond what the document supports.

## 3. Participants and permissions

| Participant | What they can do | What they cannot do |
|---|---|---|
| Asserter | Deposit synthetic units, post one claim with one evidence URL and a bond, finalize an unchallenged claim, appeal once if the first determinate judgment goes against them. | Challenge their own claim, withdraw a locked bond, appeal twice, act after a terminal state. |
| Challenger | Deposit synthetic units, match the asserter's bond before the challenge window closes, appeal once if the first determinate judgment goes against them. | Challenge with a different bond, challenge after the window, challenge their own claim, act after a terminal state. |
| Any address | Deposit and withdraw its own synthetic balance, call `adjudicate` after a dispute's window closes, call `finalize` after a window closes, call `void_stale` on a stale unsettled dispute, read every view. | Adjudicate before the challenge window closes, finalize early, force a second adjudication outside `appeal`, withdraw another address's balance. |
| GenLayer validators | Independently fetch the frozen evidence URL, independently prompt the model, compare verdict/digest/availability exactly, and independently verify the leader citation. | Choose payout amounts, recipients, deadlines, or accounting. |
| Deployer | Freeze the court title and all three duration settings in the constructor. | Pause, upgrade, seize bonds, change deadlines, or override a verdict. There is no admin role after deployment. |

Every write is permissionless except for the checks above. In particular, the
asserter does not have to be the one who finalizes, adjudicates, or triggers
settlement. Any address may advance a claim once the corresponding window has
closed.

## 4. Frozen configuration and bounds

Constructor:

```python
def __init__(court_title: str, challenge_window_seconds: int,
             appeal_window_seconds: int, dispute_deadline_seconds: int)
```

- `court_title`: normalized text, 1-120 characters. Audit label only.
- `challenge_window_seconds`: integer, 60-2,592,000 seconds (60 seconds to 30
  days). Frozen for the lifetime of the contract. Every claim's challenge
  deadline is `asserted_at + challenge_window_seconds`.
- `appeal_window_seconds`: integer, 60-2,592,000 seconds. Frozen. Every
  determinate first judgment creates an appeal deadline of `min(judged_at + appeal_window_seconds, stale_deadline)`.
- `dispute_deadline_seconds`: integer, at most 7,776,000 seconds (90 days),
  and at least `challenge_window_seconds + appeal_window_seconds + 60`.
  Frozen for the lifetime of the contract. A successful challenge sets
  `stale_deadline = challenged_at + dispute_deadline_seconds` exactly once.
- A boolean is not accepted as an integer.
- The constructor mints no units and creates no claim.

Fixed bounds:

| Bound | Value | Purpose |
|---|---:|---|
| `MAX_CLAIMS` | 32 | Total claims per contract. |
| `MAX_ACCOUNTS` | 128 | Lifetime ledger addresses; never evict an account to bypass this cap. |
| `MAX_CLAIM_CHARS` | 800 | Frozen claim text, normalized whitespace, minimum 10 characters. |
| `MAX_CLAIM_BYTES` | 3,200 | Strict UTF-8 bound, checked before and after normalization. |
| `MAX_EVIDENCE_BYTES` | 15,000 | Complete evidence body only. Never classify a prefix. |
| `MAX_URL_CHARS` | 500 | One HTTPS URL per claim. |
| `MAX_BOND_UNITS` | 10^12 | Original assertion bond `B`; the challenge matches it. |
| `MAX_APPEAL_BOND_UNITS` | 2 x 10^12 | Exactly `2B`, including when `B` is maximal. |
| `MAX_CLAIM_ESCROW_UNITS` | 4 x 10^12 | Temporary `4B` pot during an appeal. |
| `MAX_DEPOSIT_UNITS` | 10^12 | Per deposit call. |
| `MAX_LEDGER_UNITS` | 10^18 | Cumulative deposits across the contract. |
| `MIN_CITED_CHARS` | 1 | Any determinate verdict requires an exact citation. |
| `MAX_CITED_CHARS` | 600 | Cited text upper bound. |
| `MAX_MODEL_RESPONSE_BYTES` | 4,096 | Bound raw model JSON text before parsing, or the serialized object when the SDK already decoded it. |
| `MIN_APPEAL_CITED_CHARS` | 24 | Appeal must cite a non-trivial exact passage. |
| `MAX_HISTORY` | 256 | Bounded list of decoded event objects. |
| `MAX_HISTORY_DETAIL` | 200 | Bounded detail string per event. |

All amounts are positive integer units; reject bool, zero, negative, fractional
and over-bound values before arithmetic. Compute in Python integers, check
bounds, then store amounts/counters as `u256`. A new account is registered only
by its first successful deposit; an existing account can still deposit,
withdraw and settle when the account cap is full. Every bond participant must
already have an account with sufficient available funds. Do not insert empty
accounts on reads or rejected operations. Account balances use `TreeMap` plus
a bounded address index; claims use `TreeMap[str, str]` canonical JSON plus a
bounded claim index, and history uses `DynArray[str]`.

All stored text must encode as strict UTF-8. Validate raw claim length before
normalizing whitespace so oversized whitespace cannot bypass the bound. URL
text is ASCII and is never silently rewritten; claim ID input is an exact
eight-character generated ID. No unbounded user metadata or model reasoning
is stored.

Claim IDs are deterministic: `C-000001`, `C-000002`, ... in creation order.
No user-supplied claim ID is accepted.

## 5. Claim record

Each claim is stored as one canonical JSON object under its claim ID. It
contains:

| Field | Meaning |
|---|---|
| `claim_id` | Deterministic ID. |
| `asserter` | Lowercase address text. |
| `claim_text` | Frozen normalized claim text. |
| `evidence_url` | Frozen HTTPS URL. |
| `bond_units` | Original bond `B`, posted by the asserter. |
| `status` | `OPEN`, `DISPUTED`, `PROVISIONAL`, `ACCEPTED`, `FINAL`, or `VOID`. |
| `asserted_at`, `challenge_deadline` | ISO-8601 UTC timestamps. |
| `challenger`, `challenged_at`, `stale_deadline` | Frozen on challenge; matched challenge bond is derived as `B`. |
| `judged_at`, `appeal_deadline` | First judgment timestamps, empty before adjudication. |
| `first_result` | Canonical first consensus result object, or `{}`. |
| `final_result` | Controlling result object after finality, or `{}`. |
| `verdict` | Controlling `TRUE`, `FALSE`, `UNDETERMINED`, or `""`. |
| `provisional_winner` | `asserter` or `challenger` after a determinate first judgment. |
| `appeal_used`, `appellant`, `appeal_bond_units`, `appealed_at` | Appeal audit fields. |
| `final_winner` | Settled winner, or `""`. |
| `escrow_units` | Units currently locked by this claim. |
| `settled_units` | Units released from escrow by this claim. |
| `settlement_count` | `0` before settlement; exactly `1` in a terminal state. |
| `terminal_at` | ISO timestamp when the claim became terminal. |
| `void_reason` | Empty, `UNDETERMINED`, `UNDETERMINED_APPEAL`, or `STALE_DISPUTE`. |

The two result objects are separately retained so an appeal cannot erase the
first judgment from the audit record.

## 6. State machine

```text
  assert_claim
       |
       v
     OPEN --------------------------------- finalize (>= deadline) ---> ACCEPTED
       |                                                               (B refunded)
       | challenge (< deadline, bond == B, not asserter)
       v
    DISPUTED
       |
       | adjudicate (>= challenge deadline; permissionless; once)
       |
       +---- UNDETERMINED / UNAVAILABLE ----> VOID
       |                                      (B refunded to each side)
       |
       +---- TRUE / FALSE ------------------> PROVISIONAL
                                                 |
                       +-------------------------+-------------------------+
                       |                                                   |
        finalize (>= appeal deadline, no appeal)          appeal (< deadline, loser, bond 2B, once)
                       |                                                   |
                       v                                                   v
                     FINAL                                               FINAL
                 (2B pot to W1)                        (4B to final winner)
                                                 or VOID on UNDETERMINED
                                                 (all three bonds refunded)

  DISPUTED or PROVISIONAL -- void_stale (>= stale_deadline) --> VOID
                                      (all locked contributions refunded)
```

State table:

| Status | Escrow for the claim | Allowed claim actions | Terminal |
|---|---:|---|---|
| `OPEN` | `B` | `challenge` before the deadline; `finalize` at or after it. | No |
| `DISPUTED` | `2B` | `adjudicate` at or after the challenge deadline and before staleness; `void_stale` at or after staleness. | No |
| `PROVISIONAL` | `2B` | Loser `appeal` before the appeal deadline; anyone `finalize` at or after it but before staleness; anyone `void_stale` at or after staleness. | No |
| `ACCEPTED` | `0` | None. Bond was refunded. | Yes |
| `FINAL` | `0` | None. Pot was released once. | Yes |
| `VOID` | `0` | None. Bonds were refunded. | Yes |

Transition rules:

1. `assert_claim` requires a positive bounded bond covered by the asserter's
   withdrawable balance. It locks the bond, computes the challenge deadline
   from the frozen window, and stores the claim with status `OPEN`.
2. `challenge` requires status `OPEN`, `now < challenge_deadline`, a sender
   different from the asserter, and a bond exactly equal to `B`. It locks the
   challenger's `B` and moves to `DISPUTED`.
3. `finalize` on `OPEN` requires `now >= challenge_deadline` and no challenge.
   It moves to `ACCEPTED` and refunds `B` to the asserter with no consensus
   call.
4. `adjudicate` requires status `DISPUTED` and `now >= challenge_deadline`. It
   also requires `now < stale_deadline` and runs one successful consensus judgment:
   - `TRUE` or `FALSE` moves to `PROVISIONAL`. The determinate winner is the
     provisional winner. The appeal deadline is set to
     `min(now + appeal_window_seconds, stale_deadline)`. Escrow stays at `2B`.
   - `UNDETERMINED` or unavailable evidence moves directly to `VOID`. Both
     bonds are refunded. There is no loser and no appeal.
5. `appeal` requires status `PROVISIONAL`, `now < appeal_deadline`, the sender
   is the provisional loser, `now < stale_deadline`, `appeal_used == false`, and a bond exactly equal
   to `2B`. It locks the appeal bond and runs one fresh consensus judgment
   under the stricter rubric.
   - A determinate appeal moves to `FINAL` and settles `4B` in one transfer.
   - An undetermined or unavailable appeal moves to `VOID` and refunds all
     three bonds.
   - There is no second appeal.
6. `finalize` on `PROVISIONAL` requires `appeal_deadline <= now < stale_deadline` and no
   appeal. It moves to `FINAL` and releases the `2B` pot to the provisional
   winner.
7. `void_stale` requires `DISPUTED` or `PROVISIONAL` and
   `now >= stale_deadline`. It moves to `VOID`, records `STALE_DISPUTE` and
   refunds every currently locked contribution. Neither web nor LLM nor a
   nondeterministic closure runs. At this boundary, adjudication, appeal and
   provisional award finalization are rejected, so callers cannot race the
   refund by choosing a different entrypoint. An `OPEN` claim still follows
   normal unchallenged finalization. Already terminal claims cannot be voided.
8. Any claim action on a terminal status reverts. A second adjudication, a
   second challenge, or a second appeal reverts.
9. `deposit_units` and `withdraw_units` are not claim actions. They remain
   available after a claim is terminal and never touch locked funds.

Timing uses the transaction's ISO-8601 block time in UTC. "Before" is strict
(`now < deadline`); "at or after" is inclusive (`now >= deadline`). A challenge
submitted exactly at the deadline reverts. An appeal submitted exactly at the
appeal deadline reverts.

Expiry alone does not send a transaction or change storage. Deadlines are
computed once from the consensus-visible transaction time, never from a caller
argument or local wall clock. `adjudicate` deliberately waits until the original
challenge deadline even when a challenge was posted early. An appeal performs
its second judgment and settlement atomically; no externally visible
`APPEAL_PENDING` state is needed. A failed appeal transaction restores the
prior state and does not consume the one appeal; one *successful* appeal is the
limit, and a retry still must be before the original appeal deadline and before staleness.

## 7. Evidence rules

The claim freezes exactly one evidence URL. At assertion time the contract
validates its shape:

- Starts with `https://`, maximum 500 characters, no whitespace.
- No userinfo (`@`), no backslash, no non-default port.
- Public hostname or public IPv4 address. Reject `localhost`, `.local`,
  `.internal`, `.localhost`, loopback, private, link-local, carrier-grade NAT,
  documentation, multicast, and reserved ranges.
- Host labels must be non-empty, at most 63 characters, ASCII alphanumeric or
  hyphen, and must not start or end with a hyphen.
- Exactly one URL. Duplicate or multiple URLs are not supported.

Reject fragments, control characters, encoded authority tricks, non-ASCII
hostnames and IPv6 literals in this bounded version. Query strings and paths
are permitted, but the whole input must parse as one URL. A visible 3xx response is unavailable. The pinned SDK's `web.get`
has no redirect-control parameter; runtime redirect behavior is not proven in
Phase 2 and must be reviewed before a live release. Do not follow links, extract HTML,
execute JavaScript, or fetch a second document. Lexical URL checks alone cannot
prove that a DNS name resolves publicly; use the runtime's public-network
restrictions and verify its redirect/response-body behavior in Phase 2.

Reachability is not checked at assertion time. It is judged only during
consensus. At adjudication and appeal the frozen URL is fetched inside the
nondeterministic closure. Evidence is `AVAILABLE` only when all of the following
hold:

1. The fetch returns HTTP 200.
2. The body is a non-empty byte sequence.
3. `len(body) <= 15,000` bytes. A larger body is UNAVAILABLE, not truncated.
4. The complete body decodes as strict UTF-8.
5. The decoded body contains at least one non-whitespace character.

A transport failure, timeout, or known incomplete/truncated response is also
unavailable. Never use a fetch option that silently returns only the first
15,000 bytes. Request identity content encoding where supported and do not
classify a partial or encoded body. The pinned SDK exposes `Response.body` without a prefix-length option;
the contract consumes that body in full, without slicing, and also rejects a
Content-Length mismatch or non-identity Content-Encoding. Local SDK inspection
and mocked boundaries do not prove network transport completeness; live review
must verify fetched bytes against the pinned fixture digest. The 15,000-byte bound applies before UTF-8 decoding, with no newline
normalization. No arbitrary VM/programming errors are converted into evidence
unavailability.

Otherwise the result is:

```json
{
  "available": false,
  "cited_text": "",
  "evidence_digest": "",
  "verdict": "UNDETERMINED"
}
```

No model call is made for unavailable evidence. Each participant independently
derives availability; all must compare the same four-field result to agree.
An outage seen only by the leader does not force a refund if a validator sees
available evidence: that is disagreement, so no court transition is committed.

For available evidence, `evidence_digest` is `sha256:<64 lowercase hex>` over
the complete raw body bytes. The model never supplies the digest; code computes
it. This means the digest binds the exact document version that was fetched,
and a mutable publisher URL can cause consensus to fail if validators observe
different bytes. Production evidence should use a pinned URL (for example, a
raw file addressed by commit SHA).

## 8. Consensus result and validator comparison

The model returns only:

```json
{"verdict": "TRUE|FALSE|UNDETERMINED", "cited_text": "..."}
```

Code enriches that into the canonical result with exactly four keys:

```json
{
  "available": true,
  "cited_text": "...",
  "evidence_digest": "sha256:...",
  "verdict": "TRUE|FALSE|UNDETERMINED"
}
```

Rules enforced in code:

- Unknown or missing keys are rejected.
- Duplicate JSON keys, invalid types and an oversized raw response are rejected;
  verdicts and citations must be strings, with no coercion.
- `available` must be a real boolean.
- `evidence_digest` must equal the SHA-256 of the fetched raw bytes.
- `verdict` must be one of the three values.
- `UNDETERMINED` must have an empty `cited_text`.
- `TRUE` and `FALSE` must have a non-empty `cited_text`.
- `cited_text` must be an exact contiguous substring of the decoded evidence
  body. No normalization, paraphrase, ellipsis, or case folding is accepted.
- `cited_text` is limited to 600 characters.
- The first adjudication requires at least 1 character of exact citation.
- The appeal requires at least 24 characters and at least four
  whitespace-separated tokens of exact citation. This is the code-enforced
  part of the stricter rubric.
- A malformed model result raises `[LLM_ERROR]`. The transaction reverts and
  no bond is settled.

The first-adjudication prompt asks for a short exact excerpt that supports or
refutes the claim. The appeal prompt is deliberately stricter: the excerpt must
be a direct, claim-level passage that, by itself, unambiguously establishes the
verdict; if no such passage exists, the model must answer `UNDETERMINED`. The
appeal prompt does not receive the first verdict, so it is a fresh reading
rather than an affirmation check.

Both prompts treat the claim and evidence as untrusted quoted data. Instructions
inside them must not change the rubric. `TRUE` requires affirmative support for
the whole claim; `FALSE` requires affirmative contradictory evidence. Silence,
missing context or uncertainty requires `UNDETERMINED`. A valid citation is a
necessary check, not proof of semantic correctness. The minimum appeal quote
length can make a very short document undetermined; this conservative outcome
refunds all posted bonds.

Validator comparison, for each successful leader result:

1. Validate the exact four-key schema, enums and types; reject leader errors.
2. Independently fetch the frozen URL. Compare `available` and
   `evidence_digest` exactly with the leader. Disagree if either differs.
3. If both independently find unavailable evidence, agree only on the canonical
   `UNDETERMINED`, empty-citation, empty-digest result; do not call the model.
4. For available evidence, independently classify the frozen claim. Compare
   `verdict` exactly. The validator's own chosen citation may differ.
5. Verify the leader's citation is an exact contiguous substring of the
   validator's own decoded body and meets this stage's length/token rules.
6. For TRUE/FALSE, ask the validator's own model whether that specific leader
   excerpt supports the leader verdict in the complete document context. Require
   exactly `{"supports": true}` with a real boolean. The appeal check also
   requires the passage alone to establish the verdict. False, malformed or
   failed verification disagrees. UNDETERMINED requires an empty citation and
   independent UNDETERMINED classification, without a supporting-excerpt call.
7. Store the leader result, including its verified citation; never substitute
   the independently selected quote. Revalidate the accepted schema before
   persistence. A different valid supporting citation is accepted; an invented,
   undersized or non-supporting one is rejected.

Use a custom `run_nondet_unsafe` callback, not a verdict-only comparison or
LLM strict-equality helper. The closures receive only frozen claim/URL and
stage, and mutate no storage. A disagreement commits no court transition.
Only a successful first adjudication or successful one-shot appeal counts;
the protocol may rerun a closure during consensus. Before the absolute stale
deadline a reverted transaction may be retried. At staleness, anyone can recover
the locked original bonds deterministically. No live judgment is authorized
in Phase 2.

The LLM never sees bond amounts, balances, recipients, or payout instructions.
It returns a factual classification only.

## 9. Deterministic settlement and appeal formula

Let `B` be the original claim bond. The challenger posts exactly `B`, so the
first-stage pot is `2B`. Let `W1` be the provisional winner and `L1` the
provisional loser. Let `Wf` be the final winner.

First adjudication:

| Verdict | Status after adjudicate | Escrow | Economic effect |
|---|---|---:|---|
| `TRUE` | `PROVISIONAL` | `2B` | Asserter is `W1`; pot remains locked pending appeal. |
| `FALSE` | `PROVISIONAL` | `2B` | Challenger is `W1`; pot remains locked pending appeal. |
| `UNDETERMINED` / unavailable | `VOID` | `0` | Asserter gets `B` back and challenger gets `B` back. |

The pot is not credited to a withdrawable balance at first adjudication. This is
deliberate: a one-shot appeal must be solvent without clawbacks. The first
judgment vests a provisional entitlement; `finalize` releases it only after the
appeal window closes. The claim's `verdict` is already `TRUE` or `FALSE`; only
the money is held.

Appeal:

- Only `L1` may appeal, only once, only before `appeal_deadline`.
- The appeal bond is exactly `2B`.
- The claim escrow during the appeal transaction is `2B + 2B = 4B`.
- A determinate appeal result decides `Wf`:
  - `TRUE` means the asserter is `Wf`.
  - `FALSE` means the challenger is `Wf`.
- The final winner receives all `4B` in one credit from locked escrow.
- The other party receives nothing from this claim.
- If the appeal result is `UNDETERMINED` or unavailable, the claim becomes
  `VOID`: the asserter gets `B`, the challenger gets `B`, and the appellant
  gets the `2B` appeal bond back.

No-appeal finalization:

- `finalize` at/after the appeal deadline but before staleness, with no appeal, moves
  `PROVISIONAL -> FINAL` and credits `2B` to `W1`.

Net effects of the appeal formula, relative to each party's total posted bonds:

| Path | Asserter net | Challenger net |
|---|---:|---:|
| First `TRUE`, no appeal, finalized | `+B` | `-B` |
| First `FALSE`, no appeal, finalized | `-B` | `+B` |
| First `TRUE`, challenger appeals, appeal `TRUE` | `+3B` | `-3B` |
| First `TRUE`, challenger appeals, appeal `FALSE` | `-B` | `+B` |
| First `FALSE`, asserter appeals, appeal `FALSE` | `-3B` | `+3B` |
| First `FALSE`, asserter appeals, appeal `TRUE` | `+B` | `-B` |
| First `UNDETERMINED` | `0` | `0` |
| Appeal `UNDETERMINED` | `0` | `0` |

Stale dispute refund:

Clear the controlling verdict and leave the final result empty; a stale refund
does not fabricate a second consensus finding. Retain the first result for audit.

- At `now >= stale_deadline`, `void_stale` refunds `B` to each side from a
  still-unsettled DISPUTED or PROVISIONAL claim and sets VOID, even if the first
  judgment was determinate. No winner is paid. A successful appeal already
  settles atomically, so no appeal bond remains locked in an unsettled state.
- This is one settlement of all locked contributions, not a clawback of a
  previously finalized award. The first result remains in the audit record.

There is no protocol fee, no partial slash, no discretionary amount, and no
owner override. Exactly one of these formulas executes for a claim, once.

The appeal bond is intentionally punitive for a frivolous appeal: a losing
appellant forfeits its original bond plus the `2B` appeal bond, while the
provisional winner receives `4B`. A successful appellant recovers the pot but
does not profit beyond winning the original dispute.

## 10. Accounting

The contract is a closed synthetic deposit ledger. It does not custody or
transfer GEN, stablecoins, or any external asset. Deposits are demonstration
units.

Cumulative categories:

- `D` = total synthetic units deposited.
- `A` = total withdrawable account balances.
- `L` = total units locked in claim escrow.
- `P` = cumulative units withdrawn (paid out of the ledger).

Invariant:

```text
D == A + L + P
D >= 0, A >= 0, L >= 0, P >= 0
A = D - L - P
```

Every write is a transfer between categories:

| Operation | `D` | `A` | `L` | `P` |
|---|---:|---:|---:|---:|
| `deposit_units(x)` | `+x` | `+x` | | |
| lock a bond `x` | | `-x` | `+x` | |
| refund/release `x` from escrow | | `+x` | `-x` | |
| `withdraw_units(x)` | | `-x` | | `+x` |

Claim escrow must equal exactly:

| Status | Escrow |
|---|---:|
| `OPEN` | `B` |
| `DISPUTED` | `2B` |
| `PROVISIONAL` | `2B` |
| `ACCEPTED`, `FINAL`, `VOID` | `0` |

The appeal path temporarily creates `4B` of escrow inside one transaction; on
success it resolves to `0`, and on revert the whole transaction leaves the
pre-call `2B` state unchanged.

`_assert_invariant()` runs after every write. It recomputes the locked total
from the bounded claim set and checks:

1. The stored cumulative categories satisfy `D == A + L + P`.
   Independently sum all bounded account balances and require that sum to equal
   `A`; counters alone cannot prove that individual balances conserve units.
2. The recomputed claim escrow equals the stored locked total.
3. Every claim's escrow matches its status formula.
4. No bond, refund, release, or withdrawal exceeds the available balance or
   claim escrow.
5. Cumulative deposits stay within `MAX_LEDGER_UNITS`.
6. Each terminal claim has `settlement_count == 1`, zero escrow and
   `settled_units == B`, `2B` or `4B` for its path. Each nonterminal claim has
   `settlement_count == 0` and zero settled units. Increment the count only in
   the single settlement helper, which rejects a second settlement.

A failure raises `[INVARIANT]` and reverts the transaction. Because all writes
are transactional, a consensus failure, a malformed model result, an invalid
state transition, or an accounting failure leaves no partial settlement.

`withdraw_units` debits the sender's balance before crediting `P`. A second
withdrawal of already withdrawn units therefore has insufficient balance and
reverts. Locked funds cannot be withdrawn.

`P` counts withdrawals only; a settlement is a credit to `A`, not also a credit
to `P`. A later withdrawal after a new deposit or new settlement is legitimate;
the prohibited second withdrawal is reuse of an already consumed balance.
Deposits are permissionless demo minting, bounded by per-call and cumulative
caps, so the bonds impose only a synthetic ledger cost. They do not create a
real financial deterrent or Sybil resistance. There are no external transfers
or callbacks on settlement or withdrawal.

## 11. History

`_record(claim_id, action, detail)` appends one canonical JSON string:

```json
{"seq":1,"claim_id":"C-000001","action":"CHALLENGE","at":"...","detail":"..."}
```

Allowed actions are `ASSERT`, `CHALLENGE`, `ADJUDICATE`, `APPEAL`, and
`FINALIZE` and `VOID_STALE`. `detail` is bounded to 200 characters. History is capped at 256
records. Since claims are capped at 32 and each claim has at most six events,
the cap is not reachable through normal operation; if it is somehow reached,
the write reverts with `[LIMIT]`.

Deposits and withdrawals are not claim history. They are reflected in
`get_accounting()` and the caller's balance.

## 12. API

Writes:

| Method | Purpose |
|---|---|
| `deposit_units(amount: u256) -> None` | Credit the sender's synthetic balance. |
| `withdraw_units(amount: u256) -> None` | Debit the sender's available balance into paid-out units. |
| `assert_claim(claim_text: str, evidence_url: str, bond: u256) -> dict` | Create an `OPEN` claim and lock the bond. |
| `challenge(claim_id: str, bond: u256) -> dict` | Match the bond before the challenge deadline; move to `DISPUTED`. |
| `adjudicate(claim_id: str) -> dict` | Permissionless first consensus judgment after the challenge window closes. |
| `appeal(claim_id: str, bond: u256) -> dict` | Loser's one-time appeal with `2B`, before the appeal deadline. |
| `void_stale(claim_id: str) -> dict` | Refund a stale DISPUTED/PROVISIONAL claim without inference. |
| `finalize(claim_id: str) -> dict` | Accept an unchallenged claim or release a provisional award after the appeal window. |

Views:

| Method | Purpose |
|---|---|
| `get_config() -> dict` | Court title, frozen windows, fixed bounds, claim count, total deposited. |
| `get_claim(claim_id: str) -> dict` | Full claim record, including both result JSONs and escrow. |
| `get_balance(account: Address) -> int` | Withdrawable synthetic balance. |
| `get_accounting() -> dict` | `total_deposited`, `available_total`, `locked_total`, `paid_out`, `conserved`. |
| `get_history() -> list` | Bounded list of decoded event objects. |

## 13. Failure behavior

| Condition | Result |
|---|---|
| Challenge after the window | Revert `[EXPECTED] challenge window has closed`. |
| Challenge with the wrong bond | Revert `[EXPECTED] challenge bond must equal the asserter bond`. |
| Challenge by the asserter | Revert `[EXPECTED] asserter may not challenge its own claim`. |
| Adjudicate before the window closes | Revert `[EXPECTED] challenge window has not closed`. |
| Adjudicate an `OPEN` claim | Revert `[EXPECTED] claim is not disputed`. |
| Appeal by the winner | Revert `[EXPECTED] only the provisional loser may appeal`. |
| Appeal after the appeal deadline | Revert `[EXPECTED] appeal window has closed`. |
| Appeal with the wrong bond | Revert `[EXPECTED] appeal bond must equal twice the original bond`. |
| Second appeal / second adjudication | Revert `[EXPECTED] claim state does not allow this action`. |
| Evidence non-200, empty, oversized, or invalid UTF-8 | Consensus result `UNDETERMINED`, `available=false`; claim `VOID`; both bonds refunded. |
| Malformed model JSON, bad verdict, bad citation | Revert `[LLM_ERROR]`; no settlement. |
| Validator disagrees on verdict/digest/availability or cannot verify the leader citation | Consensus fails; transaction reverts; no settlement. |
| Insufficient available balance | Revert `[EXPECTED] insufficient available balance`. |
| Withdraw more than the available balance, or withdraw twice | Revert `[EXPECTED] insufficient available balance`. |
| Any claim action after a terminal state | Revert `[EXPECTED] claim is already terminal`. |
| `void_stale` before the absolute dispute deadline | Revert; state and accounting unchanged. |
| Adjudicate/appeal/finalize provisional award at or after staleness | Revert; caller must use `void_stale`. |
| Stale DISPUTED/PROVISIONAL claim, `void_stale` by any caller | VOID; all locked contributions refunded once, no web/LLM. |
| Accounting invariant failure | Revert `[INVARIANT]`. |

No state-changing method has a fallback that pays on an invalid or disputed
result. The court fails closed.

## 14. Distinctiveness against the named accepted contracts

The comparison set is Source-Conflict Kernel, Readiness Gate, Delegated
Handoff, Spec-Bid Auction, and Token Gate. This is a local source review, not
an ecosystem-wide originality claim.

| Accepted comparator | When its judgment runs | Participants and actions | Economic layer | Difference from this court |
|---|---|---|---|---|
| **Source-Conflict Kernel** | A nonterminal `resolve` after the frozen deadline classifies sources and derives `YES`/`NO`/`CONTESTED`/`UNAVAILABLE`/`INCONCLUSIVE`; a resolved read-back is idempotent. | A deployer freezes 2-8 sources and a claim; any caller resolves. | None. | This court accepts an unchallenged claim without evidence judgment. Only a matched-bond challenge enables the first semantic consensus, followed by a possible loser-funded appeal. |
| **Readiness Gate** | `assess` invokes consensus in its active assessment interval. Pre-cutoff WAIT, max-wait VOID, and valid cached/consumed readiness have deterministic paths. | An owner freezes criteria, sources and deadlines, then binds a consumer; that consumer may consume READY. | None. | Its conditional judgment is gated by time and readiness lifecycle, with no economic dispute. This court's unchallenged acceptance releases a bond, and only a matched challenger opens semantic judgment. |
| **Delegated Handoff** | At every handoff proposal; a scope judgment is required before budget is reserved. | An assignment owner proposes a child scope to a named recipient; recipient accepts; optional principal approves. | Synthetic budget reservations, but no bonds, challenge, or slashing. | This court has no parent/child assignment tree and no consent workflow. Its reservation is an adversarial bond, and the scope of the judgment is one frozen claim versus one evidence URL, not containment inside a parent task. |
| **Spec-Bid Auction** | `resolve_auction` assesses every revealed bid before price selection; zero valid reveals produces deterministic NO_AWARD. | Suppliers commit and reveal sealed bids with evidence; the selected supplier accepts the reserved award. | Synthetic price competition and reservation, but no challenger bond, challenge window, or appeal. | The auction's semantic path is triggered by revealed offers. This court judges one factual claim only after a matched-bond dispute and permits the loser to fund one stricter re-judgment. |
| **Token Gate** | Active `review` invokes consensus; active issuer disclosure invokes a second rubric. Terminal/deadline handling has deterministic paths. | A deployer freezes token claims and sources; the issuer alone may submit disclosures. | None. | Its second judgment answers a frozen disclosure agenda, not a paid adversarial challenge. This court has matched bonds, a provisional award and a one-shot loser appeal. |

None of the five reviewed implementations makes semantic consensus conditional
on an economic dispute. Some already avoid inference on deterministic timeout
or cached-result paths; avoiding inference alone is therefore not the
distinctiveness claim. The mechanism here combines these four properties:

1. **Conditional consensus.** The fast path has no web fetch and no LLM call.
   Consensus exists only because a second economic actor disputed the claim.
2. **Matched-bond gate.** A challenge is not a free comment; it must exactly
   match the asserter's bond before the deadline.
3. **One-shot loser-funded appeal.** The losing party, not the winner or an
   admin, decides whether a second, stricter judgment happens. The appeal bond
   is `2B`, so frivolous appeals are expensive, and the result is final.
4. **Verdict-to-ledger code.** The model returns only verdict and exact
   citation. Code computes the evidence digest, validates the citation against
   the fetched body, verifies the leader citation, and maps the verdict to a fixed
   bond formula. The model never names a payout, amount, or recipient.

### Source review evidence

These local implementation files, rather than names alone, support the table.
The review establishes the local mechanism comparison; it does not independently
revalidate Portal acceptance or deployed releases.

| Comparator | Local source | Relevant methods and inspected lines |
|---|---|---|
| Source-Conflict Kernel | `C:/Users/User/Desktop/Intelligent Contracts/standalone/source-conflict-resolution-kernel/contracts/SourceConflictKernel.py` | `_consensus_candidate` at 167; `resolve` at 263; semantic call at 270. |
| Readiness Gate | `C:/Users/User/Desktop/Intelligent Contracts/standalone/resolution-readiness-gate/contracts/ResolutionReadinessGate.py` | `assess` at 525; deterministic branches at 534-539; semantic call at 541. |
| Delegated Handoff | `C:/Users/User/Desktop/Genlayer apps/intelligent-contracts-v2/delegated-task-handoff/contracts/delegated_task_handoff.py` | `propose_handoff` at 350; scope judgment at 386; reservation at 407-411. |
| Spec-Bid Auction | `C:/Users/User/Desktop/Genlayer apps/intelligent-contracts-v2/specification-bid-auction/contracts/specification_bid_auction.py` | `resolve_auction` at 496; no-reveal branch at 507; assessment at 517; supplier-only acceptance at 562-566. |
| Token Gate | `C:/Users/User/Desktop/Intelligent Contracts/standalone/token-claim-capability-gate/contracts/token_claim_capability_gate.py` | `review` at 463; terminal branch at 467; `_consensus_review` at 471; `submit_disclosure` at 483 and `_consensus_disclosure` at 499. |

**Disposition: KEEP.** The distinctive state transition is `OPEN -> ACCEPTED`
by silence, with consensus reachable only through `OPEN -> DISPUTED ->
PROVISIONAL -> FINAL/VOID` and an economic loser who must pay `2B` to reopen
the question.

## 15. Limits and non-goals

- Bond units and deposits are synthetic demonstration units. There is no GEN,
  stablecoin, or external asset custody, transfer, or payment.
- This is not a legal court, arbitration service, or enforceable judgment.
- A public URL can change after assertion. The evidence digest binds what each
  validator fetched, but the contract cannot force a publisher to keep a page
  stable. Pinned URLs are recommended.
- The model can misread evidence. Validators independently re-fetch and
  re-prompt, but correlated model error remains possible. Ambiguity is supposed
  to produce `UNDETERMINED` and a `VOID` claim, not a forced binary answer.
- The court does not verify that a claim is meaningful, newsworthy, or
  economically valuable. It only judges the frozen text against the frozen
  evidence.
- Only one challenge and one appeal are allowed. A claim with no adjudication can be refunded by anyone at its frozen stale
  deadline. A caller must still submit the transaction; passage of time alone
  does not release units.
- Evidence must be a complete UTF-8 body of at most 15,000 bytes. PDFs, images,
  and larger documents generally fail this policy. There is no PDF/image parser
  or JavaScript renderer; the policy judges only the returned UTF-8 body, so a
  JavaScript shell may instead produce `UNDETERMINED` for insufficient content.
- Independent models may disagree on the verdict or citation support, and
  mutable evidence can change the digest. Such disagreement blocks judgment,
  but `void_stale` eventually permits a refund. Model confirmation is not proof
  against correlated error or prompt injection.
- Lifetime claim, account and cumulative-deposit caps can be exhausted. They
  bound this demonstration's storage; they are not a production spam solution.
- The contract is StudioNet-only for this release. No mainnet, Bradbury, or
  value-bearing deployment is claimed.

## 16. Phase 2 verification plan

The direct-mode suite will cover:

1. Unchallenged claim: assert, warp past the challenge window, `finalize`, and
   verify `ACCEPTED`, bond refund, and zero web/LLM mock invocations.
2. `TRUE` first judgment: assert, challenge, warp, adjudicate, verify the
   provisional winner, finalize after the appeal window, and verify both bonds
   credited once.
3. `FALSE` first judgment: the same path with the challenger as provisional
   winner.
4. `UNDETERMINED`: verify `VOID`, both bonds refunded, no appeal available.
5. Challenge after the window: expect revert and unchanged accounting.
6. Challenge with the wrong bond: expect revert and unchanged accounting.
7. Appeal once only: a valid appeal settles `4B`; a second appeal reverts.
8. Appeal with the wrong bond: expect revert.
9. Appeal flip: first `TRUE`, challenger appeals, appeal `FALSE`, verify the
   challenger receives `4B` and the asserter receives nothing.
10. Accounting invariant after every step: `D == A + L + P`, claim escrow by
    status, and no negative or double withdrawal.
11. Forged leader: same verdict with a forged non-substring or unsupported cited text, and
    the same verdict with a different digest, both rejected by `run_validator`, except that a different valid supporting
    citation is accepted under the approved verified-citation policy.
12. Evidence failures: non-200, empty, oversized (>15,000 bytes), and invalid
    UTF-8 all become `UNAVAILABLE -> UNDETERMINED -> VOID`, with both bonds
    refunded.
13. Terminal-state actions and a second withdrawal: expect revert.
14. Constructor and input bounds: bad windows, bad bonds, oversized claims,
    invalid URLs, and claim-count limits.
15. Maximum original bond permits an exact `2B` appeal and `4B` pot without
    overflow; deposits across multiple calls can fund the maximum appeal.
16. Bounded accounts/history, independent sum of balances, exactly-one
    settlement, failed-appeal rollback and exact deadline boundaries.
17. Availability mismatch and schema/type/duplicate-key forgeries are rejected;
    an agreed unavailable appeal refunds both original bonds plus the appeal
    bond. Exactly 15,000 valid UTF-8 bytes is accepted; 15,001 is unavailable.

18. Verified citation binding: a valid alternative quote is accepted and the
    stored leader citation is preserved; a non-substring, too-short, fewer than
    four appeal tokens, or non-supporting quote is rejected. Schema/key/type
    forgeries and model failures cannot authorize settlement.
19. Stale DISPUTED and PROVISIONAL claims: before the deadline revert; at the
    deadline refund all locked bonds exactly once by any caller with zero
    web/LLM/nondeterministic calls. A late judgment cannot extend the deadline.
    OPEN/terminal states cannot be voided, and staleness blocks other dispute
    resolution entrypoints.

Ordinary direct mode does not by itself prove validator agreement. Explicitly
exercise the validator callback for the forged-leader cases, confirm the pinned
test tool exposes that path, and label all web/LLM fixtures as mocks. No local
test result establishes live StudioNet execution or finality.

Lint must pass before the Phase 2 stop. Phase 3 live evidence will use pinned
`raw.githubusercontent.com` files with a commit SHA in the URL and will record
raw byte counts measured with `curl`.

## 17. Phase boundaries and release constraints

The current authorized work is Phase 2 only: implementation, direct-mode tests,
lint, `.gitattributes` with `eol=lf`, a local commit and `PHASE2_HANDOFF.md`.
Do not create repositories, push, deploy, retrieve keys or submit to the Portal.
Phase 3 must be handed to the stronger model for review and a separate live run.

Use the pinned virtual environment at
`C:/Users/User/Desktop/Genlayer apps/intelligent-contracts-v2/.venv`:
`genlayer-test==0.30.0rc2`, `genvm-linter==0.11.1rc2`. The future live caller must
use GenLayerJS or the previously reviewed license-bundle adapter because the
user reports `genlayer-py==0.19.0rc2` method encoding is incompatible with this
runner. No live compatibility is asserted by Phase 2.

For a future approved StudioNet run, measure commit-pinned raw GitHub fixtures
using curl; deploy from the local source commit and verify exact Git blob bytes.
Record court status separately from protocol ACCEPTED/FINALIZED and leader
execution/votes; read back after every step. Do not retry an unexpected live
judgment. Contract repository must remain private and no Portal submission may
be made. This phase produces no live manifest or passing live evidence gate.

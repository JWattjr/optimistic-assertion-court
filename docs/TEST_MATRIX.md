# Phase 2 requirement-to-test matrix

All named tests are in `tests/test_court.py`. Parameterized functions expand to
multiple test cases. `invoke` checks ledger conservation after successful steps;
`rejected` checks accounting and history are unchanged after a rejection. The
invariant also independently sums balances and escrows. The tests explicitly
call `VMContext.run_validator` on captured callbacks; ordinary direct execution
alone would test only the leader.

| Design requirement | Test coverage |
|---|---|
| Plan 1: unchallenged ACCEPTED, refund, zero web/LLM/nondeterministic calls | `test_unchallenged_zero_web_llm_or_consensus` (external functions patched to fail if called) |
| Plan 2: TRUE first result, provisional escrow, deterministic final award | `test_first_judgment_settlement[TRUE-0]` |
| Plan 3: FALSE first result and challenger award | `test_first_judgment_settlement[FALSE-1]` |
| Plan 4: UNDETERMINED voids, refunds, no appeal | `test_first_judgment_settlement[UNDETERMINED-None]` |
| Plan 5: challenge at/after deadline reverts | `test_late_challenge_exact_boundary` |
| Plan 6: exact matching challenge bond | `test_wrong_challenge_bond` |
| Plan 7: one successful loser appeal only | `test_appeal_once_uphold_flip_or_refund`; `test_appeal_actor_and_deadline_guards` |
| Plan 8: exact 2B appeal bond | `test_wrong_appeal_bond` |
| Plan 9: appeal flips payout, preserves first result | `test_appeal_once_uphold_flip_or_refund[TRUE-FALSE]` and `[FALSE-TRUE]` |
| Plan 10: conservation, nonnegative balances, status escrow after every step | `check`/`invoke`/`rejected` throughout suite; settlement tests; `test_cumulative_deposit_cap_rejects_before_registering_account` |
| Plan 11: forged leader with same verdict, invalid citation/digest rejected | `test_forged_or_unsupported_leader_rejected` |
| Plan 12: non-200, empty, oversized, invalid UTF-8 become unavailable then VOID | `test_unavailable_evidence_void_and_refund_without_llm` |
| Plan 13: terminal actions and reused withdrawal fail | `test_withdrawal_only_available_no_double_withdrawal_and_terminal_actions`; `test_all_claim_actions_rejected_after_other_terminal_states` |
| Plan 14: constructor, inputs, windows, bonds, URLs, claim-count limits | `test_constructor_window_bounds`; `test_title_and_config_are_bounded_and_frozen`; `test_claim_input_bounds_and_balance`; `test_valid_public_url_shapes`; `test_invalid_public_url_hosts`; `test_invalid_url_characters`; `test_claim_count_limit_and_history` |
| Plan 15: maximum B supports 2B appeal and 4B pot | `test_maximum_original_bond_allows_twice_bond_appeal` |
| Plan 16: bounded accounts/history and single settlement; failed appeal atomicity | `test_lifetime_account_bound_preserves_existing_accounts`; `test_claim_count_limit_and_history`; `test_failed_appeal_leaves_original_bonds_and_appeal_unused`; terminal tests |
| Plan 17: available/digest mismatch, schema/type/duplicate-key failures, unavailable appeal, byte boundary | `test_forged_or_unsupported_leader_rejected`; `test_unavailable_disagreement_cannot_accept_leader`; `test_malformed_model_result_cannot_settle`; `test_unavailable_appeal_refunds_all_three_bonds`; `test_exactly_15000_raw_bytes_and_digest` |
| Plan 18 / approved change 1: different valid excerpt accepted and leader quote retained | `test_valid_alternative_citation_is_verified_and_leader_quote_retained` |
| Citation must be a substring, nonempty at first stage, support verdict | `test_forged_or_unsupported_leader_rejected[non-substring]`, `[empty]`, `[non-supporting]` |
| Appeal citation >=24 characters and >=4 whitespace tokens | `test_too_short_appeal_citation_rejected_by_validator`; `test_appeal_minimum_four_tokens_is_enforced`; `test_failed_appeal_leaves_original_bonds_and_appeal_unused` |
| Compare verdict, evidence digest and availability exactly; genuine boolean support confirmation | `test_forged_or_unsupported_leader_rejected[verdict]`, `[digest]`, `[availability]`, `[bool-verdict]`, `[string-supports]` |
| Plan 19 / approved change 2: stale DISPUTED/PROVISIONAL refund before/at/after boundary, any caller, no web/LLM | `test_void_stale_before_at_and_after_deadline_no_consensus` (both states, times 300 and 301, precheck 299; external functions patched to fail) |
| Stale OPEN/terminal prohibited; adjudication/appeal/final award blocked at staleness | `test_void_stale_open_or_already_settled_rejected`; `test_void_stale_before_at_and_after_deadline_no_consensus`; `test_late_first_judgment_does_not_extend_stale_deadline` |
| Fresh immutable appeal rubric and both first/final outcomes retained | `test_appeal_once_uphold_flip_or_refund`; appeal minimum tests; separate callback capture per stage |
| No self-challenge, duplicate challenge, early or duplicate adjudication | `test_challenge_guards_and_first_judgment_once` |
| Only available balance can fund bonds or withdrawals; positive bounded deposits | `test_claim_input_bounds_and_balance`; `test_unknown_id_and_unfunded_address`; `test_withdrawal_only_available_no_double_withdrawal_and_terminal_actions`; `test_deposit_bounds` |
| Complete returned body, identity encoding, no partial/mismatched response, exact raw hash | `test_unavailable_evidence_void_and_refund_without_llm`; `test_exactly_15000_raw_bytes_and_digest` |
| Transport exception is unavailable; implementation errors cannot silently refund | `test_transport_failure_is_unavailable_but_programming_error_is_not`; `test_fetch_programming_error_does_not_void_dispute` |
| No admin mutators, frozen durations/bounds, deterministic generated IDs and bounded history | `test_title_and_config_are_bounded_and_frozen`; `test_claim_count_limit_and_history`; source/ABI inspection |
| Runner pin, SDK safety/storage typing, ABI validity, LF line endings | `genvm-lint check` (3 AST checks plus SDK validation); schema extraction; final Git/blob and LF checks recorded in handoff |
| Distinctiveness against the five named local accepted contracts | Phase 1 local source review, retained in `DESIGN.md` section 14; no automated or live originality claim |
| StudioNet-only target, private/no-push/no-deploy/no-key Phase 2 boundary | Operational scope; no live/network release actions form part of these checks |

## Evidence limits

All model/web responses are controlled fixtures except a transport-error unit
fixture. Independent callback execution verifies the comparison code with these
fixtures; it does not demonstrate actual validator votes, network finality,
semantic correctness, remote URL reachability or runtime redirect behavior.
The cumulative-deposit cap test temporarily scales the test module's constant
to 201 units, avoiding a million maximum-sized deposits. The production source
remains capped at 10^18. History's 256-record cap is unreachable through 32 valid
claims (at most four persisted lifecycle events per claim); the test exercises
all 32 unchallenged claim lifecycles and checks bounded monotonic history.

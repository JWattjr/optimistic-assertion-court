# Portal draft — not submitted

Optimistic Assertion Court accepts a bonded claim after an unchallenged window with no web/LLM call. A matched-bond dispute activates validators to independently fetch evidence, agree on verdict/digest/availability and verify the leader's exact citation. Code controls payouts; ambiguity refunds. The loser may fund one stricter appeal at 2B. The live StudioNet demo includes both dispute outcomes and a loser-funded appeal confirming FALSE with the full 4B pot paid to the challenger, plus rejected winner, wrong-bond and second appeals. Late challenges and reused withdrawals also revert. Stale disputes can be refunded without inference. Limits: synthetic bond units, bounded UTF-8 evidence and model risk; no real asset custody.

Portal note length: 732 characters.

The contract repository remains PRIVATE. No Portal submission was made. If the owner later elects
to submit, the owner must decide and perform any required repository visibility change.

## Evidence

- StudioNet contract: `0xC59715a21e2cac8e8978F4D3098087930399fCF2`.
- Reviewed deployed-source commit: `3b0ce9c68628538431942bc6d8db00773ab716cf`.
- [Complete manifest](deployments/studionet-release-2026-10-20.json).
- [Fixture URLs, curl counts and SHA-256](docs/EVIDENCE.json).
- [Review and limits](docs/REVIEW.md), [verification results](docs/REVIEW_RESULTS.json),
  [test matrix](docs/TEST_MATRIX.md), and [local distinctiveness comparison](docs/DESIGN.md#14-distinctiveness-against-the-named-accepted-contracts).

## Appended live appeal evidence

- [Pinned appeal fixture](https://raw.githubusercontent.com/JWattjr/genlayer-demo-evidence/24cf4f229fc811b65df86f0c9593dccde2cd35a9/optimistic-assertion-court/appeal-raven-bridge.txt), 313 curl-measured raw bytes.
- [c. Adjudicate FALSE](https://explorer-studio.genlayer.com/tx/0x8bf578156f5ae58090c111afbbf2eb9d2d833e04c4b3c2369858170ce1b7edb3) — SUCCESS/return, FINALIZED.
- [d. Winner appeal rejected](https://explorer-studio.genlayer.com/tx/0x70fac984eba0dd615f4c6b414afe57767ce210eac9e6d80b8326a46f451eb8fa) — ERROR/rollback, FINALIZED.
- [e. Wrong bond rejected](https://explorer-studio.genlayer.com/tx/0xe986bafb1dc6814067b9c17e9b9716a83a4f3c341fb0010a1ee1e4732d2aec56) — ERROR/rollback, FINALIZED.
- [f. Loser appeal confirms FALSE](https://explorer-studio.genlayer.com/tx/0xb0577b9dd6df2efc8c5491106b007038abafe4b2d15502cf1509c497ed5d63ae) — SUCCESS/return, FINALIZED.
- [g. Second appeal rejected](https://explorer-studio.genlayer.com/tx/0x034330a78ee855a2898dc77d0586a48a247d0f6c929cff227cee051c37f79bc0) — ERROR/rollback, FINALIZED.

# Phase 9 decision — Legacy V1 retired

Decision:

- The old CLIP + ExtraTrees brain is retired.
- We will not spend development time reconstructing or improving it.
- It remains only as historical context.
- The active comparison floor is the simple reproducible baseline.
- Every new brain/model candidate from this point forward gets its own
  candidate ID/version and retains its parent candidate for comparison.
- No future brain replaces the active one without a measured quality gate.
- Rollback information is preserved whenever a candidate is promoted.

This matches the product direction: engineering time goes into the new Brain
architecture and measurable improvements, not resurrection of a legacy model
that did not solve the target problem.

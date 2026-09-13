<!-- template: tla-validation-plan/1 -->
# Validation Plan — <engagement title>

**Deployment is not validation.** "It deployed" or "the template validated" does not show that a requirement is met.

## Principles
- Every requirement you claim is met has a test or an explicit review rationale (see `TRACEABILITY_MATRIX.md`).
- **Every boundary has a negative test** — an attempt that must be refused.
- **A test that has never been seen to fail proves nothing:** for each critical negative test, run it once with the
  control deliberately removed in a safe test setup and confirm it fails (a sensitivity run). Never ship that setup.
- Check leaks at the layer that decides (for example what was retrieved), not only in the final answer.
- Use synthetic data only.

## Test levels
`L0` static checks · `L1` configuration intent · `L2` deployment smoke · `L3` requirement acceptance (positive, negative,
isolation, security) · `L4` failure and assumption tests · `L5` fresh-copy run of the published instructions.

## Tests
| ID | Verifies | Level | Type | Setup | Action | Expected result | Evidence captured | Sensitivity run | Cleanup |
|---|---|---|---|---|---|---|---|---|---|
| TST-AREA-000 | <SEC-…> | L3 | negative | <state before> | <what you attempt> | <refused / allowed> | <what you record> | <control removed → must fail> | <how to reset> |

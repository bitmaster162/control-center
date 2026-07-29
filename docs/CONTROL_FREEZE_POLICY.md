# CONTROL_FREEZE Policy R64

Approved by Robert as D3.

1. Maximum one **control-generation** per seven calendar days.
2. Exceptions: P0 security, broken current pointer, corrupted authority state or unrecoverable return-plane failure.
3. Dispatch, evidence, transport and product deltas do not create a control-generation.
4. A proposed control-generation must contain at least one:
   - `PRODUCT_DELTA`;
   - `USER_VALUE_DELTA`;
   - `P0_RISK_REDUCTION`;
   - `BROKEN_INVARIANT_REPAIR`.
5. A generation that only repackages the same state is rejected as `CONTROL_CHURN`.
6. Current pointer is written last and only after device + provider readback.
7. Every generation carries a lineage entry and explicit supersession scope.

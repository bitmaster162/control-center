# P0 R2 Replay Anchor Projection

Status: `DRAFT CANDIDATE / HISTORICAL REPLAY REFERENCE / NO CURRENT-TRUTH APPLY / NO EFFECT`

## Purpose

Provide the Control Center side of the P0 R2 trusted-replay handshake without turning a TradingOS self-hash into its own trust root.

The projection derives one deterministic replay reference from the exact bounded R64 authority basis already present in the Control Center candidate:

```text
R64 CURRENT_STATE SHA-256
R64 MANIFEST SHA-256
R64 CURRENT_POINTER SHA-256
        ↓
Control Center composite authority_root_sha256
        +
case_id / case_sha256 / temporal evidence_bundle_sha256
        ↓
case_binding_sha256
```

TradingOS R2 may consume these values as the expected reference:

```text
expected_authority_id
expected_root_sha256
expected_case_binding_sha256
```

## Historical-only boundary

The exact R64 provider capture used by this candidate is:

`2026-08-12T04:59:00+07:00`

That root can be used only as a historical replay reference for cases frozen at or after the capture time. A case frozen before the root capture fails closed.

This projection does **not** refresh Control Center provider truth and does not claim that the old R64 provider evidence is currently fresh.

```text
current_provider_freshness_claimed=false
historical_replay_reference_only=true
current_truth_promotion_allowed=false
```

## Trust ceiling

The composite R64 root is a deterministic projection over the exact authority-basis hashes. It is not a digital signature and does not by itself prove source authenticity against an attacker who controls both the repository/artifact tree and the independently retained trust record.

Therefore stronger authenticity still requires an independent accepted custody/signature/authority record.

```text
projected hash != signature
replay anchor != current truth
replay anchor != approval
replay anchor != execution permission
```

## No effects

```text
apply=false
current_truth=false
command_queue=false
decision_ledger=false
return_registry=false
human_gate=false
continuity=false
runtime=false
trading=false
capital=false
effect_candidates_created=0
executions_authorized=0
execution_authority=NONE
can_trade=false
capital_permission=DENY
```

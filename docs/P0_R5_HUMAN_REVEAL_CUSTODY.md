# P0 R5 — Human Reveal Custody

Status: DRAFT / SHADOW ONLY / NO CURRENT-TRUTH APPLY

R5 adds a bounded Human Gate verification path without changing R64 current truth and without creating execution authority.

## Contracts

```text
control_center.shadow_human_approval_challenge.v1
        ↓
control_center.shadow_human_custody_attestation.v1
        ↓
control_center.shadow_human_approval_verification.v1
        ↓
bitevo.shadow_authenticated_reveal_closure.v1
        ↓
control_center.shadow_authenticated_reveal_projection.v1
```

The challenge is specific to one case, DecisionPacket, SCT prediction, option set, expected human subject, session, device, custody provider, nonce and expiry window.

## Cryptographic scope

The custody attestation uses HMAC-SHA256 with verifier key material supplied out-of-band to the verifier. The repository contains no production verifier key.

A valid MAC means the attestation was produced by a party holding that verifier key for the exact challenge payload. It does not prove biometric or physical presence.

Therefore:

```text
human_identity_scope=CUSTODY_PROVIDER_SUBJECT_ASSERTION_ONLY
physical_human_presence_proven=false
```

Any attempt to mark HMAC custody evidence as physical-human proof is rejected.

## Single-use boundary

The verifier consumes an externally expected approval-registry digest. A challenge already present in that registry is rejected.

An unused challenge produces only a next registry candidate. P0 performs no Human Gate/registry write, so durable single-use enforcement is not claimed live.

## Projection boundary

The final projection is:

`NON_AUTHORITY_AUTHENTICATED_REVEAL_PROJECTION`

It can display custody verification, challenge identity and selected reveal action for review. It cannot:

- promote current truth;
- mutate Human Gate;
- mutate Decision Ledger or Command Queue;
- authorize execution;
- trade;
- create a signal/order/capital effect.

## Fixed P0 ceiling

```text
current_truth_promotion_allowed=false
apply=false
human_gate_write=false
execution_authority=NONE
can_trade=false
capital_permission=DENY
```

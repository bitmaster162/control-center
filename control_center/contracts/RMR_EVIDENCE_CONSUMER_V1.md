# RMR Evidence Consumer V1

Status: `CANDIDATE / READ-ONLY / NON-AUTHORITY`

## Purpose

This contract defines a fail-closed Control Center consumer for the accepted RobertMemoryRouter R7 loopback service. It transports evidence into review workflows; it does not make RMR a Current Truth authority.

Pinned producer identity:

- endpoint: `http://127.0.0.1:8787`
- HEAD: `8f82ad49c6ddcde7c698eec101b5f0ed985f24bc`
- tree: `911467a1a1d355b51fbe70ff95b86cd63fb7a212`
- approved identity SHA-256: `271ba9ba2f78c0cd03db7cb16ae3d2dbe9511926703658d5288677956bff02c2`
- authority class: `EVIDENCE_ONLY`
- router status: `CANDIDATE_NOT_LIVE`
- service status: `READY_LOOPBACK_ONLY`

## Security and currentness gate

Before every evidence operation the consumer must:

1. use the literal endpoint `http://127.0.0.1:8787`; no hostname, wildcard, LAN address, redirect, proxy or alternate port is accepted;
2. GET `/healthz` and require HTTP 200, no CORS header, `READY_LOOPBACK_ONLY`, `CANDIDATE_NOT_LIVE`, `EVIDENCE_ONLY`, exact pinned HEAD/tree, `query_only=1`, `source_identity_runtime_bound=true`, and `tracked_file_hashes_match=true`;
3. POST authenticated `{"operation":"status"}` to `/v1/router` using `Authorization: Bearer <token>`;
4. require `read_only=true`, `query_only=1`, `authority_class=EVIDENCE_ONLY`, `router_status=CANDIDATE_NOT_LIVE`, `source_identity.identity_match=true`, and exact pinned build HEAD/tree;
5. reject the request on any mismatch, timeout, auth failure, malformed JSON or transport failure.

The token is runtime-only secret material. It must not be committed, logged, included in evidence envelopes, or stored by this adapter.

The identity SHA is pinned by this contract while the runtime endpoint proves `source_identity.identity_match=true` and exact HEAD/tree. The envelope therefore records the binding method as `PINNED_CONFIG_PLUS_RUNTIME_IDENTITY_MATCH`; it does not claim the HTTP API directly exposes the identity-file SHA.

## Allowed operations

Only the R7 read-only operation set may be called: `status`, `search_text`, `search_all`, `search_messages`, `search_documents`, `search_events`, `search_project_events`, `search_claims`, exact getters, `get_project`, `get_evidence`, `get_git_refs`, `get_conflicts`, and `coverage`.

Unknown operations fail before network execution.

## Evidence envelope

Every successful operation produces `RMR_EVIDENCE_ENVELOPE_V1` containing request/time identifiers, pinned RMR identity, operation and input digest, counts/pagination, authority/router status, provenance/coverage/conflict fields, response digest, consumer decision, raw evidence, and explicit `current_truth_promoted=false` / `execution_authority=NONE`.

Consumer decisions are limited to:

- `EVIDENCE_ACCEPTED_FOR_REVIEW`
- `EVIDENCE_PARTIAL`
- `EVIDENCE_CONFLICT`
- `EVIDENCE_GAP`
- `EVIDENCE_REJECTED_STALE_OR_IDENTITY_MISMATCH`
- `EVIDENCE_REJECTED_HEALTH_OR_AUTH_FAILURE`

No decision means Current Truth acceptance. Labels such as `CURRENT_TRUTH_ACCEPTED`, `LIVE_AUTHORITY`, `PRODUCTION_ACCEPTED`, and `EXECUTION_AUTHORIZED` are forbidden.

## Authority ceiling

The consumer has no RMR mutation, Control Center live-state write, merge, deploy, service/NSSM, external-send, trading or capital authority. `auto_accept=false`, `auto_dispatch=false`, `self_application=false`, `can_trade=false`, `capital_permission=DENY`.

# RMR Evidence Runner V1

Status: `CANDIDATE / REVIEW-ONLY / NO AUTHORITY PROMOTION`

## Purpose

Provide a minimal local CLI boundary around the merged `RMREvidenceConsumer` so an operator-side
Python process can request RMR evidence without exposing bearer credentials to browser JavaScript
and without wiring RMR directly into Current Truth.

The runner is an evidence transport helper only. It does not make RMR a Control Center source of
semantic authority.

## Fixed boundaries

- Reuse `control_center/scripts/rmr_evidence_consumer.py`; do not duplicate its transport,
  health, identity, currentness, provenance or classification logic.
- RMR endpoint remains pinned by the consumer to `http://127.0.0.1:8787`.
- No endpoint/base-URL override is accepted by this runner.
- The bearer token is supplied only through required `--token-file`.
- No token literal CLI argument, environment-variable fallback, `.env` loading, browser storage,
  repository storage or generated evidence field is allowed.
- Successful output is one `RMR_EVIDENCE_ENVELOPE_V1` JSON object on stdout.
- Default custody is stdout only. The runner has no file-output, Drive, provider, repository,
  Return Registry or Current Truth write path.
- No `SOURCE_ENVELOPE_V1` conversion is performed.
- No service/NSSM start, stop, restart, install, configuration or ACL mutation is performed.
- No deploy, external-send, trading or capital effect exists.

## Invocation

```text
python control_center/scripts/rmr_evidence_runner.py \
  --token-file <runtime-secret-file> \
  --operation <allowed-rmr-operation> \
  --arguments-json <json-object>
```

`--arguments-json` defaults to `{}` and must decode to a JSON object. Keys that could masquerade as
transport/auth configuration (`operation`, `token`, `authorization`, `endpoint`, `base_url`) are
rejected.

## Secret handling

The runner reads the token file at call time, strips surrounding whitespace, constructs the
existing `RMREvidenceConsumer`, and does not retain the token outside process memory.

On failure the CLI emits only a stable error code and exception class, never the token value or
token-file path. Tests must assert that known secret material is absent from stdout, stderr and
serialized evidence.

Repository security rules continue to prohibit credentials and `.env` files. This contract does not
authorize changing token-file location or ACLs.

## Evidence ceiling

Before successful stdout emission the runner independently verifies that the returned envelope keeps:

- `authority_class = EVIDENCE_ONLY`
- `current_truth_promoted = false`
- `execution_authority = NONE`
- a consumer decision from the merged consumer's bounded decision set

Any mismatch fails closed.

## CI/test boundary

CI must not call the live service. Tests inject a fake transport into the real
`RMREvidenceConsumer`, use temporary token files and cover:

- token-file-only secret intake;
- allowed operation execution;
- no token/path disclosure;
- malformed/non-object arguments;
- reserved argument keys;
- invalid token sanitization;
- fail-closed authority-ceiling checks.

## Not authorized

This candidate does not authorize:

- a real token-backed RMR invocation;
- runtime/service mutation;
- secret/ACL mutation;
- RMR-to-`SOURCE_ENVELOPE_V1` mapping;
- reducer/current-truth ingestion or promotion;
- Drive/provider writes;
- deployment;
- merge.

`current_truth_promoted=false`
`execution_authority=NONE`
`can_trade=false`
`capital_permission=DENY`

# GLOBAL MAIN HANDOFF DELTA R15 — PROVENANCE / ATTESTATION / EVENT STANDARDS

**Date:** 2026-08-22 Asia/Bangkok  
**Mode:** architecture/research only  
**Authority effect:** NONE

## Decision

Do not reinvent commodity provenance, content-reference, attestation and event-envelope primitives.

Keep proprietary:
- UAI logical/provider identity semantics;
- Agent Trajectory Bundle evidence/custody envelope;
- Causal Spine/current-state semantics;
- authority/effect receipts;
- evidence adjudication;
- proprietary benchmarks.

Adapt/integrate mature standards where they fit.

## W3C PROV

Conceptual adapter:
- UAI artifact/version -> `prov:Entity`
- ingest/translate/run/evaluate -> `prov:Activity`
- human/provider/agent/model-service -> `prov:Agent`
- derived_from -> `prov:wasDerivedFrom`
- responsibility -> `prov:wasAssociatedWith`
- delegation -> `prov:actedOnBehalfOf`
- alternate representations/custody copies -> `prov:alternateOf`
- exact/provider-specific realization -> `prov:specializationOf`
- provenance set -> `prov:Bundle`

Do not require RDF/PROV-O as canonical storage.

## OCI Content Descriptor

Borrow secure member-reference shape:
`mediaType + digest + size` plus internal UAI version identity and locator.

Verify retrieved size/digest before interpretation.
Digest is exact content identity, not logical provider/custody identity.

## SLSA / in-toto provenance

Borrow attestation structure for translation/build/run receipts:
- subject/output digest;
- build/run definition;
- external/internal parameters;
- resolved dependencies;
- builder identity/version;
- invocation ID;
- started/finished timestamps;
- byproducts.

Do not claim generic agent-run SLSA compliance without satisfying the actual SLSA profile.

## OpenLineage

Optional adapter for ingestion/data jobs:
- unique run ID;
- Job;
- Inputs/Outputs;
- RunEvent `START -> RUNNING -> COMPLETE|ABORT|FAIL`;
- facets.

Operational lineage only; not authority/effect truth.

## CloudEvents

Optional streaming envelope:
- id;
- source;
- specversion;
- type;
- optional subject/time/dataschema.

`source + id` is transport/event uniqueness, not UAI logical artifact identity.

## Revised build boundary

BUILD:
- UAI
- ATB
- authority/effect receipts
- causal/current-state semantics
- proprietary benchmarks

ADAPT:
- W3C PROV
- OCI descriptors
- SLSA/in-toto attestation patterns
- OpenLineage
- CloudEvents

INTEGRATE:
- ATIF
- ATOF
- OpenTelemetry GenAI
- OpenInference
- MCP
- A2A

No merge/deploy/runtime/destructive/trading/capital effect is authorized by this delta.

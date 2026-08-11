from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from hanri.attention_governor import canonical_sha256
from hanri.guarded_cli import enhanced_sanitize
from hanri.producer_adapters import POLICY_VERSION, adapt_artifacts, collect_source_rows

UTC = dt.timezone.utc


def _write_exact(path: Path, payload: object) -> None:
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        current = path.read_text(encoding="utf-8")
        if current == text:
            return
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(text, encoding="utf-8")
    temp.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="HANRI R39.2 read-only producer adapters")
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-bundle", required=True)
    parser.add_argument("--output-receipt", required=True)
    parser.add_argument("--generated-at")
    args = parser.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if config.get("policy_version") != POLICY_VERSION:
        raise SystemExit(f"expected policy_version={POLICY_VERSION}")

    generated_at = args.generated_at or dt.datetime.now(UTC).isoformat().replace("+00:00", "Z")
    now = dt.datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    rows, skipped = collect_source_rows(config, now=now)
    adapted = adapt_artifacts(rows)

    persistence_findings: list[dict[str, str]] = []
    clean_envelopes = enhanced_sanitize(adapted["envelopes"], persistence_findings)

    receipt = dict(adapted["receipt"])
    receipt["generated_at"] = generated_at
    receipt["scan_skips"] = skipped
    receipt["scan_skip_count"] = len(skipped)
    receipt["secret_boundary"] = {
        "finding_count": int(receipt.get("secret_boundary", {}).get("finding_count", 0)) + len(persistence_findings),
        "raw_values_persisted": False,
    }
    receipt["receipt_sha256"] = canonical_sha256({k: v for k, v in receipt.items() if k != "receipt_sha256"})

    bundle = {
        "schema_version": 1,
        "producer_policy_version": POLICY_VERSION,
        "generated_at": generated_at,
        "envelopes": clean_envelopes,
    }
    bundle["bundle_sha256"] = canonical_sha256(bundle)

    _write_exact(Path(args.output_bundle), bundle)
    _write_exact(Path(args.output_receipt), receipt)

    print(json.dumps({
        "status": "PASS",
        "policy_version": POLICY_VERSION,
        "processed_sources": receipt["processed_sources"],
        "emitted_envelopes": receipt["emitted_envelopes"],
        "scan_skip_count": receipt["scan_skip_count"],
        "secret_findings_fingerprinted": receipt["secret_boundary"]["finding_count"],
        "bundle_sha256": bundle["bundle_sha256"],
        "receipt_sha256": receipt["receipt_sha256"],
        "execution_effects_performed": 0,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

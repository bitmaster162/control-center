from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hanri.identity_cli import (
    ACTOR,
    HUMAN_LABEL,
    install_identity_guard,
    r29_archive_frontier_event,
    r29_causal_spine_event,
    r29_render_human_digest,
    r29_snapshot_event,
)
from hanri import cli as core


class R29IdentityTests(unittest.TestCase):
    def test_human_digest_identifies_r29(self) -> None:
        text = r29_render_human_digest("run-1", [], [], {}, {}, [])
        self.assertIn(f"# Human Decision Digest — {HUMAN_LABEL}", text)
        self.assertNotIn("# Human Decision Digest — HANRI R28", text)

    def test_snapshot_actor_identifies_r29(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("{}", encoding="utf-8")
            event = r29_snapshot_event(path, "state")
            self.assertEqual(event["actor"], ACTOR)

    def test_frontier_actor_identifies_r29(self) -> None:
        item = {
            "name": "item.md",
            "path": "/tmp/item.md",
            "sha256": "a" * 64,
            "content_class": "GENERIC_TEXT",
            "content_signature_verified": True,
        }
        pair = {
            "generated_at": "2026-08-09T00:00:00Z",
            "origin": dict(item),
            "current": dict(item),
            "same_name_collisions": [],
        }
        event = r29_archive_frontier_event(pair)
        self.assertEqual(event["actor"], ACTOR)

    def test_causal_spine_actor_identifies_r29(self) -> None:
        def item(name: str, char: str) -> dict[str, object]:
            return {
                "name": name,
                "path": f"/tmp/{name}",
                "sha256": char * 64,
                "content_class": "GENERIC_TEXT",
                "content_signature_verified": True,
            }

        spine = {
            "generated_at": "2026-08-09T00:00:00Z",
            "origin": item("origin.md", "a"),
            "pivot": item("pivot.md", "b"),
            "current": item("current.md", "c"),
            "same_name_collisions": [],
            "coverage_certificate": {
                "scope_id": "TEST",
                "scope_manifest_sha256": "d" * 64,
                "files": [{"path": "/tmp/current.md"}],
            },
        }
        event = r29_causal_spine_event(spine)
        self.assertEqual(event["actor"], ACTOR)

    def test_install_guard_rebinds_core_identity_and_version(self) -> None:
        install_identity_guard()
        self.assertEqual(core.VERSION, "29.0.0")
        self.assertIs(core.render_human_digest, r29_render_human_digest)
        self.assertIs(core.snapshot_event, r29_snapshot_event)
        self.assertIs(core.archive_frontier_event, r29_archive_frontier_event)
        self.assertIs(core.causal_spine_event, r29_causal_spine_event)


if __name__ == "__main__":
    unittest.main()

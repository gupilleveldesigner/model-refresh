"""Decision hand-off and completion-report checks (no browser, no model calls)."""
import hashlib
import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from finalize_run import finalize
from record_decisions import build
from render_report import canonical_hash, render
from review_server import bind
from validate_decisions import validate
from validate_report import validate_report


def proposal(diff: str = "") -> dict:
    return {
        "schema_version": "1.2", "mode": "setup", "report_id": "flow", "locale": "en-US",
        "phase3": {"required_stages": ["audit", "application"], "findings": [
            {"id": "note", "title": "Kept", "approval_required": False},
            {"id": "trim", "title": "Trim", "approval_required": True, "diff": diff,
             "diff_sha256": hashlib.sha256(diff.encode()).hexdigest() if diff else ""},
            {"id": "plugin", "title": "Plugin", "approval_required": True},
        ]},
    }


def outcome(results: list[dict], status: str = "COMPLETE") -> dict:
    return {"status": status, "results": results, "stages": {
        "audit": {"status": "pass", "evidence": ["read"]},
        "application": {"status": "pass", "evidence": ["re-read"]},
        "behavior": {"status": "unverified", "reason": "not observed"},
        "effect": {"status": "unverified", "reason": "not measured"}}}


APPLIED = {"decision": "approve", "applied": True, "verification": "PASS",
           "verification_level": "config", "evidence": ["file re-read"]}


class RecordTests(unittest.TestCase):
    def test_numbers_ids_and_default_defer(self):
        report = proposal()
        packet, filled = build(report, {"approve": ["#1"], "reject": [], "defer": []}, "defer", {"2": "later"}, "chat")
        result = validate(report, packet)
        self.assertTrue(result["valid"] and result["executable"])
        self.assertEqual((result["approved"], result["deferred"], filled), (["trim"], ["plugin"], ["plugin"]))
        self.assertEqual(packet["choices"][1]["note"], "later")

    def test_unknown_and_conflicting_references(self):
        report = proposal()
        with self.assertRaises(ValueError):
            build(report, {"approve": ["9"], "reject": [], "defer": []}, "defer", {}, "chat")
        with self.assertRaises(ValueError):
            build(report, {"approve": ["trim"], "reject": ["1"], "defer": []}, "defer", {}, "chat")

    def test_unmentioned_items_can_stay_unresolved(self):
        packet, _ = build(proposal(), {"approve": ["trim"], "reject": [], "defer": []}, None, {}, "chat")
        self.assertEqual((packet["unresolved"], packet["executable"]), (["plugin"], False))

    def test_unknown_source_is_rejected(self):
        report = proposal()
        packet, _ = build(report, {"approve": [], "reject": [], "defer": []}, "defer", {}, "chat")
        self.assertFalse(validate(report, {**packet, "source": "agent"})["valid"])


class RenderTests(unittest.TestCase):
    def test_page_hands_decisions_back_without_a_file(self):
        report = proposal()
        page = render(report, canonical_hash(report), {"trim": {"decision": "approve", "note": ""}})
        self.assertIn('id="submit-decisions"', page)
        self.assertIn("fetch('/submit'", page)
        self.assertIn('data-no="2"', page)
        self.assertIn('"trim": {"decision": "approve"', page)
        self.assertNotIn(".download=`model-refresh-decisions", page)


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.report = proposal()
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "decisions.json"
        self.server = bind(self.report, "<html></html>", self.path, 0)
        threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True).start()
        self.base = f"http://127.0.0.1:{self.server.server_address[1]}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.directory.cleanup()

    def post(self, packet: dict, **headers) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json", "X-Review-Token": self.server.token, **headers}
        request = urllib.request.Request(self.base + "/submit", json.dumps(packet).encode(), headers)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read() or b"{}")

    def packet(self) -> dict:
        return build(self.report, {"approve": ["trim"], "reject": ["plugin"], "defer": []}, None, {}, "chat")[0]

    def test_submit_writes_validated_packet(self):
        status, body = self.post(self.packet())
        self.assertEqual((status, body["approved"], body["rejected"]), (200, ["trim"], ["plugin"]))
        saved = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(saved["source"], "review_server")
        self.assertTrue(self.server.done.is_set())
        self.assertEqual(self.post(self.packet())[0], 409)

    def test_rejects_wrong_token_origin_host_and_stale_packet(self):
        self.assertEqual(self.post(self.packet(), **{"X-Review-Token": "nope"})[0], 403)
        self.assertEqual(self.post(self.packet(), Origin="https://example.com")[0], 403)
        self.assertEqual(self.post(self.packet(), Host="example.com")[0], 403)
        self.assertEqual(self.post({**self.packet(), "report_sha256": "0" * 64})[0], 400)
        incomplete = build(self.report, {"approve": ["trim"], "reject": [], "defer": []}, None, {}, "chat")[0]
        self.assertEqual(self.post(incomplete)[0], 400)
        self.assertFalse(self.path.exists())

    def test_page_requires_token(self):
        with self.assertRaises(urllib.error.HTTPError):
            urllib.request.urlopen(self.base + "/", timeout=5)
        with urllib.request.urlopen(f"{self.base}/?t={self.server.token}", timeout=5) as response:
            self.assertEqual(response.status, 200)


class EvidenceContractTests(unittest.TestCase):
    def report(self, result: dict, status: str = "COMPLETE") -> dict:
        r = proposal()
        r["phase5"] = outcome([{"finding_id": "trim", **result}, {"finding_id": "plugin", "decision": "reject", "applied": False}], status)
        return r

    def test_pass_needs_evidence_and_level(self):
        self.assertTrue(validate_report(self.report(APPLIED))["valid"])
        for missing in ("evidence", "verification_level"):
            self.assertFalse(validate_report(self.report({k: v for k, v in APPLIED.items() if k != missing}))["valid"])

    def test_unverified_item_cannot_be_complete(self):
        unverified = {"decision": "approve", "applied": True, "verification": "UNVERIFIED", "summary": "no way to observe"}
        self.assertFalse(validate_report(self.report(unverified))["valid"])
        self.assertTrue(validate_report(self.report(unverified, "PARTIAL"))["valid"])


class FinalizeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.target = self.root / "CLAUDE.md"
        self.target.write_text("keep\nnew rule\n", encoding="utf-8")
        self.diff = f"--- {self.target}\n+++ {self.target}\n@@\n-old rule\n+new rule\n"
        self.report_path = self.root / "report.json"

    def tearDown(self):
        self.directory.cleanup()

    def write(self, results: list[dict], decisions: dict[str, list[str]] | None, status: str = "COMPLETE") -> None:
        report = proposal(self.diff)
        if decisions is not None:
            packet, _ = build(report, {"approve": [], "reject": [], "defer": [], **decisions}, None, {}, "chat")
            (self.root / "decisions.json").write_text(json.dumps(packet), encoding="utf-8")
        report["phase5"] = outcome(results, status)
        self.report_path.write_text(json.dumps(report), encoding="utf-8")

    def results(self, **plugin) -> list[dict]:
        return [{"finding_id": "trim", **APPLIED}, {"finding_id": "plugin", "decision": "reject", "applied": False, **plugin}]

    def test_consistent_run_reports_limits(self):
        self.write(self.results(), {"approve": ["trim"], "reject": ["plugin"]})
        errors, summary = finalize(self.report_path)
        self.assertEqual(errors, [])
        self.assertIn("1 of 1 approved items applied", summary)
        self.assertIn("Runtime behavior after the change was not observed.", summary)
        self.assertIn("were not measured", summary)

    def test_requires_recorded_decisions(self):
        self.write(self.results(), None)
        self.assertTrue(any("no record" in e for e in finalize(self.report_path)[0]))

    def test_record_must_match_what_the_user_chose(self):
        self.write(self.results(), {"approve": ["trim", "plugin"]})
        self.assertTrue(any("user chose approve" in e for e in finalize(self.report_path)[0]))

    def test_proposal_changed_after_decision(self):
        self.write(self.results(), {"approve": ["trim"], "reject": ["plugin"]})
        report = json.loads(self.report_path.read_text(encoding="utf-8"))
        report["phase3"]["findings"][0]["title"] = "edited later"
        self.report_path.write_text(json.dumps(report), encoding="utf-8")
        self.assertTrue(any("changed after the user decided" in e for e in finalize(self.report_path)[0]))

    def test_applied_claim_must_be_visible_on_disk(self):
        self.write(self.results(), {"approve": ["trim"], "reject": ["plugin"]})
        self.target.write_text("keep\nold rule\n", encoding="utf-8")
        self.assertTrue(any("lacks 1 added line" in e for e in finalize(self.report_path)[0]))
        results = self.results()
        results[0]["disk_check_note"] = "the CLI rewrote the line in another form"
        self.write(results, {"approve": ["trim"], "reject": ["plugin"]})
        errors, summary = finalize(self.report_path)
        self.assertEqual(errors, [])
        self.assertIn("another form", summary)

    def test_pure_removal_left_in_place(self):
        self.diff = f"--- {self.target}\n+++ {self.target}\n@@\n-old rule\n"
        self.target.write_text("keep\nold rule\n", encoding="utf-8")
        self.write(self.results(), {"approve": ["trim"], "reject": ["plugin"]})
        self.assertTrue(any("still holds all 1 removed" in e for e in finalize(self.report_path)[0]))


if __name__ == "__main__":
    unittest.main()

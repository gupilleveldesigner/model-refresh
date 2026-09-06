"""Negative cases for model evidence and completion claims (no model calls)."""
import unittest
from validate_report import AXES, validate_report


def sample():
    return {
        "schema_version": "1.1", "report_id": "test", "locale": "ko-KR",
        "mode": "migration", "target_model": "gpt-6-astra",
        "phase3": {"findings": [], "required_stages": ["audit"]},
        "model_review": {
            "sources": [{"id": "official", "url": "https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra",
                         "checked_at": "2026-09-06", "model": "gpt-6-astra", "host": "API",
                         "section": "Prompting best practices", "takeaway": "Review instruction conflicts."}],
            "axes": [{"axis": a, "source_ids": ["official"], "current": "fixture",
                      "decision": "unverified", "reason": "No behavior run"} for a in sorted(AXES)]},
        "phase5": {"status": "COMPLETE", "results": [], "stages": {
            "audit": {"status": "pass", "evidence": ["fixture review"]},
            "application": {"status": "not_applicable", "reason": "No changes"},
            "behavior": {"status": "unverified", "reason": "Not run"},
            "effect": {"status": "unverified", "reason": "Not measured"}}}}


class ReportTests(unittest.TestCase):
    def test_valid_scoped_completion(self):
        self.assertTrue(validate_report(sample())["valid"])

    def test_missing_model_evidence(self):
        r = sample(); del r["model_review"]
        self.assertFalse(validate_report(r)["valid"])

    def test_unresolved_model(self):
        r = sample(); r["target_model"] = "latest"
        self.assertFalse(validate_report(r)["valid"])

    def test_missing_axis_and_bad_reference(self):
        for mutation in ("missing", "reference"):
            r = sample()
            if mutation == "missing": r["model_review"]["axes"].pop()
            else: r["model_review"]["axes"][0]["source_ids"] = ["absent"]
            self.assertFalse(validate_report(r)["valid"])

    def test_missing_source_date(self):
        r = sample(); del r["model_review"]["sources"][0]["checked_at"]
        self.assertFalse(validate_report(r)["valid"])

    def test_required_behavior_not_run(self):
        r = sample(); r["phase3"]["required_stages"].append("behavior")
        self.assertFalse(validate_report(r)["valid"])

    def test_pass_without_evidence(self):
        r = sample(); r["phase5"]["stages"]["effect"] = {"status": "pass"}
        self.assertFalse(validate_report(r)["valid"])

    def test_approved_but_unapplied(self):
        r = sample(); r["phase3"]["findings"] = [{"id": "f", "approval_required": True}]
        r["phase5"]["results"] = [{"finding_id": "f", "decision": "approve", "applied": False}]
        self.assertFalse(validate_report(r)["valid"])

    def test_rejected_is_not_unfinished(self):
        r = sample(); r["phase3"]["findings"] = [{"id": "f", "approval_required": True}]
        r["phase5"]["results"] = [{"finding_id": "f", "decision": "reject", "applied": False}]
        r["phase5"]["status"] = "NO_CHANGES"
        self.assertTrue(validate_report(r)["valid"])

    def test_unapproved_application(self):
        r = sample(); r["phase3"]["findings"] = [{"id": "f"}]
        r["phase5"]["results"] = [{"finding_id": "f", "decision": "reject", "applied": True}]
        self.assertFalse(validate_report(r)["valid"])

    def test_legacy_is_marked_unchecked(self):
        result = validate_report({"schema_version": "1.0"})
        self.assertTrue(result["valid"])
        self.assertTrue(result["warnings"])

    def test_setup_does_not_require_model_matrix(self):
        r = sample(); r["mode"] = "setup"; del r["model_review"]
        self.assertTrue(validate_report(r)["valid"])

    def test_proposal_requires_scope(self):
        r = sample(); r["phase5"] = None; del r["phase3"]["required_stages"]
        self.assertFalse(validate_report(r)["valid"])

    def test_wrong_model_source(self):
        r = sample(); r["model_review"]["sources"][0]["model"] = "other-model"
        self.assertFalse(validate_report(r)["valid"])

    def test_renderer_and_decisions_reject_missing_evidence(self):
        from render_report import render, canonical_hash
        from validate_decisions import validate
        r = sample(); del r["model_review"]
        with self.assertRaises(ValueError): render(r, canonical_hash(r))
        d = {"report_id": "test", "report_sha256": canonical_hash(r),
             "choices": [], "unresolved": [], "executable": True}
        self.assertFalse(validate(r, d)["valid"])

    def test_render_exposes_evidence_and_stages(self):
        from render_report import render, canonical_hash
        r = sample(); html = render(r, canonical_hash(r))
        self.assertIn('Model evidence', html)
        self.assertIn('<b>behavior</b>', html)
        self.assertIn('Not measured', html)


if __name__ == "__main__":
    unittest.main()

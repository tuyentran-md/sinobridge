from pathlib import Path
import tempfile
import unittest
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from hanviet_bridge.ingest import ingest
from hanviet_bridge.store import load_segments, save_segments
from hanviet_bridge.qa import audit, check_segment
from hanviet_bridge.translate import translate, parse_model_json
from hanviet_bridge.export import markdown, epub
from hanviet_bridge.explore import search
from hanviet_bridge.review import approve, revise, review_html, approval_is_current
from hanviet_bridge.qa import unmatched_numbers

class CoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.src = self.root / "sample.md"
        self.src.write_text("# 标题\n\n中国的医保有120个案例，p=0.05 [1]，10.1234/demo.\n", encoding="utf-8")
        self.ws = self.root / "workspace"
        self.meta = ingest(self.src, self.ws, "paper")
    def tearDown(self):
        self.tmp.cleanup()

    def test_ingest_traceable_and_revision_guard(self):
        segs = load_segments(self.ws)
        self.assertEqual(len(segs), 2)
        self.assertEqual(segs[1]["location"], "line:3")
        self.assertEqual(self.meta["segment_count"], len(segs))
        self.assertEqual(self.meta, ingest(self.src, self.ws, "paper"))
        self.src.write_text("different", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            ingest(self.src, self.ws, "paper")

    def test_qa_mismatch_and_release_blocked(self):
        segs = load_segments(self.ws)
        segs[0]["translation"] = "Tiêu đề"
        segs[0]["status"] = "DRAFT"
        segs[1]["translation"] = "Chính sách bảo hiểm Việt Nam có 120 trường hợp, p=0.05 [1]."
        segs[1]["status"] = "DRAFT"
        save_segments(self.ws, segs)
        codes = [i["code"] for i in check_segment(segs[1])]
        self.assertIn("DOI_MISMATCH", codes)
        self.assertIn("JURISDICTION_CONTEXT", codes)
        result = audit(self.ws)
        self.assertEqual(result["release_readiness"], "BLOCKED")
        self.assertNotEqual(result["gates"]["G7"]["status"], "PASS")

    def test_external_model_requires_explicit_consent(self):
        result = translate(self.ws, "gemini", "test-model", allow_external=False, dry_run=True)
        self.assertEqual(result["external_data_transfer"], "NOT_PERFORMED")
        with self.assertRaises(RuntimeError):
            translate(self.ws, "gemini", "test-model", allow_external=False, dry_run=False)

    def test_parser_enforces_json(self):
        self.assertEqual(parse_model_json('{"translation":"Bản dịch","ambiguities":[]}')["translation"], "Bản dịch")
        with self.assertRaises(ValueError):
            parse_model_json('{"wrong":"payload"}')

    def test_draft_epub_exists_and_is_epub3(self):
        target = self.root / "draft.epub"
        with self.assertRaises(RuntimeError):
            epub(self.ws, target, draft=False)
        epub(self.ws, target, draft=True)
        with zipfile.ZipFile(target) as z:
            self.assertEqual(z.namelist()[0], "mimetype")
            self.assertEqual(z.read("mimetype"), b"application/epub+zip")
            self.assertIn(b'xml:lang="vi"', z.read("OEBPS/chapter.xhtml"))

    def test_draft_markdown(self):
        target = self.root / "draft.md"
        markdown(self.ws, target, bilingual=True, draft=True)
        self.assertIn("Source line:1", target.read_text())

    def test_search_validation_never_calls_network(self):
        with self.assertRaises(ValueError):
            search("", "openalex")
        with self.assertRaises(ValueError):
            search("test", "openalex", limit=100)

    def test_numbers_compare_by_value_across_locales(self):
        self.assertEqual(unmatched_numbers("OR 1.25（95% CI 1.01–1.55），1,200名", "OR 1,25 (KTC 95% 1,01–1,55), 1.200 trẻ"), [])
        self.assertEqual(unmatched_numbers("１２０名", "120 trẻ"), [])
        self.assertEqual(unmatched_numbers("120 trẻ", "共一百二十名"), [])
        self.assertEqual(unmatched_numbers("死亡率为5%", "tử vong 50%"), ["5%"])
        self.assertEqual(unmatched_numbers("万一出现", "nếu chẳng may"), [])

    def test_revision_history_and_stale_approval(self):
        segs = load_segments(self.ws)
        sid = segs[1]["id"]
        segs[1]["translation"], segs[1]["status"] = "Bản nháp sai", "DRAFT"
        save_segments(self.ws, segs)
        approve(self.ws, sid, "reviewer", "read source")
        self.assertTrue(approval_is_current(load_segments(self.ws)[1]))
        segs = load_segments(self.ws)
        segs[1]["translation"] = "edited outside the tool"
        save_segments(self.ws, segs)
        self.assertIn("STALE_APPROVAL", [i["code"] for i in check_segment(load_segments(self.ws)[1])])
        revise(self.ws, sid, "Bản sửa", "reviewer", "wrong number", "HIGH", "NUMERIC_MISMATCH")
        seg = load_segments(self.ws)[1]
        self.assertEqual(seg["status"], "REVISED")
        self.assertNotIn("approval", seg)
        self.assertEqual(seg["history"][-1]["previous"], "edited outside the tool")
        self.assertEqual(seg["history"][-1]["severity"], "HIGH")

    def test_review_page_is_offline_and_escaped(self):
        segs = load_segments(self.ws)
        segs[1]["translation"], segs[1]["status"] = "</script><b>x</b>", "DRAFT"
        save_segments(self.ws, segs)
        audit(self.ws)
        page = review_html(self.ws, self.root / "review.html").read_text(encoding="utf-8")
        self.assertNotIn("</script><b>", page)
        self.assertNotIn("http://", page.replace("http://www.w3.org", ""))
        self.assertNotIn("https://", page)
        self.assertIn(segs[1]["id"], page)

if __name__ == "__main__":
    unittest.main()

from pathlib import Path
import tempfile
import unittest
import zipfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sinobridge.ingest import ingest
from sinobridge.store import load_segments, save_segments
from sinobridge.qa import audit, check_segment
from sinobridge.translate import translate, parse_model_json
from sinobridge.export import markdown, epub
from sinobridge.explore import search
from sinobridge.review import approve, revise, review_html, approval_is_current
from sinobridge.qa import unmatched_numbers

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

    def test_epub3_chapters_toc_and_colophon(self):
        target = self.root / "book.epub"
        epub(self.ws, target, bilingual=True)
        with zipfile.ZipFile(target) as z:
            names = z.namelist()
            self.assertEqual(names[0], "mimetype")
            self.assertEqual(z.read("mimetype"), b"application/epub+zip")
            self.assertIn("OEBPS/ch001.xhtml", names)
            self.assertIn(b"epub:type=\"toc\"", z.read("OEBPS/nav.xhtml"))
            self.assertIn("chưa được người duyệt".encode(), z.read("OEBPS/title.xhtml"))
            from xml.dom import minidom
            for n in names:
                if n.endswith((".xhtml", ".opf", ".xml")):
                    minidom.parseString(z.read(n))  # well-formed XML

    def test_markdown_clean_and_traceable(self):
        target = self.root / "draft.md"
        markdown(self.ws, target, bilingual=True)
        text = target.read_text()
        self.assertNotIn("<!--", text)
        self.assertIn("chưa được người duyệt", text)
        markdown(self.ws, target, trace=True)
        self.assertIn("line:3", target.read_text())

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


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
    def tearDown(self):
        self.tmp.cleanup()

    def test_wechat_style_container_and_gbk(self):
        from sinobridge.sources.html_text import html_blocks, decode_html
        html = ('<html><head><meta charset="gbk"><title>标题</title></head><body><nav>菜单</nav>'
                '<div id="js_content"><section><span>第一段</span></section><h2>小标题</h2>'
                '<p>第二段<br>续行</p></div><div class="comments">评论</div></body></html>')
        blocks, title = html_blocks(decode_html(html.encode("gbk")))
        self.assertEqual(title, "标题")
        self.assertEqual([b[2] for b in blocks], ["第一段", "小标题", "第二段\n续行"])
        self.assertEqual(blocks[1][1], "heading")

    def test_subtitle_roundtrip(self):
        from sinobridge.export import subtitles
        srt = self.root / "v.srt"
        srt.write_text("1\n00:00:01,000 --> 00:00:02,500\n你好\n\n2\n00:00:03,000 --> 00:00:04,000\n<i>再见</i>\n", encoding="utf-8")
        ws = self.root / "ws"
        ingest(srt, ws, "subtitle")
        segs = load_segments(ws)
        self.assertEqual([s["source"] for s in segs], ["你好", "再见"])
        segs[0]["translation"] = "Xin chào"
        save_segments(ws, segs)
        out = subtitles(ws, self.root / "vi.srt").read_text(encoding="utf-8")
        self.assertIn("00:00:01,000 --> 00:00:02,500\nXin chào", out)
        vtt = subtitles(ws, self.root / "vi.vtt").read_text(encoding="utf-8")
        self.assertTrue(vtt.startswith("WEBVTT"))
        self.assertIn("00:00:01.000 --> 00:00:02.500", vtt)

    def test_citation_imports_and_library(self):
        from sinobridge.sources.references import import_references
        from sinobridge import library as lib
        ris = self.root / "cnki.ris"
        ris.write_text("TY  - JOUR\nTI  - 先天性巨结肠的诊治\nAU  - 张三\nAU  - 李四\nPY  - 2021\nJO  - 中华小儿外科杂志\n"
                       "DO  - 10.3760/cma.j.issn.0253-3006.2021.01.001\nKW  - 巨结肠；儿童\nER  - \n", encoding="utf-8")
        enw = self.root / "wf.txt"
        enw.write_text("%0 Journal Article\n%T 先天性巨结肠的诊治\n%A 张三\n%D 2021\n"
                       "%R 10.3760/CMA.J.ISSN.0253-3006.2021.01.001\n", encoding="gb18030")
        ne = self.root / "ne.net"
        ne.write_text("{Reference Type}: Journal Article\n{Title}: 肛门直肠畸形术后随访\n{Author}: 王五\n{Year}: 2019\n", encoding="utf-8")
        a, b, c = import_references(ris), import_references(enw), import_references(ne)
        self.assertEqual((a["format"], b["format"], c["format"]), ("ris", "endnote", "noteexpress"))
        self.assertEqual(a["records"][0]["authors"], ["张三", "李四"])
        self.assertEqual(a["records"][0]["keywords"], ["巨结肠", "儿童"])
        library = self.root / "lib"
        lib.add(library, a["records"], {"file": "cnki.ris"})
        res = lib.add(library, b["records"] + c["records"], {"file": "wf.txt"})
        self.assertEqual((res["added"], res["merged_duplicates"], res["total"]), (1, 1, 2))
        rec = lib.find(library, "巨结肠")[0]
        self.assertEqual(len(rec["found_via"]), 2)
        self.assertIn("TI  - 先天性巨结肠的诊治", lib.to_ris([rec]))

    def test_providers_local_needs_no_external_flag(self):
        from sinobridge.translate import resolve_endpoint
        self.assertTrue(resolve_endpoint("ollama", None)[2])
        self.assertFalse(resolve_endpoint("deepseek", None)[2])
        with self.assertRaises(ValueError):
            resolve_endpoint("openai-compatible", None)
        src = self.root / "a.md"
        src.write_text("一段话", encoding="utf-8")
        ingest(src, self.root / "w", "article")
        with self.assertRaises(RuntimeError):
            translate(self.root / "w", "deepseek", "m", allow_external=False, dry_run=False)

    def test_registry_and_caj_message(self):
        from sinobridge.sources import registry, open_document
        reg = registry()
        self.assertTrue({"file", "url", "openalex", "crossref"} <= set(reg))
        with self.assertRaises(ValueError):
            open_document("http-less-thing.xyz")
        caj = self.root / "x.caj"
        caj.write_bytes(b"x")
        from sinobridge.sources.files import extract_file
        with self.assertRaisesRegex(ValueError, "PDF"):
            extract_file(caj)


class HanVietTests(unittest.TestCase):
    def test_known_names_and_places(self):
        from sinobridge.hanviet import transliterate
        cases = {"毛泽东": "Mao Trạch Đông", "诸葛亮": "Gia Cát Lượng", "周恩来": "Chu Ân Lai",
                 "北京": "Bắc Kinh", "重庆": "Trùng Khánh", "司马迁": "Tư Mã Thiên", "四川省": "tỉnh Tứ Xuyên"}
        for zh, vi in cases.items():
            self.assertEqual(transliterate(zh)["hanviet"], vi, zh)

    def test_character_level_and_flags(self):
        from sinobridge.hanviet import transliterate, readings, tone_key
        r = transliterate("张三丰", use_lexicon=False)
        self.assertEqual(r["hanviet"], "Trương Tam Phong")
        self.assertEqual(readings("行", "xing2")[0][0], "hành")
        self.assertEqual(readings("重", "chong2")[0][0], "trùng")
        self.assertEqual(transliterate("乐山")["hanviet"], "Lạc Sơn")      # pinyin context: le4 -> lạc
        self.assertLess(readings("乐")[0][1], 0.75)                       # without context: flagged
        self.assertEqual(tone_key("Hoà"), tone_key("hòa"))
        self.assertEqual(tone_key("lý"), tone_key("lí"))

    def test_term_memory_record_and_audit(self):
        from sinobridge import terms
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        src = root / "a.md"
        src.write_text("诸葛亮来到成都。\n\n诸葛亮笑了。", encoding="utf-8")
        ws = root / "ws"
        ingest(src, ws, "book")
        segs = load_segments(ws)
        notes = terms.record(ws, segs[0]["id"], [
            {"zh": "诸葛亮", "vi": "Chư Cát Lượng", "type": "person", "origin": "chinese"},
            {"zh": "特朗普", "vi": "Trump", "type": "person", "origin": "foreign"},
            {"zh": "乐山", "vi": "Lạc Sơn", "type": "place", "origin": "chinese"}])
        mem = terms.load(ws)
        self.assertEqual(mem["诸葛亮"]["render"], "Gia Cát Lượng")    # dictionary wins over the model
        self.assertEqual(mem["特朗普"]["render"], "Trump")            # foreign names are not Hán-Việt'd
        self.assertEqual(mem["乐山"]["render"], "Lạc Sơn")            # valid contextual reading kept
        self.assertEqual(notes[0]["standard"], "Gia Cát Lượng")
        segs[0]["translation"], segs[1]["translation"] = "Gia Cát Lượng đến Thành Đô.", "Khổng Minh cười."
        save_segments(ws, segs)
        self.assertEqual(terms.name_hints(segs[0]["source"]).get("诸葛亮"), "Gia Cát Lượng")
        result = audit(ws)
        codes = [(i["segment_id"], i["code"]) for i in result["issues"]]
        self.assertIn((segs[1]["id"], "TERM_INCONSISTENT"), codes)
        self.assertNotIn((segs[0]["id"], "TERM_INCONSISTENT"), codes)
        terms.set_term(ws, "诸葛亮", "Khổng Minh", "person")
        self.assertEqual(terms.load(ws)["诸葛亮"]["status"], "locked")
        tmp.cleanup()


class EnglishTargetTests(unittest.TestCase):
    def test_english_names(self):
        from sinobridge.names import english, render_name
        self.assertEqual(english("诸葛亮", "person")["render"], "Zhuge Liang")
        self.assertEqual(english("张明华", "person")["render"], "Zhang Minghua")
        self.assertEqual(english("欧阳明", "person")["render"], "Ouyang Ming")
        self.assertEqual(english("单明", "person")["render"], "Shan Ming")          # surname reading
        self.assertEqual(english("西安", "place")["render"], "Xi'an")
        self.assertEqual(english("四川省", "place")["render"], "Sichuan Province")
        self.assertEqual(english("某某县", "place")["render"].split()[-1], "County")
        self.assertEqual(render_name("诸葛亮", "person", "vi")["render"], "Gia Cát Lượng")

    def test_english_workspace_end_to_end(self):
        from sinobridge import terms
        from sinobridge.translate import system_prompt
        self.assertIn("Chinese-to-English", system_prompt("en"))
        self.assertIn("Hán-Việt", system_prompt("vi"))
        tmp = tempfile.TemporaryDirectory()
        root = Path(tmp.name)
        src = root / "a.md"
        src.write_text("# 第一章\n\n诸葛亮来到成都，人口120万。\n\n诸葛亮笑了。", encoding="utf-8")
        ws = root / "ws"
        meta = ingest(src, ws, "book", target="en")
        self.assertEqual(meta["target_language"], "en")
        with self.assertRaises(RuntimeError):            # same source, other target -> new workspace
            ingest(src, ws, "book", target="vi")
        segs = load_segments(ws)
        self.assertEqual(terms.name_hints(segs[1]["source"], "en"), {"诸葛亮": "Zhuge Liang", "成都": "Chengdu"})
        terms.record(ws, segs[1]["id"], [{"zh": "诸葛亮", "render": "Zhu Geliang", "type": "person"},
                                         {"zh": "成都", "render": "Chengdu", "type": "place"}], "en")
        self.assertEqual(terms.load(ws)["诸葛亮"]["render"], "Zhuge Liang")
        segs[0]["translation"] = "# Chapter 1"
        segs[1]["translation"] = "Zhuge Liang came to Chengdu, population 1.2 million."
        segs[2]["translation"] = "Kongming laughed."
        save_segments(ws, segs)
        result = audit(ws)
        codes = [(i["segment_id"], i["code"]) for i in result["issues"]]
        self.assertIn((segs[2]["id"], "TERM_INCONSISTENT"), codes)
        self.assertNotIn((segs[1]["id"], "TERM_INCONSISTENT"), codes)
        out = root / "book.epub"
        epub(ws, out, bilingual=True)
        with zipfile.ZipFile(out) as z:
            self.assertIn(b'xml:lang="en"', z.read("OEBPS/ch001.xhtml"))
            self.assertIn(b"<dc:language>en</dc:language>", z.read("OEBPS/content.opf"))
            self.assertIn(b"Draft machine translation", z.read("OEBPS/title.xhtml"))
        page = review_html(ws, root / "r.html").read_text(encoding="utf-8")
        self.assertIn("Click an English passage", page)
        self.assertIn('lang="en"', page)
        tmp.cleanup()

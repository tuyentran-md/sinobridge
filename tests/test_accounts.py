"""Account providers (ChatGPT via Codex CLI, Google via Antigravity CLI) with fake CLIs on PATH.

No real model is called: the fake tools record their arguments and answer with fixed JSON.
"""
import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
import sys
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sinobridge import translate as tr  # noqa: E402

FAKE_CODEX = r'''#!/usr/bin/env python3
import json, sys, os
args = sys.argv[1:]
prompt = sys.stdin.read()
open(os.environ["FAKE_LOG"], "w").write(json.dumps({"args": args, "prompt": prompt, "cwd": os.getcwd()}))
out = args[args.index("-o") + 1]
open(out, "w").write(json.dumps({"translation": "Thành Đô nổi tiếng về ẩm thực.", "ambiguities": [], "notes": [],
                                 "entities": [{"zh": "成都", "render": "Thành Đô", "type": "place"}]}))
'''

FAKE_AGY = r'''#!/usr/bin/env python3
import json, sys, os
args = sys.argv[1:]
open(os.environ["FAKE_LOG"], "w").write(json.dumps({"args": args, "cwd": os.getcwd()}))
print("Here is the result:\n" + json.dumps({"translation": "Chengdu is famous for its food.", "ambiguities": [],
                                              "notes": [], "entities": []}))
'''

FAILING = "#!/bin/sh\necho 'Not logged in' >&2\nexit 1\n"


class AccountProviders(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name)
        self.log = self.bin / "log.json"
        self.env = mock.patch.dict(os.environ, {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}",
                                                "FAKE_LOG": str(self.log)})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def tool(self, name, body):
        path = self.bin / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)

    def test_chatgpt_runs_codex_read_only_with_schema(self):
        self.tool("codex", FAKE_CODEX)
        result = tr.call_model("chatgpt", "", "成都以美食闻名。", "", "article", {}, target="vi")
        self.assertEqual(result["translation"], "Thành Đô nổi tiếng về ẩm thực.")
        call = json.loads(self.log.read_text())
        args = call["args"]
        self.assertEqual(args[0], "exec")
        for flag in ("--ephemeral", "--skip-git-repo-check", "--output-schema"):
            self.assertIn(flag, args)
        self.assertEqual(args[args.index("--sandbox") + 1], "read-only")
        self.assertNotIn("-m", args, "empty model means the account default")
        self.assertIn("成都以美食闻名", call["prompt"])
        self.assertIn("sinobridge-", call["cwd"], "runs in a throwaway directory")

    def test_google_runs_agy_and_tolerates_prose(self):
        self.tool("agy", FAKE_AGY)
        result = tr.call_model("google", "gemini-flash", "成都以美食闻名。", "", "article", {}, target="en")
        self.assertEqual(result["translation"], "Chengdu is famous for its food.")
        args = json.loads(self.log.read_text())["args"]
        self.assertEqual(args[0], "-p")
        self.assertIn("--sandbox", args)
        self.assertEqual(args[args.index("--model") + 1], "gemini-flash")

    def test_missing_or_signed_out_tool_explains_next_step(self):
        with mock.patch.object(tr.shutil, "which", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "not installed"):
                tr.call_model("chatgpt", "", "你好", "", "article", {})
        self.tool("agy", FAILING)
        with self.assertRaisesRegex(RuntimeError, "sign"):
            tr.call_model("google", "", "你好", "", "article", {})

    def test_account_needs_external_consent_but_no_key_or_model(self):
        self.tool("codex", FAKE_CODEX)
        from sinobridge.ingest import ingest
        ws = self.bin / "ws"
        src = self.bin / "a.md"
        src.write_text("成都以美食闻名。\n", encoding="utf-8")
        ingest(src, ws, "article")
        plan = tr.translate(ws, "chatgpt", "", allow_external=False, dry_run=True)
        self.assertFalse(plan["local"])
        with self.assertRaisesRegex(RuntimeError, "OFF"):
            tr.translate(ws, "chatgpt", "", allow_external=False, dry_run=False)
        tr.translate(ws, "chatgpt", "", allow_external=True, dry_run=False)
        seg = json.loads((ws / "segments.jsonl").read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(seg["translation"], "Thành Đô nổi tiếng về ẩm thực.")


if __name__ == "__main__":
    unittest.main()

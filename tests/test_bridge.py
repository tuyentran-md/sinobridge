"""The local app as a bridge for the browser edition: CORS, origin/host checks and the agy call.

A fake `agy` on PATH stands in for the real tool; no model is called.
"""
import http.client
import json
import os
import socket
import stat
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sinobridge import webapp  # noqa: E402

FAKE_AGY = r'''#!/usr/bin/env python3
import json, os, sys
args = sys.argv[1:]
if args == ["models"]:
    print("Fetching available models...")
    print("gemini-3.8-flash-medium\tGemini 3.8 Flash (Medium)")
    print("gemini-4-argon-low\tGemini 4 Argon (Low)")
    sys.exit(0)
open(os.environ["FAKE_LOG"], "w").write(json.dumps({"args": args, "cwd": os.getcwd()}))
print("⟦1⟧ Thành Đô nổi tiếng về ẩm thực.")
'''

PAGES = "https://tuyentran-md.github.io"


class Bridge(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        agy = bin_dir / "agy"
        agy.write_text(FAKE_AGY, encoding="utf-8")
        agy.chmod(agy.stat().st_mode | stat.S_IEXEC)
        self.log = root / "log.json"
        self.env = mock.patch.dict(os.environ, {"PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
                                                "FAKE_LOG": str(self.log)})
        self.env.start()
        webapp.MODEL_CACHE.clear()
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            self.port = s.getsockname()[1]
        self.server = webapp.create_server(root / "data", self.port)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.env.stop()
        self.tmp.cleanup()

    def call(self, method, path, origin=PAGES, body=None, host=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=20)
        headers = {"Host": host or f"127.0.0.1:{self.port}"}
        if origin:
            headers["Origin"] = origin
        data = None
        if body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response, (json.loads(raw) if raw else None)

    def test_preflight_allows_pages_origin_and_private_network(self):
        response, _ = self.call("OPTIONS", "/bridge/google/v1/chat/completions")
        self.assertEqual(response.status, 204)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), PAGES)
        self.assertEqual(response.getheader("Access-Control-Allow-Private-Network"), "true")

    def test_other_sites_missing_origin_and_bad_host_are_refused(self):
        for kwargs in ({"origin": "https://evil.example"}, {"origin": None},
                       {"host": "attacker.example:80"}):
            response, _ = self.call("GET", "/bridge/v1/info", **kwargs)
            self.assertEqual(response.status, 403, kwargs)
            self.assertIsNone(response.getheader("Access-Control-Allow-Origin"))
        response, _ = self.call("OPTIONS", "/bridge/v1/info", origin="https://evil.example")
        self.assertEqual(response.status, 403)

    def test_info_and_models(self):
        response, info = self.call("GET", "/bridge/v1/info")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.getheader("Access-Control-Allow-Origin"), PAGES)
        self.assertEqual(info["app"], "sinobridge")
        self.assertTrue(info["accounts"]["google"])
        _, models = self.call("GET", "/bridge/google/v1/models")
        self.assertEqual([m["id"] for m in models["data"]], ["gemini-3.8-flash-medium", "gemini-4-argon-low"])
        _, models = self.call("GET", "/bridge/chatgpt/v1/models")
        self.assertEqual([m["id"] for m in models["data"]], ["default"])

    def test_chat_runs_agy_with_chosen_model_in_empty_folder(self):
        body = {"model": "gemini-3.8-flash-medium", "messages": [
            {"role": "system", "content": "Translate numbered passages."},
            {"role": "user", "content": "Passages:\n⟦1⟧ 成都以美食闻名。"}]}
        response, answer = self.call("POST", "/bridge/google/v1/chat/completions", body=body)
        self.assertEqual(response.status, 200, answer)
        self.assertEqual(answer["choices"][0]["message"]["content"], "⟦1⟧ Thành Đô nổi tiếng về ẩm thực.")
        call = json.loads(self.log.read_text())
        args = call["args"]
        self.assertEqual(args[args.index("--model") + 1], "gemini-3.8-flash-medium")
        self.assertIn("--sandbox", args)
        self.assertNotIn("--json-schema", args)
        self.assertIn("成都以美食闻名", args[args.index("-p") + 1])
        self.assertTrue(Path(call["cwd"]).name.startswith("sinobridge-"))
        self.assertFalse(Path(call["cwd"]).exists())   # throwaway folder removed afterwards

    def test_bad_requests(self):
        response, answer = self.call("POST", "/bridge/google/v1/chat/completions", body={"model": "x; rm -rf /",
                                     "messages": [{"role": "user", "content": "hi"}]})
        self.assertEqual(response.status, 400)
        self.assertIn("model", answer["error"]["message"])
        response, _ = self.call("POST", "/bridge/unknown/v1/chat/completions", body={"messages": []})
        self.assertEqual(response.status, 404)


if __name__ == "__main__":
    unittest.main()

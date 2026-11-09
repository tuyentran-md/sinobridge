"""Local UI integration checks: real HTTP server, zero external model requests."""
import json
import socket
import sys
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sinobridge.webapp import create_server
from sinobridge.store import load_segments, save_segments

ROOT = Path(__file__).resolve().parents[1]

def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class WebAppTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.port = free_port()
        self.server = create_server(Path(self.tmp.name), port=self.port)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:" + str(self.port)
        with urlopen(self.base + "/") as r:
            self.page = r.read().decode()
        self.assertIn("Thả sách vào.", self.page)
        self.token = self.page.split("const TOKEN=")[1].split(";")[0].strip('"')
        self.assertGreater(len(self.token), 30)

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def call(self, path, data=None, headers=None, method=None):
        h={"Host": "127.0.0.1:"+str(self.port), "X-SinoBridge-Token":self.token}
        if data is not None:
            h["Origin"] = self.base
        h.update(headers or {})
        req = Request(self.base+path, data=data, headers=h, method=method)
        with urlopen(req, timeout=5) as r:
            if "application/json" in r.headers.get("Content-Type",""):
                return json.loads(r.read()), r
            return r.read(), r

    def upload(self):
        sample = (ROOT / "examples/synthetic_zh.md").read_bytes()
        item,_=self.call("/api/upload", data=sample,
                         headers={"X-Filename":quote("Demo.md"),"X-Document-Kind":"book"})
        self.assertGreater(item["segments"],0)
        return item

    def test_security_origin_token_host_and_upload(self):
        with self.assertRaises(HTTPError) as e:
            urlopen(self.base+"/api/projects")
        self.assertEqual(e.exception.code, 403)
        with self.assertRaises(HTTPError) as e:
            self.call("/api/upload", data=b"ABC",
                      headers={"Origin":"https://attacker.example","X-Filename":"evil.md"})
        self.assertEqual(e.exception.code,403)
        item=self.upload()
        items,_=self.call("/api/projects")
        self.assertEqual(items["projects"][0]["id"],item["id"])
        view,_=self.call("/api/preview?id="+item["id"])
        self.assertTrue(view["segments"][0]["source"])
        with self.assertRaises(HTTPError) as e:
            self.call("/api/preview?id=../../etc/passwd")
        self.assertEqual(e.exception.code,400)

    def test_model_key_used_only_in_memory_and_export(self):
        item=self.upload()
        uid=item["id"]
        folder=Path(self.tmp.name)/uid
        with self.assertRaises(HTTPError) as e:
            self.call("/api/start",data=json.dumps({
                "id":uid,"provider":"openai","model":"test-model","key":""}).encode(),
                headers={"Content-Type":"application/json"})
        self.assertEqual(e.exception.code,400)
        seen=[]
        def synthetic_translation(workspace,provider,model,**kwargs):
            seen.append(kwargs.get("credential"))
            assert kwargs.get("allow_external") is True
            segs=load_segments(workspace)
            seg=next(s for s in segs if s["status"]=="PENDING")
            seg["translation"]="Bản dịch thử nghiệm"
            seg["status"]="DRAFT"
            save_segments(workspace,segs)
            return {"remaining":sum(s["status"]=="PENDING" for s in segs)}
        with patch("sinobridge.webapp.translate",side_effect=synthetic_translation):
            result,_=self.call("/api/start",data=json.dumps({
                "id":uid,"provider":"openai","model":"test-model","key":"NEVER_SAVE_THIS_KEY"}).encode(),
                headers={"Content-Type":"application/json"})
            self.assertTrue(result["started"])
            state="running"
            for _ in range(100):
                result,_=self.call("/api/status?id="+uid)
                state=result["job"]["state"]
                if state in ("done","error"):
                    break
                time.sleep(.02)
            self.assertEqual(state,"done",result)
        self.assertEqual(seen,["NEVER_SAVE_THIS_KEY"]*item["segments"])
        for path in folder.rglob("*"):
            if path.is_file():
                self.assertNotIn("NEVER_SAVE_THIS_KEY",path.read_bytes().decode("utf-8",errors="ignore"))
        for ext in ("epub","md","html"):
            body,_=self.call("/api/download?id="+uid+"&format="+ext)
            self.assertGreater(len(body),100)
        result,_=self.call("/api/status?id="+uid)
        self.assertEqual(result["translated"],item["segments"])

    def test_english_target_and_localhost_origin(self):
        sample = "# 第一章\n\n诸葛亮来到成都。\n".encode("utf-8")
        headers = {"X-Filename": quote("Demo.md"), "X-Document-Kind": "book", "X-Target-Language": "en",
                   "Origin": self.base.replace("127.0.0.1", "localhost")}
        item, _ = self.call("/api/upload", data=sample, headers=headers)
        self.assertEqual(item["target"], "en")
        with self.assertRaises(HTTPError) as e:
            self.call("/api/upload", data=sample, headers={**headers, "X-Target-Language": "fr"})
        self.assertEqual(e.exception.code, 400)

if __name__ == "__main__":
    unittest.main()

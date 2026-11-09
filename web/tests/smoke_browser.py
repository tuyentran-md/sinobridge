"""Browser smoke test for the public demo.

Never downloads model weights and never calls a real provider: the Gemini endpoint is
intercepted and answered locally, so the batching, retry, key handling and export paths
run end to end at zero cost.
"""
import json
import os
import pathlib
import re
import signal
import subprocess
import tempfile
import time
import urllib.request
import zipfile
from playwright.sync_api import sync_playwright

WEB = pathlib.Path(__file__).resolve().parents[1]
ROOT = WEB.parent
PORT = 18871
URL = f"http://127.0.0.1:{PORT}/"
GEMINI = "https://generativelanguage.googleapis.com/"
server = subprocess.Popen(["npm", "run", "dev", "--", "--port", str(PORT), "--strictPort"],
                          cwd=WEB, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)


class FakeGemini:
    """Answers /models and /chat/completions like the OpenAI-compatible Gemini endpoint."""

    def __init__(self):
        self.calls, self.auth, self.passages = 0, set(), 0
        self.throttled = False

    def __call__(self, route, request):
        if request.method == "OPTIONS":
            return route.fulfill(status=204, headers=self.cors())
        self.auth.add(request.headers.get("authorization"))
        if request.url.endswith("/models"):
            body = {"data": [{"id": "models/gemini-2.5-flash"}, {"id": "models/gemini-2.5-pro"}, {"id": "models/text-embedding-004"}]}
            return route.fulfill(status=200, headers=self.cors(), body=json.dumps(body), content_type="application/json")
        self.calls += 1
        if not self.throttled:   # first chat call is rate limited: the client must wait and retry
            self.throttled = True
            return route.fulfill(status=429, headers={**self.cors(), "retry-after": "1"}, body="{}")
        payload = json.loads(request.post_data)
        assert payload["model"] == "gemini-2.5-flash", payload["model"]
        user = payload["messages"][-1]["content"]
        numbers = re.findall(r"⟦(\d+)⟧", user.split("Passages:", 1)[1])
        self.passages += len(numbers)
        answer = "\n".join(f"⟦{n}⟧ Bản dịch thử {n}" for n in numbers)
        body = {"choices": [{"message": {"role": "assistant", "content": answer}}]}
        return route.fulfill(status=200, headers=self.cors(), body=json.dumps(body), content_type="application/json")

    @staticmethod
    def cors():
        return {"access-control-allow-origin": "*", "access-control-allow-headers": "authorization,content-type",
                "access-control-allow-methods": "GET,POST,OPTIONS"}


try:
    for _ in range(60):
        try:
            urllib.request.urlopen(URL, timeout=0.5)
            break
        except Exception:
            time.sleep(.15)
    else:
        raise RuntimeError("Vite dev server failed to start")

    with tempfile.TemporaryDirectory() as d, sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(accept_downloads=True, viewport={"width": 1440, "height": 900})
        fake = FakeGemini()
        hosts = set()
        ctx.route(GEMINI + "**", fake)
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.on("request", lambda r: hosts.add(r.url.split("/")[2]))
        page.goto(URL, wait_until="domcontentloaded")
        assert "SinoBridge" in page.title()
        assert page.get_by_role("heading", name="Mở cửa vào Hán văn").is_visible()

        # Import a file: the bilingual reader replaces the welcome screen.
        page.locator("#file").set_input_files(str(ROOT / "examples" / "synthetic_zh.md"))
        page.locator("#current").wait_for(state="visible")
        assert "synthetic_zh.md" in page.locator("#current").inner_text()
        rows = page.locator("#preview .row").count()
        assert rows > 0
        assert page.locator('[data-export="epub"]').is_disabled()
        assert page.locator("#start").is_disabled(), "no key yet"

        # Paste a key: the model list is fetched and a Flash model preselected.
        assert page.locator("#provider").input_value() == "gemini"
        page.locator("#api-key").fill("test-key")
        page.wait_for_function("document.querySelector('#model').value==='gemini-2.5-flash'")
        assert page.locator("#start").is_enabled()
        page.locator("#start").click()
        page.wait_for_function("document.querySelector('#status').textContent.startsWith('Xong')", timeout=30000)
        assert fake.auth == {"Bearer test-key"}, fake.auth
        assert fake.passages == rows, (fake.passages, rows)
        assert fake.calls >= 2, "the 429 must be retried"
        assert page.locator("#preview .row.done").count() == rows
        assert "Bản dịch thử" in page.locator("#preview .row .tr").first.inner_text()
        assert hosts <= {f"127.0.0.1:{PORT}", "generativelanguage.googleapis.com"}, hosts
        assert page.evaluate("localStorage.getItem('sb-key-gemini')") is None, "key must not persist unless asked"

        # Persistence and exports.
        page.reload(wait_until="domcontentloaded")
        page.locator("#current").wait_for(state="visible")
        assert page.locator("#preview .row.done").count() == rows
        for fmt in ("epub", "docx", "html", "txt"):
            with page.expect_download() as download:
                page.locator('[data-export="' + fmt + '"]').click()
            dest = pathlib.Path(d) / ("out." + fmt)
            download.value.save_as(str(dest))
            assert dest.stat().st_size > 100, fmt
            if fmt == "epub":
                with zipfile.ZipFile(dest) as z:
                    assert z.namelist()[0] == "mimetype"
                    assert z.read("mimetype") == b"application/epub+zip"
                    assert "Bản dịch thử" in z.read("OEBPS/main.xhtml").decode()
            if fmt == "docx":
                with zipfile.ZipFile(dest) as z:
                    assert "word/document.xml" in z.namelist()
            if fmt == "html":
                assert "Bản dịch thử" in dest.read_text()

        # Remember-key is opt in.
        assert page.locator("#api-key").input_value() == "", "an unremembered key is gone after reload"
        page.locator("#api-key").fill("test-key")
        page.locator("#remember").check()
        assert page.evaluate("localStorage.getItem('sb-key-gemini')") == "test-key"
        page.locator("#remember").uncheck()
        assert page.evaluate("localStorage.getItem('sb-key-gemini')") is None

        # Re-import the generated EPUB and DOCX.
        for fmt in ("epub", "docx"):
            page.locator("#file").set_input_files(str(pathlib.Path(d) / ("out." + fmt)))
            page.wait_for_function('document.querySelector("#current").textContent.includes("out.' + fmt + '")', timeout=15000)
            assert page.locator("#preview .row").count() > 0, fmt
        assert not errors, errors

        # A wrong key is reported as a key problem.
        ctx2 = browser.new_context()
        ctx2.route(GEMINI + "**", lambda route, request: route.fulfill(status=401, headers=FakeGemini.cors(), body="{}"))
        p2 = ctx2.new_page()
        p2.goto(URL, wait_until="domcontentloaded")
        p2.locator("#try-sample").click()
        p2.locator("#current").wait_for(state="visible")
        assert "Ví dụ tiếng Trung" in p2.locator("#current").inner_text()
        p2.locator("#api-key").fill("bad-key")
        p2.locator("#model").fill("gemini-2.5-flash")
        p2.locator("#start").click()
        p2.wait_for_function("document.querySelector('#status').classList.contains('error')", timeout=15000)
        assert "Key không đúng" in p2.locator("#status").inner_text()
        ctx2.close(); ctx.close(); browser.close()
    print("BROWSER_SMOKE_PASS: import, key + model list, batched translation with 429 retry, "
          "persistence, 4 exports, opt-in key storage, wrong-key message, no real model calls")
finally:
    try:
        os.killpg(server.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    server.wait(timeout=10)

# HanViet Bridge

**Đọc, dịch và tra cứu tài liệu tiếng Trung sang tiếng Việt — mọi câu dịch đều truy được về đúng đoạn gốc.**

*Source-traceable Chinese → Vietnamese reading, translation and research toolkit. English summary below.*

HanViet Bridge là công cụ mã nguồn mở (MIT) gồm ba phần dùng chung một nền:

| Phần | Làm gì |
|---|---|
| **Nguồn** (connectors) | Lấy tài liệu tiếng Trung từ file (TXT, Markdown, DOCX, EPUB, PDF), trang web công khai (bài WeChat, Zhihu, báo, blog, Wikipedia), trang lưu từ trình duyệt, phụ đề video (Bilibili/Douyin: .srt/.vtt), trích dẫn xuất từ CNKI/Wanfang/VIP/SinoMed. Có cơ chế plugin để cộng đồng viết thêm nguồn. |
| **Dịch & kiểm định** | Dịch theo đoạn có ngữ cảnh và bảng thuật ngữ, bằng mô hình bạn chọn (DeepSeek, Qwen, OpenAI, Gemini, OpenRouter, hoặc **Ollama chạy trên máy** — không gửi dữ liệu ra ngoài). Tự động kiểm số liệu, DOI, trích dẫn, thuật ngữ, ngữ cảnh pháp lý Trung Quốc; sửa có lịch sử; duyệt gắn với đúng câu đã duyệt. |
| **Xuất bản sạch** | EPUB3 chia chương có mục lục, DOCX, Markdown, phụ đề .srt/.vtt tiếng Việt, và trang đọc song ngữ offline: bấm một câu tiếng Việt → thấy câu tiếng Trung, lỗi, ghi chú, lịch sử sửa. |

## Cài đặt

Python 3.10+.

    git clone <repo-url> && cd hanviet-bridge
    python3 -m venv .venv && . .venv/bin/activate
    pip install -e '.[all]'      # gồm hỗ trợ PDF và DOCX

## Dùng nhanh

    hanviet sources                                    # xem các nguồn hỗ trợ
    hanviet ingest sach.epub --workspace work/sach --kind book
    hanviet ingest "https://zh.wikipedia.org/wiki/汉越词" --workspace work/wiki --kind article
    hanviet ingest video.zh.srt --workspace work/video --kind subtitle

Dịch (mặc định 1 đoạn để thử; `--max-segments 0` = tất cả):

    # Mô hình chạy trên máy, không cần khoá API, dữ liệu không rời máy
    hanviet translate --workspace work/sach --provider ollama --model qwen2.5:14b --max-segments 5

    # Dịch vụ từ xa: phải bật --allow-external sau khi kiểm tra quyền/bảo mật tài liệu
    export DEEPSEEK_API_KEY=...
    hanviet translate --workspace work/sach --provider deepseek --model deepseek-chat --allow-external --dry-run
    hanviet translate --workspace work/sach --provider deepseek --model deepseek-chat --allow-external --max-segments 0

Nhà cung cấp: `ollama`, `deepseek`, `qwen`, `openai`, `gemini`, `openrouter`, `openai-compatible --base-url ...`
(xem `.env.example`). Tên model là của nhà cung cấp; công cụ không mặc định model nào.

Kiểm định, đọc, sửa, duyệt:

    hanviet audit  --workspace work/sach --glossary examples/glossary.sample.json
    hanviet export --workspace work/sach --format html --out out/doc-song-ngu.html
    hanviet revise --workspace work/sach --segment <ID> --text "Câu sửa" --reviewer "Lan" \
                   --reason "Sai số liệu 58 -> 85" --severity HIGH
    hanviet approve --workspace work/sach --segment <ID> --reviewer "Lan" --evidence "Đối chiếu bản gốc"

Xuất bản:

    hanviet export --workspace work/sach  --format epub --out out/sach.epub
    hanviet export --workspace work/sach  --format epub --bilingual --out out/sach-song-ngu.epub
    hanviet export --workspace work/sach  --format docx --out out/sach.docx
    hanviet export --workspace work/video --format srt  --out out/video.vi.srt

Sản phẩm không có dấu "nháp" trên từng trang; trạng thái duyệt được ghi **một lần, trung thực** ở trang bản quyền
(ví dụ "Bản dịch nháp: 120/300 đoạn đã được người duyệt"). Mỗi đoạn vẫn có mã neo ẩn trỏ về đoạn gốc.

## Tra cứu nghiên cứu tiếng Trung

    hanviet search "先天性巨结肠" --source openalex --limit 10 --library mylib
    hanviet library import cnki_export.ris --library mylib      # RIS / EndNote / NoteExpress
    hanviet library list --library mylib --query 巨结肠
    hanviet library link --library mylib --record <ID> --workspace work/paper1
    hanviet library export --library mylib --out refs.ris        # mở bằng Zotero/EndNote

- OpenAlex trả về cả tóm tắt và link truy cập mở (OA) nếu có.
- **CNKI/Wanfang/VIP/SinoMed**: công cụ không đăng nhập hay cào dữ liệu. Ai có quyền truy cập thì tự xuất trích dẫn
  (RIS/EndNote/NoteExpress) và tải PDF, rồi `library import` + `ingest` file PDF. File `.caj` cần đổi sang PDF trước.
- Mạng xã hội cần đăng nhập (Weibo, Zhihu, Xiaohongshu, WeChat bị robots.txt chặn): mở bằng trình duyệt của bạn,
  *Lưu trang (HTML)*, rồi `ingest` file đã lưu.

## Nguyên tắc

- **Truy vết**: mỗi đoạn có mã, vị trí trong file gốc (dòng, trang, khối, mốc thời gian phụ đề), SHA-256 nguồn;
  trang web được lưu bản chụp (`source_snapshot.html`) vì nội dung web thay đổi.
- **Không giả vờ chắc chắn**: kiểm định tự động chỉ là bằng chứng một phần; không cổng ngữ nghĩa/khoa học nào
  tự động "PASS". Xem [chính sách QA](docs/qa-policy.md).
- **Quyền và riêng tư**: chỉ gửi văn bản ra API khi bạn bật `--allow-external`; không vượt paywall, không cào hàng loạt,
  tôn trọng robots.txt. Bản dịch không xoá bản quyền của tác giả gốc.
- Không dùng bản dịch tài liệu y khoa để kết luận lâm sàng khi chưa đọc nguồn gốc.

## Viết thêm nguồn (plugin)

Một package Python bất kỳ có thể thêm connector qua entry point `hanviet_bridge.sources` — ví dụ API CNKI có
bản quyền của một trường, trình đọc file xuất Weibo, RSS. Xem [docs/connectors.md](docs/connectors.md).

## Lộ trình

Xem [ROADMAP.md](ROADMAP.md). Đóng góp: [CONTRIBUTING.md](CONTRIBUTING.md).

## English summary

HanViet Bridge ingests Chinese material (files, public web pages, saved pages, subtitles, CNKI/Wanfang citation
exports, plugin connectors), translates it to Vietnamese segment-by-segment with your chosen model (local Ollama or
remote APIs behind an explicit `--allow-external`), runs deterministic QA (numbers by value across locales, DOI,
citations, glossary, jurisdiction), keeps an append-only revision history and hash-bound approvals, and exports clean
EPUB3/DOCX/Markdown/SRT plus an offline bilingual review page. Every output passage links back to its exact source
passage.

## Ghi công

Cảm hứng quy trình (trung thành, tự nhiên, kiểm định nhiều cổng, truy vết) từ
[prompt dịch How To Live Better](https://thuongtin.notion.site/Prompt-d-ch-How-To-Live-Better-t-ti-ng-Trung-sang-ti-ng-Vi-t-41172ac96186819dae67c730db8d7152)
và [thuongtin/HowToLiveBetter](https://github.com/thuongtin/HowToLiveBetter) (CC BY 4.0). Mã nguồn được viết độc lập,
giấy phép MIT.

## Kiểm thử

    python3 -m unittest discover -s tests -v

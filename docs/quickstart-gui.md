# Bắt đầu với SinoBridge

SinoBridge giúp dịch sách hoặc tài liệu tiếng Trung sang tiếng Việt và tiếng Anh. Bạn dùng model/API key của mình. Ứng dụng lưu tài liệu trên máy đang chạy, không cần tạo tài khoản SinoBridge.

## Cài trên Mac

1. Cài Python 3.10 trở lên nếu máy chưa có.
2. Trên GitHub, chọn Code → Download ZIP rồi giải nén.
3. Mở thư mục scripts và nhấp đúp **Start SinoBridge.command**.
4. Lần đầu máy sẽ tải các thư viện cần thiết. Sau khi xong, giao diện mở trong trình duyệt.

macOS có thể cảnh báo khi chạy script tải từ Internet. Hãy kiểm tra file và nguồn tải trước khi cho phép chạy.

## Cài trên Windows

1. Cài Python 3.10 trở lên từ python.org.
2. Tải bản ZIP trên GitHub và giải nén.
3. Trong thư mục scripts, nhấp đúp **Start SinoBridge.bat**.
4. Lần đầu máy cài các thư viện cần thiết. Giao diện sẽ mở trong trình duyệt.

## Dịch tài liệu

1. Thả file EPUB, PDF, Word hoặc TXT vào ô chọn file.
2. Chọn tiếng Việt hoặc tiếng Anh và loại tài liệu.
3. Chọn dịch vụ AI, nhập tên model và API key bạn có. Nếu dùng Ollama, bạn cần cài sẵn model trên máy.
4. Xác nhận quyền gửi tài liệu đến dịch vụ AI (không cần với Ollama), rồi bấm **Dịch tài liệu**.
5. Chờ dịch xong hoặc dừng giữa chừng. Bạn có thể mở lại để dịch tiếp những đoạn còn lại.
6. Tải EPUB, Word, Markdown hoặc file HTML song ngữ.

**Chi phí:** SinoBridge không thu phí dịch. Dịch vụ AI có thể tính tiền API theo gói của bạn.

**Dữ liệu:** Tài liệu lưu ở thư mục .sinobridge/projects trong thư mục home. API key chỉ dùng trong bộ nhớ khi dịch, không được ghi ra file. Khi dùng model qua API, nội dung tài liệu được gửi đến nhà cung cấp đã chọn.

**Lưu ý:** Đây chưa phải ứng dụng cài đặt độc lập; máy vẫn cần Python. PDF dạng ảnh scan cần OCR trước. Bản dịch tự động có thể sai ở số liệu, tên riêng, bảng biểu và thuật ngữ chuyên môn. Kiểm tra nội dung quan trọng với bản gốc trước khi dùng. Việc xuất bản hoặc chia sẻ bản dịch phải tuân thủ quyền tác giả.

## Quick start in English

Install Python 3.10+, download and unzip the repository, then double-click **Start SinoBridge.command** on macOS or **Start SinoBridge.bat** on Windows (in the scripts folder). Drop in your document, choose English or Vietnamese, enter your own model and API key, then translate and download EPUB/Word or bilingual HTML. You can switch the interface language in the top-right corner.

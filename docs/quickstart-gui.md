# SinoBridge — 3 bước cho người chưa biết lập trình

SinoBridge là ứng dụng tự chạy trên máy tính, không có server lưu tài liệu và không cần tài khoản SinoBridge.

## macOS

1. Cài Python 3.10+ nếu máy chưa có.
2. Tải repository về máy (GitHub → Code → Download ZIP), giải nén.
3. Nhấp đúp vào **scripts/Start SinoBridge.command**. Lần đầu ứng dụng cài các thư viện cần thiết và cần Internet; các lần sau chỉ khởi động. Nếu macOS chưa cho chạy script tải từ Internet, dùng Terminal mở file sau khi xem nội dung và xác nhận bạn tin nguồn.
4. Trình duyệt mặc định mở giao diện SinoBridge.

## Windows

1. Cài Python 3.10+ từ python.org, bật mục Add Python to PATH nếu có.
2. Download ZIP và giải nén repository.
3. Nhấp đúp **scripts/Start SinoBridge.bat**. Lần đầu cài thư viện cần thiết qua pip.
4. Trình duyệt mặc định mở SinoBridge.

## Dịch

- Thả file sách EPUB/PDF/DOCX/TXT hoặc tài liệu vào giao diện, chọn **dịch sang Tiếng Việt hoặc English**.
- Chọn nhà cung cấp AI mà **bạn tự có API key và quyền truy cập**, nhập model ID và key; hoặc chọn Ollama nếu đã cài model trên máy.
- Tích chọn đồng ý gửi tài liệu tới dịch vụ ngoài (không cần khi dùng Ollama).
- Nhấn Bắt đầu dịch, xem tiến độ và tải EPUB/Word/bản song ngữ.

Đối với model qua API, nhà cung cấp có thể tính phí; SinoBridge không thu phí hay cấp key. Nếu máy đã có Ollama, phải tự tải model tương ứng trước.
Dữ liệu nằm trong ~/.sinobridge/projects. API key giữ trong RAM một tác vụ, không lưu vào dự án. Chỉ khi người dùng nhấn dịch thì nội dung mới được gửi ra dịch vụ model đã chọn.

## Giới hạn hiện tại

Đây là ứng dụng nguồn mở chạy local, **không phải chương trình cài đặt độc lập**: phải có Python lần đầu.
Bản dịch tự động có thể sai. PDF scan, bảng biểu và công thức cần kiểm tra thủ công.
Không tự phát hành bản dịch của sách có bản quyền.

## English (short)

Install Python 3.10+, download the repository ZIP, double-click `scripts/Start SinoBridge.command` (macOS) or
`scripts/Start SinoBridge.bat` (Windows). Drop in a document, choose English or Vietnamese, enter your own model and
API key, start translating, then download EPUB/Word or the bilingual review page. The interface language can be
switched in the top corner.

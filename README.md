# VietTranscribe — Phiên âm tiếng Việt trên Windows

Ứng dụng Python/Tkinter dùng faster-whisper để chuyển M4A, MP3, WAV, MP4, FLAC thành file TXT. Chạy CPU, không cần API trả phí.

## Cài đặt lần đầu

Mở PowerShell tại thư mục dự án, chạy:

    powershell -ExecutionPolicy Bypass -File .\install.ps1
    powershell -ExecutionPolicy Bypass -File .\run.ps1

Nếu vừa cài Python, phải đóng và mở lại PowerShell trước khi cài đặt.

## Cập nhật bản mới nhất

**Đợi phiên âm đang chạy hoàn thành, sau đó đóng phần mềm** trước khi cập nhật:

    cd "$env:USERPROFILE\Downloads\VietTranscribe"
    git pull origin main
    powershell -ExecutionPolicy Bypass -File .\run.ps1

Nếu từng sửa code cục bộ, hãy sao lưu các thay đổi trước khi cập nhật.

## Chức năng

1. Chọn file và thư mục kết quả.
2. Chọn mô hình AI (mặc định small), ngôn ngữ (mặc định vi).
3. Nhấn BẮT ĐẦU PHIÊN ÂM.
4. Xem phần trăm tiến độ dựa trên thời lượng file, tốc độ xử lý so với thời gian thực (ví dụ 0.5x), và ước tính thời gian còn lại.
5. Sau **mỗi đoạn nhận dạng**, ứng dụng ghi nội dung vào file <tên file>.partial.txt. File này vẫn tồn tại khi dừng giữa chừng hoặc bị lỗi.
6. Khi nhận dạng xong, bản nháp được chuyển thành <tên file>.txt, đây là kết quả chính thức.
7. Nút DỪNG VÀ GIỮ VĂN BẢN yêu cầu dừng ở ranh giới giữa các đoạn; thao tác có thể không diễn ra ngay lập tức.

**Lưu ý:** File .partial.txt là văn bản chưa hoàn chỉnh, không phải checkpoint để tiếp tục phiên âm từ vị trí trước. Khi chạy lại cùng file, sẽ có cảnh báo trước khi ghi đè bản nháp cũ. Ước tính thời gian còn lại chỉ mang tính tham khảo và có thể thay đổi.

Lần đầu cần Internet để tải mô hình; các lần sau có thể chạy offline. Độ chính xác phụ thuộc chất lượng âm thanh và mô hình được chọn.

## Bảo mật

Không commit file ghi âm cá nhân vào GitHub. Repository hiện đang ở chế độ Public.

## Kiểm tra cú pháp

    .\.venv\Scripts\python.exe -m py_compile .\app.py

Mã nguồn chưa được kiểm thử đầy đủ trên mọi máy Windows.

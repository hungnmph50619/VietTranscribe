# VietTranscribe — Chuyển âm thanh thành văn bản tiếng Việt

Ứng dụng giao diện Windows sử dụng [faster-whisper](https://github.com/SYSTRAN/faster-whisper) (MIT). Phiên âm M4A, MP3, WAV, MP4, FLAC sang TXT, SRT, VTT, JSON bằng CPU; không cần API trả phí.

## Cài đặt

Yêu cầu Windows 10/11, mạng Internet khi cài đặt và tải mô hình lần đầu.

Mở PowerShell và chạy:

```powershell
winget install --id Python.Python.3.11 --exact
git clone https://github.com/hungnmph50619/VietTranscribe.git
cd VietTranscribe
powershell -ExecutionPolicy Bypass -File .\install.ps1
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Nếu vừa cài Python, đóng và mở lại PowerShell trước khi chạy script cài đặt. Nếu Git chưa được cài, chạy `winget install --id Git.Git -e` trước khi clone.

## Cách dùng

1. Chọn file ghi âm cần phiên âm.
2. Chọn thư mục xuất kết quả.
3. Chọn mô hình `small` (mặc định) và ngôn ngữ `vi`.
4. Nhấn **BẮT ĐẦU PHIÊN ÂM**.
5. Mở thư mục kết quả và lấy TXT hoặc SRT gửi vào ChatGPT.

Mô hình `base` nhanh hơn trên máy yếu, `medium` chính xác hơn nhưng thường chậm hơn. Lần đầu mô hình được tải từ Internet; sau đó phiên âm trên máy. Kết quả có thể sai ở những đoạn âm thanh nhiễu hoặc nhiều người nói cùng lúc.

## Bảo mật

Không đưa file ghi âm riêng tư lên GitHub. Dự án có `.gitignore` để loại trừ các đuôi tệp âm thanh và phụ đề thông dụng. Repository hiện do chủ tài khoản đặt Public.

## Tình trạng

Mã nguồn Python đã qua kiểm tra cú pháp, chưa kiểm thử đầy đủ trên Windows thực.

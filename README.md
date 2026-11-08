# VietTranscribe — Phiên âm tiếng Việt thành TXT (Windows)

Ứng dụng chạy trên CPU với **faster-whisper**, không cần API key hoặc phí phiên âm. Hỗ trợ M4A, MP3, WAV, MP4, FLAC và các định dạng mà PyAV đọc được.

## Bản sửa giao diện trên Windows DPI cao

Nếu ở phiên bản cũ phần danh sách ghi âm quá cao và che mất nút **Bắt đầu**, hãy cập nhật và mở lại chương trình. Giao diện mới giới hạn chiều cao danh sách theo số file, chuẩn hóa tỷ lệ hiển thị và cuộn phần nội dung khi cửa sổ không đủ cao.

```powershell
cd "$env:USERPROFILE\Downloads\VietTranscribe"
git pull origin main
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Việc đổi giao diện **không xóa** các thư mục checkpoint hay file TXT đã xuất. Nếu đang chạy phiên âm, nên hoàn thành hoặc dừng sau đoạn hiện tại trước khi cập nhật.

## Giao diện mới (CustomTkinter)

- Bố cục sáng, gọn, kiểu Windows 11: danh sách file, thiết lập mô hình, tiến độ và nút hành động.
- **Chọn nhiều file** bằng nút `+ Thêm file`, hoặc thử **kéo thả file** vào cửa sổ (tự tắt khi TkDND không khả dụng).
- Từng file có trạng thái **Chờ xử lý / Đang xử lý / Hoàn thành / Lỗi / Tạm dừng**.
- Chọn một file rồi bấm **Mở TXT** để xem văn bản đã hoàn thành bằng chương trình mặc định.
- **Chi tiết xử lý** mặc định được thu gọn, chỉ mở khi cần xem nhật ký.
- Giữ nguyên các cơ chế xử lý CPU, chia đoạn 10 phút, tự lưu và tiếp tục checkpoint.
- Cần cài thư viện giao diện mới **một lần** khi nâng cấp từ bản Tkinter cũ.

**Cập nhật sau khi đóng VietTranscribe:**

```powershell
cd "$env:USERPROFILE\Downloads\VietTranscribe"
git pull origin main
powershell -ExecutionPolicy Bypass -File .\install.ps1
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Từ các lần cập nhật giao diện sau, nếu `requirements.txt` không đổi thì không cần chạy lại `install.ps1`.

## Tính năng

- Chọn **nhiều file**; chạy tuần tự trong hàng đợi, dùng chung một mô hình AI. Danh sách file được giữ lại trên máy khi đóng và mở lại phần mềm; file lỗi không chặn toàn bộ hàng đợi.
- Giải mã âm thanh theo luồng, chia mỗi file thành các đoạn **10 phút** với khoảng chồng lấn 2 giây ở đầu đoạn sau để giảm rủi ro mất lời tại điểm cắt.
- Sau **mỗi đoạn hoàn tất**, ghi `parts/00000.txt`, `parts/00001.txt`, ... và `manifest.json` bằng thao tác thay thế file an toàn. Tạo `van_ban_dang_xu_ly.partial.txt` liên tục.
- Nếu dừng, mất điện hoặc máy thoát bất ngờ, bấm **BẮT ĐẦU / TIẾP TỤC** để chương trình **bỏ qua các đoạn đã lưu hợp lệ** và phiên âm phần còn lại. Đoạn đang xử lý dở có thể phải làm lại.
- Khi đã hoàn thành toàn bộ file, xuất **`van_ban_day_du.txt`**.
- Hiển thị tiến độ theo số đoạn, tốc độ và thời gian còn lại *ước tính*. Trong lúc chạy một đoạn 10 phút, % có thể đứng yên đến khi đoạn hoàn thành.
- Mỗi file và cấu hình tạo một thư mục kết quả riêng, tránh ghi đè khi trùng tên.

## Chọn mô hình và chế độ tốc độ

Các mô hình được xếp theo **xu hướng** tốc độ chạy CPU, không phải số đo được bảo đảm cho mọi máy:

| Mô hình | Xếp hạng tốc độ | Ưu điểm | Hạn chế |
| --- | --- | --- | --- |
| `tiny` | Nhanh nhất | Nhẹ, chạy trên máy yếu | Dễ sai / bỏ sót tiếng Việt |
| `base` | Rất nhanh | Thích hợp ghi âm rõ tiếng | Nhận dạng thuật ngữ kém hơn mô hình lớn |
| `small` | Trung bình — khuyên dùng | Cân bằng độ chính xác và tốc độ | Chậm hơn base |
| `medium` | Chậm | Thường chính xác hơn ở âm thanh khó | Tốn CPU và RAM |
| `large-v3` | Chậm nhất | Năng lực nhận dạng lớn | Rất nặng nếu chỉ có CPU |

Chế độ phiên âm sử dụng thuật toán beam search:

- **Nhanh**: `beam_size=1`, ưu tiên tốc độ, có thể giảm độ chính xác.
- **Cân bằng**: `beam_size=3`, là lựa chọn mặc định.
- **Chính xác hơn**: `beam_size=5`, có thể chậm hơn, không bảo đảm mọi file đều chính xác hơn.

Cấu hình mặc định: `small + Cân bằng`. Chế độ và tên mô hình được giữ lại khi mở lại ứng dụng. **Thay đổi mô hình hoặc chế độ tạo checkpoint riêng**, không sử dụng lại kết quả của cấu hình khác. Chế độ nhanh có thể giúp tiết kiệm thời gian CPU, nhưng không bảo đảm tốc độ tăng theo tỉ lệ beam size.

## Cập nhật Windows từ repository

**Để bản ghi đang chạy hoàn thành và đóng VietTranscribe trước khi cập nhật.** Mở PowerShell:

```powershell
cd "$env:USERPROFILE\Downloads\VietTranscribe"
git pull origin main
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Nếu chưa cài đặt lần nào, chạy:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
powershell -ExecutionPolicy Bypass -File .\run.ps1
```

Máy mới cần Python 3.11, có thể được script cài qua winget. Nếu vừa cài Python, hãy mở lại PowerShell trước khi chạy lại `install.ps1`. Không cần tải GitHub ZIP nếu đã clone repository trước đó.

## Sử dụng

1. Nhấn **Thêm file...** và chọn một hoặc nhiều file ghi âm.
2. Chọn **Thư mục xuất kết quả**.
3. Mô hình `small`, chế độ `Cân bằng`, ngôn ngữ `vi`, VAD bật là lựa chọn mặc định. Có thể chọn `base + Nhanh` nếu ưu tiên xử lý nhanh.
4. Nhấn **BẮT ĐẦU / TIẾP TỤC**. Sau khi mở lại phần mềm, danh sách file trước đó được khôi phục; nhấn nút này để tiếp tục các checkpoint đã hoàn thành.
5. Có thể nhấn **DỪNG SAU ĐOẠN HIỆN TẠI**; dữ liệu các đoạn hoàn thành vẫn được giữ.
6. Sau khi hoàn thành, mở thư mục `<tên file>__<mã>/van_ban_day_du.txt` để lấy kết quả. Nếu chưa xong, dùng `van_ban_dang_xu_ly.partial.txt` để đọc phần đã có.

**Lưu ý:** Tính năng tiếp tục dựa vào đường dẫn file, kích thước, thời điểm sửa đổi và cấu hình nhận dạng. Nếu bạn thay đổi file gốc hoặc mô hình, chương trình tạo công việc mới để bảo vệ kết quả cũ. Không xóa thư mục `parts` hoặc `manifest.json` nếu muốn tiếp tục. Phần mềm phải giải mã lại âm thanh khi tiếp tục, nhưng **không phải chạy lại suy luận AI cho các đoạn hoàn thành**.

## Giới hạn và bảo mật

- Văn bản có thể sai tại ranh giới hai đoạn, ở đoạn nhiễu hoặc lời nói chồng nhau. Phần chồng lấn 2 giây giúp giảm rủi ro nhưng không bảo đảm loại bỏ hoàn toàn lặp hoặc thiếu từ.
- CPU có thể chạy chậm với mô hình lớn. Chọn `base` nếu cần nhẹ hơn, `small` nếu ưu tiên chất lượng.
- Không đưa file ghi âm riêng tư vào repository Public.
- Lần đầu cần Internet để tải mô hình, sau đó nhận dạng chạy tại máy.

## Kiểm thử

```powershell
py -3.11 -m py_compile app.py transcription.py
py -3.11 -m unittest discover -s tests -v
```

Kiểm thử tự động mô phỏng dừng, khôi phục, kiểm tra checksum, trùng tên file và xuất Unicode. Chưa khẳng định đã kiểm thử phiên âm thực tế mọi định dạng trên Windows.

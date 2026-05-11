# Video Translator Desktop

Desktop app **dịch âm thanh trên video → lồng tiếng Việt** hoàn toàn tự động.

```
input.mp4  ──►  app  ──►  output.mp4 (audio đã được lồng tiếng Việt)
```

## Pipeline

1. **Tách audio** từ video bằng `ffmpeg`
2. **Nhận dạng + dịch** bằng [Soniox](https://soniox.com) (`stt-async-v4`, one-way translation → `vi`)
3. **Tách câu** từ tokens dựa trên dấu câu / khoảng lặng
4. **Tạo giọng đọc tiếng Việt** cho từng câu bằng [Edge TTS](https://github.com/rany2/edge-tts) (miễn phí)
5. **Ghép timeline** đặt từng đoạn TTS đúng vị trí thời gian
6. **Ghép video** gốc với audio tiếng Việt → file MP4 output

## Yêu cầu hệ thống

- Python ≥ 3.10
- `ffmpeg` (tự động cài qua `imageio-ffmpeg`, hoặc tự cài và đảm bảo có trong PATH)
- Một [Soniox API key](https://console.soniox.com) (miễn phí cho sử dụng nhỏ)

## Cài đặt

### Chạy từ source

```bash
git clone https://github.com/ann88fgh/video-translator-desktop.git
cd video-translator-desktop

# Tạo virtual env
python -m venv .venv
source .venv/bin/activate          # Linux/macOS
# .venv\Scripts\activate            # Windows PowerShell

# Cài dependencies
pip install -e ".[dev]"

# Cấu hình Soniox API key
cp .env.example .env
# rồi mở .env và điền SONIOX_API_KEY=...
# (cũng có thể nhập key trong cửa sổ Settings sau khi mở app)

# Chạy app
python -m video_translator
```

### Build file .exe (Windows)

```powershell
pip install pyinstaller
pyinstaller build.spec
# kết quả: dist/video-translator.exe (one-file)
```

## Cách dùng

1. Mở app → hộp thoại GUI hiện ra
2. Nếu chưa cấu hình → bấm **⚙ Settings** → dán Soniox API key
3. Kéo file video `.mp4` (hoặc `.mkv` / `.webm` / `.mov`) vào ô lớn ở giữa
4. Chọn giọng đọc tiếng Việt (mặc định: **Hoài My** — nữ)
5. Bấm **Bắt đầu lồng tiếng**
6. Theo dõi tiến trình. Khi xong, app hiện nút **Mở thư mục output**

## Công nghệ

| Thành phần | Công nghệ | Lý do |
| --- | --- | --- |
| GUI | [customtkinter](https://github.com/TomSchimansky/CustomTkinter) | Modern, không cần Qt/Electron |
| Audio extract / mux | [ffmpeg](https://ffmpeg.org) (qua `imageio-ffmpeg`) | Standard de facto |
| Speech-to-Text + dịch | [Soniox `stt-async-v4`](https://soniox.com) | Realtime + 60+ ngôn ngữ + dịch chính xác |
| Text-to-Speech | [edge-tts](https://github.com/rany2/edge-tts) | Miễn phí, giọng tiếng Việt rất tự nhiên |

## Roadmap

- [ ] Hỗ trợ video không có audio (skip dub, copy nguyên file)
- [ ] Burn phụ đề song ngữ vào video
- [ ] Trộn audio gốc nhỏ + tiếng Việt to (chế độ documentary)
- [ ] Hỗ trợ batch nhiều file
- [ ] Voice cloning (dùng giọng người nói gốc bằng ElevenLabs / OpenVoice)

## License

MIT — xem [LICENSE](./LICENSE).

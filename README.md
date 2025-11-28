# 🎧 Super English Pro (Groq Edition)

**Super English Pro** là phần mềm học tiếng Anh thông minh trên Desktop, kết hợp thuật toán **Lặp lại ngắt quãng (SRS)** với sức mạnh của **Groq AI (Llama 3)** để tạo ra trải nghiệm học tập cá nhân hóa cực cao.

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![AI](https://img.shields.io/badge/AI-Groq%20Llama3-orange)
![Database](https://img.shields.io/badge/Database-SQLite-green)

## ✨ Tính Năng Đột Phá

1.  **🧠 Groq AI Integration:** Sử dụng model `openai/gpt-oss-120b` để dịch và giải thích ngữ cảnh sử dụng của câu (thay vì chỉ dịch nghĩa đen).
2.  **🔒 Smart Review Logic:**
    * Khi ôn tập, nghĩa tiếng Việt sẽ bị **ẨN**.
    * Chỉ khi bạn nghe và gõ/nói ĐÚNG, AI mới hiện nghĩa và giải thích.
3.  **💾 Database Storage (Peewee):** Dữ liệu lưu trong SQLite (`english_pro.db`), an toàn, không lo mất file, hỗ trợ hàng ngàn câu.
4.  **🗣️ AI Neural Voice:** Giọng đọc Edge TTS tự nhiên, stream trực tiếp từ RAM (Zero-latency, No temporary files).
5.  **🎙️ Luyện Nói (Shadowing):** Tích hợp Google Voice để chấm điểm phát âm của bạn.
6.  **📊 SRS Algorithm:** Tự động tính toán ngày ôn lại (1, 2, 4, 8... ngày) dựa trên độ nhớ.

## 🛠️ Cài Đặt

### 1. Yêu cầu
* Python 3.8 trở lên.
* API Key miễn phí từ [Groq Console](https://console.groq.com).

### 2. Cài đặt thư viện
Mở Terminal tại thư mục dự án và chạy:

```bash
pip install customtkinter edge-tts pygame peewee groq deep-translator SpeechRecognition
import customtkinter as ctk
import threading
import pyaudio
import wave
import os
import tempfile
import difflib
from groq import Groq

# --- CẤU HÌNH AUDIO & GROQ ---
AUDIO_RATE = 16000     # Chuẩn của Groq
AUDIO_CHANNELS = 1     # Mono
AUDIO_CHUNK = 1024

# Cấu hình giao diện
ctk.set_appearance_mode("Dark")  # Chế độ tối
ctk.set_default_color_theme("blue")  # Màu chủ đạo

class EnglishTutorApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Cấu hình cửa sổ
        self.title("Groq AI English Tutor")
        self.geometry("500x650")
        self.resizable(False, False)

        # Biến trạng thái
        self.is_recording = False
        self.frames = []
        self.api_key = ""
        
        # Data mẫu
        self.sentences = [
            "The quick brown fox jumps over the lazy dog.",
            "I am learning to speak English with confidence.",
            "Artificial Intelligence helps us learn faster.",
            "Where is the nearest coffee shop?",
            "Practice makes perfect."
        ]

        self.setup_ui()

    def setup_ui(self):
        # 1. Tiêu đề & API Key
        self.lbl_title = ctk.CTkLabel(self, text="LUYỆN NÓI TIẾNG ANH", font=("Arial", 20, "bold"))
        self.lbl_title.pack(pady=(20, 10))

        self.entry_api = ctk.CTkEntry(self, placeholder_text="Nhập Groq API Key (gsk_...)", width=400, show="*")
        self.entry_api.pack(pady=5)

        # 2. Chọn câu mẫu
        self.lbl_select = ctk.CTkLabel(self, text="Chọn câu mẫu:", text_color="#aaa")
        self.lbl_select.pack(pady=(15, 5))

        self.combo_sentences = ctk.CTkComboBox(self, values=self.sentences, width=400, command=self.update_target_text)
        self.combo_sentences.set(self.sentences[0])
        self.combo_sentences.pack(pady=5)

        # Hiển thị câu mẫu (To, Rõ)
        self.box_target = ctk.CTkTextbox(self, width=400, height=80, font=("Arial", 18), text_color="#4CAF50", fg_color="#2b2b2b")
        self.box_target.insert("0.0", self.sentences[0])
        self.box_target.configure(state="disabled") # Không cho sửa
        self.box_target.pack(pady=10)

        # 3. Nút Ghi âm
        self.btn_record = ctk.CTkButton(self, text="🎙️ BẮT ĐẦU GHI ÂM", width=200, height=50, 
                                        font=("Arial", 14, "bold"), fg_color="#1f6aa5", hover_color="#144870",
                                        command=self.toggle_recording)
        self.btn_record.pack(pady=20)

        self.lbl_status = ctk.CTkLabel(self, text="Sẵn sàng", text_color="gray")
        self.lbl_status.pack(pady=0)

        # 4. Khu vực kết quả
        self.frame_result = ctk.CTkFrame(self, width=400)
        self.frame_result.pack(pady=20, padx=20, fill="x")

        ctk.CTkLabel(self.frame_result, text="Bạn đã nói:", font=("Arial", 12, "bold")).pack(pady=(10, 0))
        
        self.txt_user_input = ctk.CTkTextbox(self.frame_result, height=60, text_color="#ddd")
        self.txt_user_input.pack(pady=5, padx=10, fill="x")
        self.txt_user_input.configure(state="disabled")

        # Hàng hiển thị điểm số
        self.stats_frame = ctk.CTkFrame(self.frame_result, fg_color="transparent")
        self.stats_frame.pack(pady=10)

        self.lbl_score = ctk.CTkLabel(self.stats_frame, text="Điểm số: --", font=("Arial", 14, "bold"))
        self.lbl_score.pack(side="left", padx=20)

        self.lbl_confidence = ctk.CTkLabel(self.stats_frame, text="Chất lượng âm: --", font=("Arial", 14))
        self.lbl_confidence.pack(side="right", padx=20)

        # Feedback text
        self.lbl_feedback = ctk.CTkLabel(self, text="", font=("Arial", 18, "bold"))
        self.lbl_feedback.pack(pady=10)

    def update_target_text(self, choice):
        self.box_target.configure(state="normal")
        self.box_target.delete("0.0", "end")
        self.box_target.insert("0.0", choice)
        self.box_target.configure(state="disabled")

    def toggle_recording(self):
        # Kiểm tra API Key
        self.api_key = self.entry_api.get().strip()
        if not self.api_key:
            self.lbl_status.configure(text="❌ Lỗi: Vui lòng nhập API Key!", text_color="#FF5555")
            return

        if not self.is_recording:
            # Bắt đầu ghi âm
            self.is_recording = True
            self.btn_record.configure(text="⏹️ DỪNG GHI ÂM", fg_color="#d32f2f", hover_color="#9a0007")
            self.lbl_status.configure(text="Đang ghi âm... (Hãy đọc to câu trên)", text_color="#FFA500")
            
            # Xóa kết quả cũ
            self.update_textbox(self.txt_user_input, "")
            self.lbl_score.configure(text="Điểm số: --", text_color="white")
            self.lbl_confidence.configure(text="Chất lượng âm: --", text_color="white")
            self.lbl_feedback.configure(text="")

            # Chạy thread ghi âm
            threading.Thread(target=self.run_recording, daemon=True).start()
        else:
            # Dừng ghi âm
            self.is_recording = False
            self.btn_record.configure(state="disabled", text="⏳ Đang xử lý...")
            self.lbl_status.configure(text="Đang gửi dữ liệu lên Groq...", text_color="#4CAF50")

    def run_recording(self):
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16, channels=AUDIO_CHANNELS,
                        rate=AUDIO_RATE, input=True, frames_per_buffer=AUDIO_CHUNK)
        
        self.frames = []
        while self.is_recording:
            data = stream.read(AUDIO_CHUNK)
            self.frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        # Lưu file tạm và gọi API
        self.save_and_process_audio()

    def save_and_process_audio(self):
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        wf = wave.open(temp_file.name, 'wb')
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(2) # 16 bit
        wf.setframerate(AUDIO_RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()

        # Chuyển sang xử lý API (trên luồng khác để không đơ UI)
        threading.Thread(target=self.run_api_analysis, args=(temp_file.name,), daemon=True).start()

    def run_api_analysis(self, file_path):
        try:
            client = Groq(api_key=self.api_key)
            target_text = self.combo_sentences.get()

            with open(file_path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=file,
                    model="whisper-large-v3-turbo",
                    language="en",
                    prompt=target_text, # Context
                    response_format="verbose_json",
                    temperature=0.0
                )

            # Phân tích kết quả
            user_text = transcription.text.strip()
            
            # Tính Confidence (avg_logprob)
            avg_logprob = 0
            if hasattr(transcription, 'segments') and transcription.segments:
                probs = [seg['avg_logprob'] for seg in transcription.segments]
                avg_logprob = sum(probs) / len(probs) if probs else 0

            # Tính điểm giống nhau
            matcher = difflib.SequenceMatcher(None, target_text.lower().strip(), user_text.lower().strip())
            score = matcher.ratio() * 100

            # Cập nhật UI (phải dùng self.after để thread-safe trong Tkinter)
            self.after(0, self.display_results, user_text, score, avg_logprob)

        except Exception as e:
            self.after(0, lambda: self.lbl_status.configure(text=f"Lỗi: {str(e)}", text_color="#FF5555"))
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            self.after(0, self.reset_button)

    def display_results(self, text, score, logprob):
        self.update_textbox(self.txt_user_input, text)
        self.lbl_status.configure(text="Hoàn tất!", text_color="gray")

        # Màu sắc điểm số
        score_color = "#4CAF50" if score > 85 else "#FFC107" if score > 60 else "#FF5555"
        self.lbl_score.configure(text=f"Điểm số: {score:.1f}%", text_color=score_color)

        # Màu sắc confidence
        conf_text = "Rõ ràng"
        conf_color = "#4CAF50"
        if logprob < -0.4: conf_text, conf_color = "Trung bình", "#FFC107"
        if logprob < -0.8: conf_text, conf_color = "Kém/Ồn", "#FF5555"
        
        self.lbl_confidence.configure(text=f"Chất lượng âm: {conf_text} ({logprob:.2f})", text_color=conf_color)

        # Feedback
        if score > 90 and logprob > -0.5:
            self.lbl_feedback.configure(text="TUYỆT VỜI! 🌟", text_color="#4CAF50")
        elif score > 70:
            self.lbl_feedback.configure(text="KHÁ TỐT! Cố gắng nói rõ hơn.", text_color="#FFC107")
        else:
            self.lbl_feedback.configure(text="CHƯA ĐẠT. Thử lại nhé! ❌", text_color="#FF5555")

    def reset_button(self):
        self.btn_record.configure(state="normal", text="🎙️ BẮT ĐẦU GHI ÂM", fg_color="#1f6aa5")

    def update_textbox(self, textbox, content):
        textbox.configure(state="normal")
        textbox.delete("0.0", "end")
        textbox.insert("0.0", content)
        textbox.configure(state="disabled")

if __name__ == "__main__":
    app = EnglishTutorApp()
    app.mainloop()
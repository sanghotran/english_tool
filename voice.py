import sys
import os
import wave
import tempfile
import difflib
import pyaudio
from groq import Groq
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QLabel, QPushButton, QComboBox, QTextEdit, 
                             QLineEdit, QMessageBox, QProgressBar, QHBoxLayout)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QFont, QIcon

# --- CẤU HÌNH GROQ & AUDIO ---
AUDIO_RATE = 16000     # Groq chuẩn hóa về 16kHz
AUDIO_CHANNELS = 1     # Mono
AUDIO_CHUNK = 1024

# --- LUỒNG GHI ÂM (Worker Thread) ---
class RecorderThread(QThread):
    finished_recording = pyqtSignal(str) # Gửi đường dẫn file khi xong

    def __init__(self):
        super().__init__()
        self.is_recording = False
        self.frames = []

    def run(self):
        self.is_recording = True
        p = pyaudio.PyAudio()
        stream = p.open(format=pyaudio.paInt16,
                        channels=AUDIO_CHANNELS,
                        rate=AUDIO_RATE,
                        input=True,
                        frames_per_buffer=AUDIO_CHUNK)
        
        self.frames = []
        while self.is_recording:
            data = stream.read(AUDIO_CHUNK)
            self.frames.append(data)

        stream.stop_stream()
        stream.close()
        p.terminate()

        # Lưu file WAV tạm
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        wf = wave.open(temp_file.name, 'wb')
        wf.setnchannels(AUDIO_CHANNELS)
        wf.setsampwidth(p.get_sample_size(pyaudio.paInt16))
        wf.setframerate(AUDIO_RATE)
        wf.writeframes(b''.join(self.frames))
        wf.close()

        self.finished_recording.emit(temp_file.name)

    def stop(self):
        self.is_recording = False

# --- LUỒNG XỬ LÝ API (Worker Thread) ---
class AnalyzerThread(QThread):
    result_ready = pyqtSignal(str, float, float) # Text, Score, Confidence
    error_occurred = pyqtSignal(str)

    def __init__(self, api_key, audio_path, target_sentence):
        super().__init__()
        self.api_key = api_key
        self.audio_path = audio_path
        self.target_sentence = target_sentence

    def run(self):
        try:
            client = Groq(api_key=self.api_key)
            
            with open(self.audio_path, "rb") as file:
                # Gọi API theo đúng tài liệu kỹ thuật
                transcription = client.audio.transcriptions.create(
                    file=file,
                    model="whisper-large-v3-turbo", 
                    language="en",
                    prompt=self.target_sentence, # Context giúp nhận diện tốt hơn
                    response_format="verbose_json",
                    temperature=0.0
                )

            user_text = transcription.text.strip()
            
            # Tính Confidence (avg_logprob)
            avg_logprob = 0
            if hasattr(transcription, 'segments') and transcription.segments:
                probs = [seg['avg_logprob'] for seg in transcription.segments]
                avg_logprob = sum(probs) / len(probs) if probs else 0

            # Tính điểm giống nhau (Similarity Score)
            matcher = difflib.SequenceMatcher(None, self.target_sentence.lower().strip(), user_text.lower().strip())
            score = matcher.ratio() * 100

            self.result_ready.emit(user_text, score, avg_logprob)

        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            # Xóa file tạm sau khi gửi xong
            if os.path.exists(self.audio_path):
                os.remove(self.audio_path)

# --- GIAO DIỆN CHÍNH (GUI) ---
class EnglishTutorApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Groq English Tutor - Luyện Nói Tiếng Anh")
        self.setGeometry(100, 100, 500, 650)
        self.setStyleSheet("background-color: #2b2b2b; color: #ffffff;")

        # Data mẫu
        self.sentences = [
            "The quick brown fox jumps over the lazy dog.",
            "I would like to improve my English pronunciation.",
            "Artificial Intelligence is changing the world.",
            "Can you recommend a good restaurant nearby?",
            "Consistency is the key to success."
        ]

        self.initUI()
        self.recorder_thread = RecorderThread()
        self.recorder_thread.finished_recording.connect(self.process_audio)

    def initUI(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        layout.setSpacing(15)

        # 1. Nhập API Key
        lbl_api = QLabel("Groq API Key:")
        lbl_api.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        layout.addWidget(lbl_api)

        self.input_api = QLineEdit()
        self.input_api.setPlaceholderText("Nhập API Key của bạn (gsk_...)")
        self.input_api.setStyleSheet("padding: 8px; border-radius: 5px; background-color: #3d3d3d; border: 1px solid #555;")
        self.input_api.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(self.input_api)

        # 2. Chọn câu mẫu
        lbl_select = QLabel("Chọn câu mẫu để luyện:")
        layout.addWidget(lbl_select)

        self.combo_sentences = QComboBox()
        self.combo_sentences.addItems(self.sentences)
        self.combo_sentences.setStyleSheet("padding: 8px; background-color: #3d3d3d; border: 1px solid #555;")
        self.combo_sentences.currentIndexChanged.connect(self.update_target_display)
        layout.addWidget(self.combo_sentences)

        # Hiển thị câu mẫu to rõ
        self.lbl_target = QLabel(self.sentences[0])
        self.lbl_target.setWordWrap(True)
        self.lbl_target.setStyleSheet("font-size: 18px; color: #4CAF50; font-weight: bold; margin: 10px 0;")
        self.lbl_target.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.lbl_target)

        # 3. Nút Ghi âm
        self.btn_record = QPushButton("🎙️ BẮT ĐẦU GHI ÂM")
        self.btn_record.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_record.setStyleSheet("""
            QPushButton {
                background-color: #2196F3; color: white; border-radius: 8px; padding: 15px; font-size: 14px; font-weight: bold;
            }
            QPushButton:hover { background-color: #1976D2; }
        """)
        self.btn_record.clicked.connect(self.toggle_recording)
        layout.addWidget(self.btn_record)

        # Trạng thái
        self.lbl_status = QLabel("Sẵn sàng")
        self.lbl_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_status.setStyleSheet("color: #aaa; font-style: italic;")
        layout.addWidget(self.lbl_status)

        # 4. Kết quả
        result_box = QWidget()
        result_box.setStyleSheet("background-color: #3d3d3d; border-radius: 10px;")
        result_layout = QVBoxLayout(result_box)

        result_layout.addWidget(QLabel("Bạn đã nói:"))
        self.txt_user_input = QTextEdit()
        self.txt_user_input.setReadOnly(True)
        self.txt_user_input.setFixedHeight(60)
        self.txt_user_input.setStyleSheet("background-color: #2b2b2b; border: none;")
        result_layout.addWidget(self.txt_user_input)

        # Điểm số và Confidence
        stats_layout = QHBoxLayout()
        self.lbl_score = QLabel("Điểm số: --")
        self.lbl_score.setStyleSheet("font-size: 14px; font-weight: bold;")
        stats_layout.addWidget(self.lbl_score)

        self.lbl_confidence = QLabel("Chất lượng âm: --")
        self.lbl_confidence.setStyleSheet("font-size: 14px;")
        stats_layout.addWidget(self.lbl_confidence)
        
        result_layout.addLayout(stats_layout)
        layout.addWidget(result_box)

        # Feedback text
        self.lbl_feedback = QLabel("")
        self.lbl_feedback.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_feedback.setStyleSheet("font-size: 16px; font-weight: bold; margin-top: 10px;")
        layout.addWidget(self.lbl_feedback)

        layout.addStretch()
        main_widget.setLayout(layout)

    def update_target_display(self):
        self.lbl_target.setText(self.combo_sentences.currentText())

    def toggle_recording(self):
        api_key = self.input_api.text().strip()
        if not api_key:
            QMessageBox.warning(self, "Thiếu API Key", "Vui lòng nhập Groq API Key trước!")
            return

        if not self.recorder_thread.isRunning():
            # Bắt đầu ghi âm
            self.recorder_thread.start()
            self.btn_record.setText("⏹️ DỪNG GHI ÂM")
            self.btn_record.setStyleSheet("background-color: #F44336; color: white; border-radius: 8px; padding: 15px; font-size: 14px; font-weight: bold;")
            self.lbl_status.setText("Đang ghi âm... (Hãy đọc câu trên)")
            self.txt_user_input.clear()
            self.lbl_feedback.clear()
        else:
            # Dừng ghi âm
            self.recorder_thread.stop()
            self.btn_record.setEnabled(False) # Khóa nút chờ xử lý
            self.lbl_status.setText("Đang dừng và lưu file...")

    def process_audio(self, file_path):
        self.lbl_status.setText("Đang gửi lên Groq AI để chấm điểm...")
        
        # Gọi Worker Thread xử lý API để không treo giao diện
        api_key = self.input_api.text().strip()
        target = self.lbl_target.text()
        
        self.analyzer = AnalyzerThread(api_key, file_path, target)
        self.analyzer.result_ready.connect(self.show_results)
        self.analyzer.error_occurred.connect(self.show_error)
        self.analyzer.start()

    def show_results(self, user_text, score, logprob):
        self.btn_record.setEnabled(True)
        self.btn_record.setText("🎙️ BẮT ĐẦU GHI ÂM")
        self.btn_record.setStyleSheet("background-color: #2196F3; color: white; border-radius: 8px; padding: 15px; font-size: 14px; font-weight: bold;")
        self.lbl_status.setText("Hoàn tất.")

        self.txt_user_input.setText(user_text)
        
        # Tô màu điểm số
        color = "#4CAF50" if score > 85 else "#FFC107" if score > 60 else "#F44336"
        self.lbl_score.setText(f"Điểm số: {score:.1f}%")
        self.lbl_score.setStyleSheet(f"font-size: 14px; font-weight: bold; color: {color};")

        # Đánh giá Confidence
        conf_text = "Rõ ràng"
        conf_color = "#4CAF50"
        if logprob < -0.4: conf_text, conf_color = "Trung bình", "#FFC107"
        if logprob < -0.8: conf_text, conf_color = "Khó nghe/Ồn", "#F44336"
        
        self.lbl_confidence.setText(f"Chất lượng âm: {conf_text} ({logprob:.2f})")
        self.lbl_confidence.setStyleSheet(f"font-size: 14px; color: {conf_color};")

        # Feedback tổng quát
        if score > 90 and logprob > -0.5:
            self.lbl_feedback.setText("TUYỆT VỜI! 🌟")
            self.lbl_feedback.setStyleSheet("color: #4CAF50; font-size: 20px; font-weight: bold;")
        elif score > 70:
            self.lbl_feedback.setText("KHÁ TỐT! Cố gắng nói rõ hơn.")
            self.lbl_feedback.setStyleSheet("color: #FFC107; font-size: 18px; font-weight: bold;")
        else:
            self.lbl_feedback.setText("CHƯA ĐẠT. Thử lại nhé! ❌")
            self.lbl_feedback.setStyleSheet("color: #F44336; font-size: 18px; font-weight: bold;")

    def show_error(self, message):
        self.btn_record.setEnabled(True)
        self.btn_record.setText("🎙️ BẮT ĐẦU GHI ÂM")
        self.btn_record.setStyleSheet("background-color: #2196F3; color: white; border-radius: 8px; padding: 15px; font-size: 14px; font-weight: bold;")
        self.lbl_status.setText("Lỗi!")
        QMessageBox.critical(self, "Lỗi API", f"Có lỗi xảy ra:\n{message}")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EnglishTutorApp()
    window.show()
    sys.exit(app.exec())
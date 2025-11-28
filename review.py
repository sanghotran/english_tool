import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import json
import os
import datetime
import difflib
import threading
import asyncio
import edge_tts
import pygame
import random
import io
from deep_translator import GoogleTranslator

# --- CẤU HÌNH ---
DATA_FILE = "data_english_pro.json"

# Cấu hình giao diện CustomTkinter
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class EnglishProApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Super English Dictation (Full Version)")
        self.geometry("900x700")

        # Khởi tạo âm thanh
        try:
            pygame.mixer.init()
        except Exception as e:
            print(f"Lỗi khởi tạo âm thanh: {e}")

        # Dữ liệu
        self.data = self.load_data()
        self.review_queue = []
        self.current_item = None

        # --- GIAO DIỆN CHÍNH (SIDEBAR + MAIN) ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar bên trái
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.lbl_logo = ctk.CTkLabel(self.sidebar, text="ENGLISH PRO", font=ctk.CTkFont(size=24, weight="bold"))
        self.lbl_logo.pack(pady=30)

        self.btn_tab_add = ctk.CTkButton(self.sidebar, text="📝 Thêm Câu Mới", height=40, command=self.show_add_frame)
        self.btn_tab_add.pack(pady=10, padx=20)

        self.btn_tab_review = ctk.CTkButton(self.sidebar, text="🎧 Ôn Tập (SRS)", height=40, command=self.show_review_frame)
        self.btn_tab_review.pack(pady=10, padx=20)
        
        self.lbl_stats = ctk.CTkLabel(self.sidebar, text=self.get_stats_text(), text_color="gray")
        self.lbl_stats.pack(side="bottom", pady=20)

        # 2. Khu vực nội dung chính
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Tạo sẵn các Frame con
        self.frame_add = self.create_add_frame()
        self.frame_review = self.create_review_frame()

        # Mặc định vào tab Ôn tập
        self.show_review_frame()

    # --- XỬ LÝ DỮ LIỆU ---
    def load_data(self):
        if not os.path.exists(DATA_FILE): return []
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return []

    def save_data(self):
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)
        self.lbl_stats.configure(text=self.get_stats_text())

    def get_stats_text(self):
        today = str(datetime.date.today())
        total = len(self.data)
        due = len([x for x in self.data if x.get('next_review', '2000-01-01') <= today])
        return f"Tổng câu: {total}\nCần ôn hôm nay: {due}"

    # --- AI VOICE (IN-MEMORY STREAMING) ---
    def play_audio_thread(self, text):
        if not text: return
        threading.Thread(target=self._run_async_tts, args=(text,)).start()

    def _run_async_tts(self, text):
        try:
            # Tạo event loop mới cho thread này
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._generate_and_play(text))
            loop.close()
        except Exception as e:
            print(f"Lỗi TTS System: {e}")

    async def _generate_and_play(self, text):
        try:
            voice = "en-US-AriaNeural" # Giọng nữ Mỹ tự nhiên
            communicate = edge_tts.Communicate(text, voice)
            
            # Hứng dữ liệu vào RAM
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]

            # Tạo file ảo
            virtual_file = io.BytesIO(audio_data)

            # Xử lý Pygame
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            
            try:
                pygame.mixer.music.unload() # Giải phóng bộ nhớ
            except AttributeError:
                pass

            pygame.mixer.music.load(virtual_file)
            pygame.mixer.music.play()

        except Exception as e:
            print(f"Lỗi TTS Streaming: {e}")

    # --- DỊCH THUẬT (AUTO TRANSLATE) ---
    # 1. Dịch Việt -> Anh (Để nhập liệu)
    def translate_thread(self):
        text_vi = self.entry_vi.get().strip()
        if not text_vi: return
        threading.Thread(target=self._run_translate, args=(text_vi,)).start()

    def _run_translate(self, text_vi):
        try:
            translated = GoogleTranslator(source='auto', target='en').translate(text_vi)
            self.after(0, lambda: self._append_translation(translated))
        except Exception as e:
            print(f"Lỗi dịch V-E: {e}")

    def _append_translation(self, text_en):
        current_content = self.txt_input.get("1.0", "end").strip()
        if current_content:
            self.txt_input.insert("end", "\n" + text_en)
        else:
            self.txt_input.insert("end", text_en)
        self.entry_vi.delete(0, "end")

    # 2. Dịch Anh -> Việt (Để hiện nghĩa khi ôn tập)
    def translate_meaning_thread(self, text_en):
        threading.Thread(target=self._run_translate_meaning, args=(text_en,)).start()

    def _run_translate_meaning(self, text_en):
        try:
            meaning = GoogleTranslator(source='en', target='vi').translate(text_en)
            self.after(0, lambda: self.lbl_meaning.configure(text=f"Nghĩa: {meaning}"))
        except:
            self.after(0, lambda: self.lbl_meaning.configure(text=""))

    # --- UI: THÊM CÂU ---
    def create_add_frame(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        
        lbl_vi = ctk.CTkLabel(frame, text="💡 Gợi ý (Nhập tiếng Việt):", font=("Arial", 14))
        lbl_vi.pack(pady=(0, 5), anchor="w")

        self.entry_vi = ctk.CTkEntry(frame, placeholder_text="Ví dụ: Tôi muốn uống cà phê", font=("Arial", 12))
        self.entry_vi.pack(fill="x", pady=(0, 5))
        self.entry_vi.bind("<Return>", lambda e: self.translate_thread())

        btn_translate = ctk.CTkButton(frame, text="Dịch sang Anh ⬇️", fg_color="#E65100", height=30,
                                      command=self.translate_thread)
        btn_translate.pack(anchor="e", pady=(0, 20))

        lbl_en = ctk.CTkLabel(frame, text="Danh sách câu tiếng Anh (Mỗi câu 1 dòng):", font=("Arial", 16, "bold"))
        lbl_en.pack(pady=(0, 10), anchor="w")

        self.txt_input = ctk.CTkTextbox(frame, height=300, font=("Arial", 13))
        self.txt_input.pack(fill="both", expand=True, pady=10)

        btn_save = ctk.CTkButton(frame, text="Lưu Vào Kho Dữ Liệu", fg_color="#2E7D32", height=45, font=("Arial", 14, "bold"),
                                 command=self.save_bulk_sentences)
        btn_save.pack(fill="x", pady=10)
        return frame

    def save_bulk_sentences(self):
        content = self.txt_input.get("1.0", "end").strip()
        if not content: return
        
        lines = content.split('\n')
        count = 0
        today = str(datetime.date.today())
        
        for line in lines:
            line = line.strip()
            if line:
                entry = {"text": line, "level": 0, "next_review": today}
                self.data.append(entry)
                count += 1
        
        self.save_data()
        self.txt_input.delete("1.0", "end")
        messagebox.showinfo("Thành công", f"Đã thêm {count} câu mới!")

    # --- UI: ÔN TẬP ---
    def create_review_frame(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        
        self.lbl_progress = ctk.CTkLabel(frame, text="Đang tải dữ liệu...", font=("Arial", 14))
        self.lbl_progress.pack(pady=10)

        # Nút nghe to
        self.btn_listen = ctk.CTkButton(frame, text="🔊 NGHE (F1)", font=("Arial", 16, "bold"), height=60,
                                        command=lambda: self.play_audio_thread(self.current_item['text'] if self.current_item else ""))
        self.btn_listen.pack(fill="x", pady=(20, 5))

        # Hiển thị nghĩa tiếng Việt
        self.lbl_meaning = ctk.CTkLabel(frame, text="", font=("Arial", 14, "italic"), text_color="#FFA726")
        self.lbl_meaning.pack(pady=(0, 20))

        # Ô nhập liệu
        self.entry_answer = ctk.CTkEntry(frame, font=("Arial", 18), height=50, placeholder_text="Gõ lại câu bạn nghe được...")
        self.entry_answer.pack(fill="x", pady=10)
        self.entry_answer.bind("<Return>", self.check_answer)
        self.entry_answer.bind("<F1>", lambda e: self.btn_listen.invoke())

        self.btn_check = ctk.CTkButton(frame, text="Kiểm tra (Enter)", command=self.check_answer)
        self.btn_check.pack(pady=5)

        # Kết quả
        self.lbl_feedback = ctk.CTkLabel(frame, text="", font=("Arial", 20, "bold"))
        self.lbl_feedback.pack(pady=15)

        # Diff Textbox
        self.txt_diff = ctk.CTkTextbox(frame, height=100, font=("Consolas", 16), fg_color="#2b2b2b")
        self.txt_diff.pack(fill="x", pady=5)
        self.txt_diff.tag_config("correct", foreground="#66BB6A")
        self.txt_diff.tag_config("wrong", foreground="#EF5350")
        self.txt_diff.tag_config("miss", foreground="#FFA726")

        self.btn_next = ctk.CTkButton(frame, text="Câu tiếp theo >>", state="disabled", height=40, command=self.next_card)
        self.btn_next.pack(pady=20)
        
        return frame

    # --- LOGIC ÔN TẬP ---
    def show_add_frame(self):
        self.frame_review.pack_forget()
        self.frame_add.pack(fill="both", expand=True)

    def show_review_frame(self):
        self.frame_add.pack_forget()
        self.frame_review.pack(fill="both", expand=True)
        self.start_session()

    def start_session(self):
        today = str(datetime.date.today())
        # Lọc câu SRS
        self.review_queue = [item for item in self.data if item.get('next_review', today) <= today]
        
        if not self.review_queue:
            self.lbl_progress.configure(text="Tuyệt vời! Hôm nay bạn đã hoàn thành tất cả.")
            self.lbl_meaning.configure(text="")
            self.entry_answer.configure(state="disabled")
            self.btn_listen.configure(state="disabled")
            self.txt_diff.delete("1.0", "end")
            self.current_item = None
        else:
            random.shuffle(self.review_queue)
            self.next_card()

    def next_card(self):
        if not self.review_queue:
            self.start_session()
            return

        self.current_item = self.review_queue[0]
        
        # Reset UI
        self.lbl_progress.configure(text=f"Số câu cần ôn: {len(self.review_queue)}")
        self.entry_answer.configure(state="normal")
        self.entry_answer.delete(0, "end")
        self.entry_answer.focus()
        self.lbl_feedback.configure(text="")
        self.txt_diff.delete("1.0", "end")
        self.lbl_meaning.configure(text="Đang tải nghĩa tiếng Việt...") 
        
        self.btn_next.configure(state="disabled")
        self.btn_listen.configure(state="normal")

        # Đọc & Dịch
        self.after(500, lambda: self.play_audio_thread(self.current_item['text']))
        self.translate_meaning_thread(self.current_item['text'])

    def check_answer(self, event=None):
        if not self.current_item: return

        # 1. Lấy dữ liệu & Chuẩn hóa
        raw_user = self.entry_answer.get().strip()
        raw_origin = self.current_item['text'].strip()

        # Thay thế dấu nháy cong bằng nháy thẳng
        user_clean = raw_user.replace("’", "'").replace("‘", "'").rstrip('.!?')
        origin_clean = raw_origin.replace("’", "'").replace("‘", "'").rstrip('.!?')

        # 2. So sánh Fuzzy
        matcher = difflib.SequenceMatcher(None, origin_clean.lower(), user_clean.lower())
        ratio = matcher.ratio()
        is_correct = ratio >= 0.9

        today = datetime.date.today()
        if is_correct:
            self.lbl_feedback.configure(text=f"✅ CHÍNH XÁC ({int(ratio*100)}%)", text_color="#66BB6A")
            
            # SRS logic: Tăng level
            new_level = self.current_item.get('level', 0) + 1
            interval = 2 ** (new_level - 1)
            next_date = today + datetime.timedelta(days=interval)
            
            self.current_item['level'] = new_level
            self.current_item['next_review'] = str(next_date)
            
            self.review_queue.pop(0)
            self.entry_answer.configure(state="disabled")
            self.btn_next.configure(state="normal")
            self.btn_next.focus()
        else:
            self.lbl_feedback.configure(text=f"❌ CỐ LÊN! ({int(ratio*100)}%)", text_color="#EF5350")
            
            # SRS logic: Reset level
            self.current_item['level'] = 0
            self.current_item['next_review'] = str(today)
            self.review_queue.append(self.review_queue.pop(0))
            
            self.play_audio_thread(raw_origin)

        self.show_diff(origin_clean, user_clean)
        self.save_data()

    def show_diff(self, original, user):
        self.txt_diff.delete("1.0", "end")
        matcher = difflib.SequenceMatcher(None, original, user)
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                self.txt_diff.insert("end", original[a0:a1], "correct")
            elif opcode == 'insert':
                self.txt_diff.insert("end", user[b0:b1], "wrong")
            elif opcode == 'delete':
                self.txt_diff.insert("end", original[a0:a1], "miss")
            elif opcode == 'replace':
                self.txt_diff.insert("end", original[a0:a1], "miss")
                self.txt_diff.insert("end", f"[{user[b0:b1]}]", "wrong")

if __name__ == "__main__":
    app = EnglishProApp()
    app.mainloop()
import customtkinter as ctk
from tkinter import messagebox
import datetime
import difflib
import threading
import asyncio
import edge_tts
import pygame
import random
import io
import speech_recognition as sr
from deep_translator import GoogleTranslator
from peewee import *
from groq import Groq

# --- CẤU HÌNH DATABASE ---
db = SqliteDatabase('english_pro.db')

class BaseModel(Model):
    class Meta:
        database = db

class Sentence(BaseModel):
    text = TextField(unique=True)
    meaning = TextField(null=True)
    level = IntegerField(default=0)
    next_review = DateField(default=datetime.date.today)
    created_at = DateField(default=datetime.date.today)

# Bảng mới để lưu Cài đặt (API Key)
class Settings(BaseModel):
    key = CharField(unique=True) # Ví dụ: 'groq_api_key'
    value = TextField()          # Ví dụ: 'gsk_...'

# Kết nối và tạo bảng
db.connect()
db.create_tables([Sentence, Settings], safe=True)

# --- CẤU HÌNH UI ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class EnglishProApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Super English Pro (Database + AI Key)")
        self.geometry("950x700")

        # Khởi tạo âm thanh & Mic
        try:
            pygame.mixer.init()
            self.recognizer = sr.Recognizer()
        except Exception as e:
            print(f"Lỗi khởi tạo media: {e}")

        # Biến quản lý
        self.review_queue = []
        self.current_sentence = None

        # --- GIAO DIỆN ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar
        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        self.lbl_logo = ctk.CTkLabel(self.sidebar, text="ENGLISH PRO", font=ctk.CTkFont(size=24, weight="bold"))
        self.lbl_logo.pack(pady=30)

        self.btn_tab_add = ctk.CTkButton(self.sidebar, text="📝 Thêm Câu Mới", height=40, command=self.show_add_frame)
        self.btn_tab_add.pack(pady=10, padx=20)

        self.btn_tab_review = ctk.CTkButton(self.sidebar, text="🎧 Ôn Tập (SRS)", height=40, command=self.show_review_frame)
        self.btn_tab_review.pack(pady=10, padx=20)
        
        # Nút Cài đặt mới
        self.btn_tab_settings = ctk.CTkButton(self.sidebar, text="⚙️ Cài Đặt (API)", height=40, fg_color="#546E7A", command=self.show_settings_frame)
        self.btn_tab_settings.pack(pady=10, padx=20)
        
        self.lbl_stats = ctk.CTkLabel(self.sidebar, text=self.get_stats_text(), text_color="gray", justify="left")
        self.lbl_stats.pack(side="bottom", pady=20, padx=10)

        # 2. Main Area
        self.main_area = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        self.frame_add = self.create_add_frame()
        self.frame_review = self.create_review_frame()
        self.frame_settings = self.create_settings_frame()

        self.show_review_frame()

    # --- DATABASE HELPERS ---
    def get_stats_text(self):
        try:
            total = Sentence.select().count()
            due = Sentence.select().where(Sentence.next_review <= datetime.date.today()).count()
            return f"Tổng số câu: {total}\nCần ôn hôm nay: {due}"
        except:
            return "Đang tải DB..."
            
    def get_api_key(self):
        try:
            setting = Settings.get(Settings.key == "groq_api_key")
            return setting.value
        except:
            return None

    def save_api_key(self, api_key):
        try:
            # get_or_create: Trả về (obj, created)
            # Nhưng ở đây ta dùng insert hoặc update
            Settings.replace(key="groq_api_key", value=api_key).execute()
            messagebox.showinfo("Thành công", "Đã lưu API Key thành công!")
        except Exception as e:
            messagebox.showerror("Lỗi", f"Không lưu được: {e}")

    # --- AI VOICE & MIC ---
    def play_audio_thread(self, text):
        if not text: return
        threading.Thread(target=self._run_async_tts, args=(text,)).start()

    def _run_async_tts(self, text):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._generate_and_play(text))
            loop.close()
        except Exception as e:
            print(f"Lỗi TTS: {e}")

    async def _generate_and_play(self, text):
        try:
            voice = "en-US-AriaNeural"
            communicate = edge_tts.Communicate(text, voice)
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    audio_data += chunk["data"]
            
            virtual_file = io.BytesIO(audio_data)
            
            if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
            try: pygame.mixer.music.unload()
            except: pass
            
            pygame.mixer.music.load(virtual_file)
            pygame.mixer.music.play()
        except Exception as e:
            print(f"TTS Error: {e}")

    def start_record_thread(self):
        threading.Thread(target=self._run_record).start()

    def _run_record(self):
        self.btn_mic.configure(text="🔴 Đang nghe...", fg_color="red", state="disabled")
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                self.btn_mic.configure(text="⏳ Đang xử lý...")
                text_spoken = self.recognizer.recognize_google(audio, language="en-US")
                self.after(0, lambda: self._update_input_with_voice(text_spoken))
        except Exception as e:
            print(f"Mic Error: {e}")
            self.after(0, lambda: messagebox.showinfo("Mic", "Không nghe rõ. Thử lại nhé!"))
        finally:
            self.after(0, lambda: self.btn_mic.configure(text="🎤 NÓI (F2)", fg_color="#D84315", state="normal"))

    def _update_input_with_voice(self, text):
        self.entry_answer.delete(0, "end")
        self.entry_answer.insert(0, text)
        self.check_answer()

    # --- DỊCH THUẬT & GROQ ---
    def translate_thread(self):
        text_vi = self.entry_vi.get().strip()
        if not text_vi: return
        threading.Thread(target=self._run_translate, args=(text_vi,)).start()

    def _run_translate(self, text_vi):
        try:
            translated = GoogleTranslator(source='auto', target='en').translate(text_vi)
            self.after(0, lambda: self._append_translation(translated))
        except Exception as e:
            print(e)

    def _append_translation(self, text_en):
        current_content = self.txt_input.get("1.0", "end").strip()
        if current_content:
            self.txt_input.insert("end", "\n" + text_en)
        else:
            self.txt_input.insert("end", text_en)
        self.entry_vi.delete(0, "end")

    def get_meaning_thread(self, sentence_obj):
        if sentence_obj.meaning:
            self.lbl_meaning.configure(text=f"{sentence_obj.meaning}")
        else:
            threading.Thread(target=self._run_translate_meaning, args=(sentence_obj,)).start()

    def _run_translate_meaning(self, sentence_obj):
        # 1. Lấy API Key từ Database
        api_key = self.get_api_key()
        
        # 2. Nếu có Key thì dùng Groq
        if api_key:
            try:
                client = Groq(api_key=api_key)
                prompt = f"""
                Giải thích ngắn gọn câu tiếng Anh sau cho người Việt: "{sentence_obj.text}"
                Format:
                - Nghĩa: ...
                - Ngữ cảnh: ... (ngắn gọn)
                """
                chat_completion = client.chat.completions.create(
                    messages=[{"role": "user", "content": prompt}],
                    model="openai/gpt-oss-120b",
                    temperature=0.3,
                )
                full_meaning = chat_completion.choices[0].message.content.strip()
                
                # Lưu DB
                sentence_obj.meaning = full_meaning
                sentence_obj.save()
                
                self.after(0, lambda: self.lbl_meaning.configure(text=full_meaning))
                return # Thành công thì thoát luôn
            except Exception as e:
                print(f"Lỗi Groq: {e}")
                self.after(0, lambda: self.lbl_meaning.configure(text="Lỗi Groq, đang thử Google..."))

        # 3. Fallback: Nếu không có Key hoặc Groq lỗi thì dùng Google
        try:
            fallback = GoogleTranslator(source='en', target='vi').translate(sentence_obj.text)
            self.after(0, lambda: self.lbl_meaning.configure(text=f"Nghĩa: {fallback}"))
        except:
            pass

    # --- UI LAYOUTS ---
    def create_add_frame(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        
        lbl_vi = ctk.CTkLabel(frame, text="💡 Gợi ý (Nhập tiếng Việt):", font=("Arial", 14))
        lbl_vi.pack(pady=(0, 5), anchor="w")
        self.entry_vi = ctk.CTkEntry(frame, placeholder_text="Ví dụ: Tôi đi làm bằng xe buýt", font=("Arial", 12))
        self.entry_vi.pack(fill="x", pady=(0, 5))
        self.entry_vi.bind("<Return>", lambda e: self.translate_thread())
        btn_trans = ctk.CTkButton(frame, text="Dịch sang Anh ⬇️", fg_color="#E65100", height=30, command=self.translate_thread)
        btn_trans.pack(anchor="e", pady=(0, 20))

        lbl_en = ctk.CTkLabel(frame, text="Danh sách câu tiếng Anh:", font=("Arial", 16, "bold"))
        lbl_en.pack(pady=(0, 10), anchor="w")
        self.txt_input = ctk.CTkTextbox(frame, height=300, font=("Arial", 13))
        self.txt_input.pack(fill="both", expand=True, pady=10)
        btn_save = ctk.CTkButton(frame, text="Lưu Vào Database", fg_color="#2E7D32", height=45, font=("Arial", 14, "bold"),
                                 command=self.save_bulk_sentences)
        btn_save.pack(fill="x", pady=10)
        return frame

    def create_review_frame(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        self.lbl_progress = ctk.CTkLabel(frame, text="Đang tải...", font=("Arial", 14))
        self.lbl_progress.pack(pady=10)

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(10, 5))
        self.btn_listen = ctk.CTkButton(btn_frame, text="🔊 NGHE (F1)", font=("Arial", 16, "bold"), height=50,
                                        command=lambda: self.play_audio_thread(self.current_sentence.text if self.current_sentence else ""))
        self.btn_listen.pack(side="left", fill="x", expand=True, padx=(0, 5))
        self.btn_mic = ctk.CTkButton(btn_frame, text="🎤 NÓI (F2)", font=("Arial", 16, "bold"), height=50, 
                                     fg_color="#D84315", hover_color="#BF360C", command=self.start_record_thread)
        self.btn_mic.pack(side="right", fill="x", expand=True, padx=(5, 0))

        self.lbl_meaning = ctk.CTkLabel(frame, text="", font=("Arial", 14, "italic"), text_color="#FFA726", wraplength=700)
        self.lbl_meaning.pack(pady=(0, 20))

        self.entry_answer = ctk.CTkEntry(frame, font=("Arial", 18), height=50, placeholder_text="Gõ lại hoặc nói...")
        self.entry_answer.pack(fill="x", pady=10)
        self.entry_answer.bind("<Return>", self.check_answer)
        self.entry_answer.bind("<F1>", lambda e: self.btn_listen.invoke())
        self.entry_answer.bind("<F2>", lambda e: self.btn_mic.invoke())

        self.btn_check = ctk.CTkButton(frame, text="Kiểm tra (Enter)", command=self.check_answer)
        self.btn_check.pack(pady=5)
        self.lbl_feedback = ctk.CTkLabel(frame, text="", font=("Arial", 20, "bold"))
        self.lbl_feedback.pack(pady=15)
        self.txt_diff = ctk.CTkTextbox(frame, height=80, font=("Consolas", 16), fg_color="#2b2b2b")
        self.txt_diff.pack(fill="x", pady=5)
        self.txt_diff.tag_config("correct", foreground="#66BB6A")
        self.txt_diff.tag_config("wrong", foreground="#EF5350")
        self.txt_diff.tag_config("miss", foreground="#FFA726")
        self.btn_next = ctk.CTkButton(frame, text="Câu tiếp theo >>", state="disabled", height=40, command=self.next_card)
        self.btn_next.pack(pady=20)
        return frame
    
    # --- UI CÀI ĐẶT (MỚI) ---
    def create_settings_frame(self):
        frame = ctk.CTkFrame(self.main_area, fg_color="transparent")
        
        ctk.CTkLabel(frame, text="Cấu hình hệ thống", font=("Arial", 20, "bold")).pack(pady=20)
        
        # Phần nhập Groq Key
        key_frame = ctk.CTkFrame(frame)
        key_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(key_frame, text="Groq API Key (Miễn phí tại console.groq.com):", font=("Arial", 14)).pack(anchor="w", padx=10, pady=5)
        
        self.entry_api_key = ctk.CTkEntry(key_frame, placeholder_text="gsk_...", width=400)
        self.entry_api_key.pack(fill="x", padx=10, pady=(0, 10))
        
        # Tự động điền key nếu đã có trong DB
        saved_key = self.get_api_key()
        if saved_key:
            self.entry_api_key.insert(0, saved_key)
        
        btn_save_key = ctk.CTkButton(key_frame, text="Lưu API Key", command=lambda: self.save_api_key(self.entry_api_key.get().strip()))
        btn_save_key.pack(pady=10)
        
        ctk.CTkLabel(key_frame, text="* Lưu ý: Key được lưu vào Database trên máy bạn.", text_color="gray", font=("Arial", 12)).pack(pady=5)

        return frame

    # --- LOGIC CHUYỂN TAB ---
    def save_bulk_sentences(self):
        content = self.txt_input.get("1.0", "end").strip()
        if not content: return
        lines = content.split('\n')
        count = 0
        skipped = 0
        for line in lines:
            line = line.strip()
            if line:
                try:
                    obj, created = Sentence.get_or_create(text=line)
                    if created: count += 1
                    else: skipped += 1
                except: pass
        self.txt_input.delete("1.0", "end")
        self.lbl_stats.configure(text=self.get_stats_text())
        messagebox.showinfo("Kết quả", f"Thêm: {count}\nTrùng: {skipped}")

    def show_add_frame(self):
        self.main_area_forget_all()
        self.frame_add.pack(fill="both", expand=True)

    def show_review_frame(self):
        self.main_area_forget_all()
        self.frame_review.pack(fill="both", expand=True)
        self.start_session()
        
    def show_settings_frame(self):
        self.main_area_forget_all()
        self.frame_settings.pack(fill="both", expand=True)

    def main_area_forget_all(self):
        self.frame_add.pack_forget()
        self.frame_review.pack_forget()
        self.frame_settings.pack_forget()

    def start_session(self):
        today = datetime.date.today()
        query = Sentence.select().where(Sentence.next_review <= today)
        self.review_queue = list(query)
        if not self.review_queue:
            self.lbl_progress.configure(text="Đã hoàn thành tất cả.")
            self.lbl_meaning.configure(text="")
            self.entry_answer.configure(state="disabled")
            self.btn_listen.configure(state="disabled")
            self.btn_mic.configure(state="disabled")
            self.txt_diff.delete("1.0", "end")
            self.current_sentence = None
        else:
            random.shuffle(self.review_queue)
            self.next_card()

    def next_card(self):
        if not self.review_queue:
            self.start_session()
            return
        self.current_sentence = self.review_queue[0]
        self.lbl_progress.configure(text=f"Cần ôn: {len(self.review_queue)}")
        self.entry_answer.configure(state="normal")
        self.entry_answer.delete(0, "end")
        self.entry_answer.focus()
        self.lbl_feedback.configure(text="")
        self.txt_diff.delete("1.0", "end")
        self.lbl_meaning.configure(text="Đang tải nghĩa...")
        self.btn_next.configure(state="disabled")
        self.btn_listen.configure(state="normal")
        self.btn_mic.configure(state="normal")
        self.after(500, lambda: self.play_audio_thread(self.current_sentence.text))
        self.get_meaning_thread(self.current_sentence)

    def check_answer(self, event=None):
        if not self.current_sentence: return
        raw_origin = self.current_sentence.text.strip()
        raw_user = self.entry_answer.get().strip()
        origin_clean = raw_origin.replace("’", "'").replace("‘", "'").rstrip('.!?')
        user_clean = raw_user.replace("’", "'").replace("‘", "'").rstrip('.!?')
        matcher = difflib.SequenceMatcher(None, origin_clean.lower(), user_clean.lower())
        ratio = matcher.ratio()
        is_correct = ratio >= 0.9
        today = datetime.date.today()
        if is_correct:
            self.lbl_feedback.configure(text=f"✅ CHÍNH XÁC ({int(ratio*100)}%)", text_color="#66BB6A")
            new_level = self.current_sentence.level + 1
            interval = 2 ** (new_level - 1)
            next_date = today + datetime.timedelta(days=interval)
            self.current_sentence.level = new_level
            self.current_sentence.next_review = next_date
            self.current_sentence.save()
            self.review_queue.pop(0)
            self.entry_answer.configure(state="disabled")
            self.btn_next.configure(state="normal")
            self.btn_next.focus()
        else:
            self.lbl_feedback.configure(text=f"❌ CỐ LÊN! ({int(ratio*100)}%)", text_color="#EF5350")
            self.current_sentence.level = 0
            self.current_sentence.next_review = today
            self.current_sentence.save()
            self.review_queue.append(self.review_queue.pop(0))
            self.play_audio_thread(raw_origin)
        self.show_diff(raw_origin, raw_user)
        self.lbl_stats.configure(text=self.get_stats_text())

    def show_diff(self, original, user):
        self.txt_diff.delete("1.0", "end")
        matcher = difflib.SequenceMatcher(None, original, user)
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal': self.txt_diff.insert("end", original[a0:a1], "correct")
            elif opcode == 'insert': self.txt_diff.insert("end", user[b0:b1], "wrong")
            elif opcode == 'delete': self.txt_diff.insert("end", original[a0:a1], "miss")
            elif opcode == 'replace':
                self.txt_diff.insert("end", original[a0:a1], "miss")
                self.txt_diff.insert("end", f"[{user[b0:b1]}]", "wrong")

if __name__ == "__main__":
    app = EnglishProApp()
    app.mainloop()
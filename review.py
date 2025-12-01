import customtkinter as ctk
from tkinter import messagebox
import datetime
import threading
import asyncio
import edge_tts
import pygame
import random
import io
import difflib
import speech_recognition as sr
from deep_translator import GoogleTranslator
from peewee import *
from groq import Groq

# ==========================================
# 1. CẤU HÌNH DATABASE
# ==========================================
db = SqliteDatabase('english_pro.db')

class BaseModel(Model):
    class Meta:
        database = db

class Sentence(BaseModel):
    text = TextField(unique=True)
    meaning = TextField(null=True)
    level = IntegerField(default=0)
    next_review = DateField(default=datetime.date.today)

class Vocabulary(BaseModel):
    word = TextField(unique=True)
    meaning = TextField(null=True)
    level = IntegerField(default=0)
    next_review = DateField(default=datetime.date.today)

class Settings(BaseModel):
    key = CharField(unique=True) 
    value = TextField()

db.connect()
db.create_tables([Sentence, Vocabulary, Settings], safe=True)

# ==========================================
# 2. GIAO DIỆN CHÍNH
# ==========================================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class EnglishApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Super English Pro: Clean UI")
        self.geometry("1100x850")

        try:
            pygame.mixer.init()
            self.recognizer = sr.Recognizer()
        except: pass

        self.mode = "sentence"
        self.review_queue = []
        self.current_item = None

        # --- SIDEBAR (MENU BÊN TRÁI) ---
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.sidebar = ctk.CTkFrame(self, width=220, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        
        # Logo
        ctk.CTkLabel(self.sidebar, text="ENGLISH PRO", font=ctk.CTkFont(size=24, weight="bold")).pack(pady=30)

        # 1. NHÓM CHỨC NĂNG HỌC TẬP
        ctk.CTkLabel(self.sidebar, text="KHÔNG GIAN HỌC:", font=("Arial", 12, "bold"), text_color="gray", anchor="w").pack(fill="x", padx=20, pady=(10, 5))
        
        self.btn_nav_sent = ctk.CTkButton(self.sidebar, text="🗣️ Ôn Câu (Dictation)", fg_color="transparent", border_width=2, anchor="w", command=self.nav_sentence)
        self.btn_nav_sent.pack(fill="x", pady=5, padx=20)
        
        self.btn_nav_vocab = ctk.CTkButton(self.sidebar, text="🧠 Ôn Từ (Vocab)", fg_color="transparent", border_width=2, anchor="w", command=self.nav_vocab)
        self.btn_nav_vocab.pack(fill="x", pady=5, padx=20)

        ctk.CTkFrame(self.sidebar, height=2, fg_color="#455A64").pack(fill="x", pady=20, padx=20)

        # 2. NHÓM QUẢN LÝ
        ctk.CTkLabel(self.sidebar, text="QUẢN LÝ:", font=("Arial", 12, "bold"), text_color="gray", anchor="w").pack(fill="x", padx=20, pady=(10, 5))

        self.btn_nav_add = ctk.CTkButton(self.sidebar, text="📝 Thêm Dữ Liệu", fg_color="transparent", border_width=2, anchor="w", command=self.nav_add)
        self.btn_nav_add.pack(fill="x", pady=5, padx=20)
        
        self.btn_nav_settings = ctk.CTkButton(self.sidebar, text="⚙️ Cài Đặt API", fg_color="transparent", border_width=2, anchor="w", command=self.nav_settings)
        self.btn_nav_settings.pack(fill="x", pady=5, padx=20)
        
        # Thống kê
        self.lbl_stats = ctk.CTkLabel(self.sidebar, text="Loading...", text_color="gray", justify="left")
        self.lbl_stats.pack(side="bottom", pady=20)

        # --- MAIN AREA ---
        self.main = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self.main.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)

        # Init Frames
        self.frame_add = self.ui_add_unified()
        self.frame_sent = self.ui_sent_review()
        self.frame_vocab = self.ui_vocab_review()
        self.frame_settings = self.ui_settings()

        self.frames = [self.frame_add, self.frame_sent, self.frame_vocab, self.frame_settings]

        # Mặc định vào Ôn câu
        self.nav_sentence()

    # ==========================================
    # 3. ĐIỀU HƯỚNG (NAVIGATION)
    # ==========================================
    def reset_buttons(self):
        # Đặt lại màu cho tất cả nút về trạng thái chưa chọn
        for btn in [self.btn_nav_sent, self.btn_nav_vocab, self.btn_nav_add, self.btn_nav_settings]:
            btn.configure(fg_color="transparent")

    def hide_all_frames(self):
        for f in self.frames: f.pack_forget()

    def nav_sentence(self):
        self.reset_buttons()
        self.hide_all_frames()
        self.btn_nav_sent.configure(fg_color="#1565C0") # Highlight nút này
        self.frame_sent.pack(fill="both", expand=True)
        self.mode = "sentence"
        self.update_stats()
        self.start_sent_session()

    def nav_vocab(self):
        self.reset_buttons()
        self.hide_all_frames()
        self.btn_nav_vocab.configure(fg_color="#D84315") # Highlight nút này
        self.frame_vocab.pack(fill="both", expand=True)
        self.mode = "vocab"
        self.update_stats()
        self.start_vocab_session()

    def nav_add(self):
        self.reset_buttons()
        self.hide_all_frames()
        self.btn_nav_add.configure(fg_color="#2E7D32") # Highlight nút này
        self.frame_add.pack(fill="both", expand=True)
        self.update_stats()

    def nav_settings(self):
        self.reset_buttons()
        self.hide_all_frames()
        self.btn_nav_settings.configure(fg_color="#546E7A") # Highlight nút này
        self.frame_settings.pack(fill="both", expand=True)

    # ==========================================
    # 4. LOGIC & HELPER
    # ==========================================
    def get_key(self):
        try: return Settings.get(Settings.key == "groq").value
        except: return None

    def update_stats(self):
        try:
            sent_total = Sentence.select().count()
            vocab_total = Vocabulary.select().count()
            if self.mode == "sentence":
                due = Sentence.select().where(Sentence.next_review <= datetime.date.today()).count()
                self.lbl_stats.configure(text=f"[CÂU]\nTổng: {sent_total} | Cần ôn: {due}")
            else:
                due = Vocabulary.select().where(Vocabulary.next_review <= datetime.date.today()).count()
                self.lbl_stats.configure(text=f"[TỪ]\nTổng: {vocab_total} | Cần ôn: {due}")
        except: pass

    # --- TTS & AUDIO ---
    def play_audio(self, text):
        threading.Thread(target=self._tts_thread, args=(text,)).start()

    def _tts_thread(self, text):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self._tts_stream(text))
            loop.close()
        except: pass

    async def _tts_stream(self, text):
        try:
            communicate = edge_tts.Communicate(text, "en-US-AriaNeural")
            audio_data = b""
            async for chunk in communicate.stream():
                if chunk["type"] == "audio": audio_data += chunk["data"]
            virtual_file = io.BytesIO(audio_data)
            if pygame.mixer.music.get_busy(): pygame.mixer.music.stop()
            try: pygame.mixer.music.unload()
            except: pass
            pygame.mixer.music.load(virtual_file)
            pygame.mixer.music.play()
        except: pass

    def start_record(self, entry_widget):
        threading.Thread(target=self._record_thread, args=(entry_widget,)).start()

    def _record_thread(self, entry_widget):
        try:
            with sr.Microphone() as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio, language="en-US")
                self.after(0, lambda: [entry_widget.delete(0, "end"), entry_widget.insert(0, text)])
        except: messagebox.showinfo("Mic", "Không nghe rõ!")

    # ==========================================
    # 5. UI THÊM DỮ LIỆU (2 TAB)
    # ==========================================
    def ui_add_unified(self):
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        
        tabview = ctk.CTkTabview(frame)
        tabview.pack(fill="both", expand=True)
        
        tab_sent = tabview.add("🗣️ THÊM CÂU")
        tab_vocab = tabview.add("🧠 THÊM TỪ (AI)")
        
        # --- TAB CÂU ---
        ctk.CTkLabel(tab_sent, text="Nhập câu tiếng Anh:", font=("Arial", 14, "bold")).pack(pady=5)
        f_trans = ctk.CTkFrame(tab_sent)
        f_trans.pack(fill="x", pady=5)
        self.entry_vi = ctk.CTkEntry(f_trans, placeholder_text="Gõ tiếng Việt để dịch...")
        self.entry_vi.pack(side="left", fill="x", expand=True, padx=5)
        self.entry_vi.bind("<Return>", self.do_translate)
        ctk.CTkButton(f_trans, text="Dịch", width=80, command=self.do_translate).pack(side="right", padx=5)

        self.txt_sent_input = ctk.CTkTextbox(tab_sent, height=300, font=("Arial", 14))
        self.txt_sent_input.pack(fill="both", expand=True, pady=10)
        ctk.CTkButton(tab_sent, text="Lưu Vào Kho Câu", fg_color="#1565C0", height=40, command=self.save_sent).pack(fill="x", pady=10)

        # --- TAB TỪ ---
        ctk.CTkLabel(tab_vocab, text="Nhập chủ đề AI gợi ý:", font=("Arial", 14, "bold")).pack(pady=5)
        f_gen = ctk.CTkFrame(tab_vocab)
        f_gen.pack(fill="x", pady=5)
        self.entry_topic = ctk.CTkEntry(f_gen, placeholder_text="Chủ đề...")
        self.entry_topic.pack(side="left", fill="x", expand=True, padx=5)
        self.entry_topic.bind("<Return>", self.generate_vocab)
        ctk.CTkButton(f_gen, text="AI Tạo Từ", fg_color="#7B1FA2", width=100, command=self.generate_vocab).pack(side="right", padx=5)
        
        self.txt_vocab_input = ctk.CTkTextbox(tab_vocab, height=250, font=("Arial", 14))
        self.txt_vocab_input.pack(fill="both", expand=True, pady=10)
        ctk.CTkButton(tab_vocab, text="Lưu Vào Kho Từ Vựng", fg_color="#D84315", height=40, command=self.save_vocab).pack(fill="x", pady=10)

        return frame

    def do_translate(self, event=None):
        text = self.entry_vi.get()
        if text:
            try:
                t = GoogleTranslator(source='auto', target='en').translate(text)
                self.txt_sent_input.insert("end", t + "\n")
                self.entry_vi.delete(0, "end")
            except: pass

    def save_sent(self):
        lines = self.txt_sent_input.get("1.0", "end").split('\n')
        c = 0
        for l in lines:
            if l.strip():
                try: 
                    Sentence.get_or_create(text=l.strip())
                    c+=1
                except: pass
        self.txt_sent_input.delete("1.0", "end")
        self.update_stats()
        messagebox.showinfo("OK", f"Đã thêm {c} câu.")

    def generate_vocab(self, event=None):
        topic = self.entry_topic.get().strip()
        key = self.get_key()
        if not topic or not key: return
        self.txt_vocab_input.delete("1.0", "end")
        self.txt_vocab_input.insert("1.0", "⏳ Đang tạo từ...")
        threading.Thread(target=self._run_gen, args=(topic, key)).start()

    def _run_gen(self, topic, key):
        try:
            client = Groq(api_key=key)
            prompt = f"List 10 English words about '{topic}'. Only words, one per line."
            res = client.chat.completions.create(messages=[{"role":"user","content":prompt}], model="openai/gpt-oss-120b").choices[0].message.content
            self.txt_vocab_input.delete("1.0", "end")
            self.txt_vocab_input.insert("1.0", res.strip())
        except Exception as e:
            self.txt_vocab_input.delete("1.0", "end")
            self.txt_vocab_input.insert("1.0", f"Lỗi: {e}")

    def save_vocab(self):
        lines = self.txt_vocab_input.get("1.0", "end").split('\n')
        c = 0
        for l in lines:
            w = l.strip()
            if w and "⏳" not in w:
                try: 
                    mean = GoogleTranslator(source='auto', target='vi').translate(w)
                    Vocabulary.get_or_create(word=w, defaults={'meaning': mean})
                    c+=1
                except: pass
        self.txt_vocab_input.delete("1.0", "end")
        self.update_stats()
        messagebox.showinfo("OK", f"Đã thêm {c} từ vựng.")

    # ==========================================
    # 6. ÔN CÂU (SENTENCE REVIEW)
    # ==========================================
    def ui_sent_review(self):
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.lbl_sent_prog = ctk.CTkLabel(frame, text="...")
        self.lbl_sent_prog.pack(pady=5)
        
        f_btn = ctk.CTkFrame(frame, fg_color="transparent")
        f_btn.pack(fill="x", pady=5)
        ctk.CTkButton(f_btn, text="🔊 NGHE (F1)", command=lambda: self.play_audio(self.current_item.text)).pack(side="left", fill="x", expand=True, padx=5)
        ctk.CTkButton(f_btn, text="🎤 NÓI (F2)", fg_color="#D84315", command=lambda: self.start_record(self.entry_sent_ans)).pack(side="right", fill="x", expand=True, padx=5)

        self.lbl_sent_mean = ctk.CTkLabel(frame, text="", font=("Arial", 14, "italic"), text_color="#FFA726", wraplength=800)
        self.lbl_sent_mean.pack(pady=10)

        self.entry_sent_ans = ctk.CTkEntry(frame, font=("Arial", 18), height=50)
        self.entry_sent_ans.pack(fill="x", pady=5)
        self.entry_sent_ans.bind("<Return>", self.check_sent)
        self.entry_sent_ans.bind("<F1>", lambda e: self.play_audio(self.current_item.text))
        self.entry_sent_ans.bind("<F2>", lambda e: self.start_record(self.entry_sent_ans))

        self.txt_diff = ctk.CTkTextbox(frame, height=100, font=("Consolas", 16), fg_color="#222")
        self.txt_diff.pack(fill="x", pady=10)
        self.txt_diff.tag_config("correct", foreground="#66BB6A")
        self.txt_diff.tag_config("wrong", foreground="#EF5350")
        self.txt_diff.tag_config("miss", foreground="#FFA726")

        self.btn_sent_next = ctk.CTkButton(frame, text="Tiếp theo >>", state="disabled", command=self.next_sent)
        self.btn_sent_next.pack(pady=10)
        return frame

    def start_sent_session(self):
        today = datetime.date.today()
        self.review_queue = list(Sentence.select().where(Sentence.next_review <= today))
        if self.review_queue:
            random.shuffle(self.review_queue)
            self.next_sent()
        else:
            self.lbl_sent_prog.configure(text="Hết bài ôn câu!")
            self.lbl_sent_mean.configure(text="")
            self.entry_sent_ans.configure(state="disabled")

    def next_sent(self):
        if not self.review_queue: self.start_sent_session(); return
        self.current_item = self.review_queue[0]
        self.lbl_sent_prog.configure(text=f"Cần ôn: {len(self.review_queue)}")
        self.entry_sent_ans.configure(state="normal")
        self.entry_sent_ans.delete(0, "end")
        self.entry_sent_ans.focus()
        self.lbl_sent_mean.configure(text="") 
        self.txt_diff.delete("1.0", "end")
        self.btn_sent_next.configure(state="disabled")
        self.after(500, lambda: self.play_audio(self.current_item.text))

    def check_sent(self, event=None):
        if not self.current_item: return
        user = self.entry_sent_ans.get().strip()
        raw = self.current_item.text.strip()
        
        ratio = difflib.SequenceMatcher(None, raw.lower(), user.lower()).ratio()
        self.show_diff(raw, user)

        if ratio >= 0.9:
            self.review_queue.pop(0)
            self.current_item.level += 1
            self.current_item.next_review = datetime.date.today() + datetime.timedelta(days=2**(self.current_item.level-1))
            self.current_item.save()
            self.btn_sent_next.configure(state="normal")
            self.btn_sent_next.focus()
            threading.Thread(target=self.groq_explain_sentence).start()
        else:
            self.review_queue.append(self.review_queue.pop(0))
            self.current_item.level = 0
            self.current_item.next_review = datetime.date.today()
            self.current_item.save()
            self.play_audio(raw)

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

    def groq_explain_sentence(self):
        if self.current_item.meaning:
            self.lbl_sent_mean.configure(text=self.current_item.meaning)
            return
        key = self.get_key()
        if key:
            try:
                self.lbl_sent_mean.configure(text="⏳ Groq đang phân tích...")
                client = Groq(api_key=key)
                prompt = f"Giải thích ngắn gọn câu: '{self.current_item.text}'"
                res = client.chat.completions.create(messages=[{"role":"user","content":prompt}], model="openai/gpt-oss-120b").choices[0].message.content
                self.current_item.meaning = res
                self.current_item.save()
                self.lbl_sent_mean.configure(text=res)
            except: self.lbl_sent_mean.configure(text="Lỗi API")
        else:
            t = GoogleTranslator(source='en', target='vi').translate(self.current_item.text)
            self.lbl_sent_mean.configure(text=t)

    # ==========================================
    # 7. ÔN TỪ (VOCAB REVIEW)
    # ==========================================
    def ui_vocab_review(self):
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        self.lbl_vocab_prog = ctk.CTkLabel(frame, text="...")
        self.lbl_vocab_prog.pack(pady=5)
        
        self.lbl_vocab_word = ctk.CTkLabel(frame, text="WORD", font=("Arial", 36, "bold"), text_color="#4FC3F7")
        self.lbl_vocab_word.pack(pady=10)
        self.lbl_vocab_hint = ctk.CTkLabel(frame, text="", font=("Arial", 16, "italic"), text_color="gray")
        self.lbl_vocab_hint.pack()
        
        ctk.CTkButton(frame, text="🔊 Nghe", command=lambda: self.play_audio(self.current_item.word)).pack(pady=5)
        
        ctk.CTkLabel(frame, text="Đặt câu:", font=("Arial", 14)).pack(anchor="w", pady=(20,0))
        self.entry_vocab_sent = ctk.CTkEntry(frame, font=("Arial", 16))
        self.entry_vocab_sent.pack(fill="x")
        self.entry_vocab_sent.bind("<Return>", self.check_vocab)
        
        ctk.CTkButton(frame, text="Check AI", fg_color="#6A1B9A", command=self.check_vocab).pack(pady=10)
        self.lbl_vocab_feed = ctk.CTkLabel(frame, text="", wraplength=800, justify="left")
        self.lbl_vocab_feed.pack()
        
        self.btn_vocab_next = ctk.CTkButton(frame, text="Tiếp theo >>", state="disabled", command=self.next_vocab)
        self.btn_vocab_next.pack(pady=20)
        return frame

    def start_vocab_session(self):
        today = datetime.date.today()
        self.review_queue = list(Vocabulary.select().where(Vocabulary.next_review <= today))
        if self.review_queue:
            random.shuffle(self.review_queue)
            self.next_vocab()
        else:
            self.lbl_vocab_prog.configure(text="Hết từ vựng ôn!")
            self.lbl_vocab_word.configure(text="DONE!")
            self.entry_vocab_sent.configure(state="disabled")

    def next_vocab(self):
        if not self.review_queue: self.start_vocab_session(); return
        self.current_item = self.review_queue[0]
        self.lbl_vocab_prog.configure(text=f"Cần ôn: {len(self.review_queue)}")
        self.lbl_vocab_word.configure(text=self.current_item.word)
        self.lbl_vocab_hint.configure(text=self.current_item.meaning)
        self.entry_vocab_sent.configure(state="normal")
        self.entry_vocab_sent.delete(0, "end")
        self.entry_vocab_sent.focus()
        self.lbl_vocab_feed.configure(text="")
        self.btn_vocab_next.configure(state="disabled")
        self.after(500, lambda: self.play_audio(self.current_item.word))

    def check_vocab(self, event=None):
        sent = self.entry_vocab_sent.get()
        if not sent: return
        key = self.get_key()
        if not key:
            self.lbl_vocab_feed.configure(text="Chưa cài API Key!")
            return
        
        self.lbl_vocab_feed.configure(text="⏳ Đang chấm điểm...", text_color="yellow")
        threading.Thread(target=self.groq_check_vocab, args=(self.current_item.word, sent, key)).start()

    def groq_check_vocab(self, word, sent, key):
        try:
            client = Groq(api_key=key)
            prompt = f"Check sentence using '{word}': '{sent}'. Output: Correct/Incorrect, Fix, Better version."
            res = client.chat.completions.create(messages=[{"role":"user","content":prompt}], model="openai/gpt-oss-120b").choices[0].message.content
            self.lbl_vocab_feed.configure(text=res, text_color="white")
            self.btn_vocab_next.configure(state="normal")
            
            self.review_queue.pop(0)
            self.current_item.level += 1
            self.current_item.next_review = datetime.date.today() + datetime.timedelta(days=2**(self.current_item.level-1))
            self.current_item.save()
        except Exception as e:
            self.lbl_vocab_feed.configure(text=f"Lỗi: {e}")

    # ==========================================
    # 8. CÀI ĐẶT
    # ==========================================
    def ui_settings(self):
        frame = ctk.CTkFrame(self.main, fg_color="transparent")
        ctk.CTkLabel(frame, text="API GROQ", font=("Arial", 20)).pack(pady=20)
        self.entry_key = ctk.CTkEntry(frame, width=400, show="*")
        self.entry_key.pack(pady=10)
        if self.get_key(): self.entry_key.insert(0, self.get_key())
        ctk.CTkButton(frame, text="Lưu", command=lambda: [Settings.replace(key="groq", value=self.entry_key.get()).execute(), messagebox.showinfo("OK","Lưu xong")]).pack(pady=10)
        return frame

if __name__ == "__main__":
    app = EnglishApp()
    app.mainloop()
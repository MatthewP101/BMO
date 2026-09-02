import time
import tkinter as tk
from tkinter import filedialog, ttk
from queue import Empty

from app.config import load_config, save_preferences
from app.memory.history import get_recent_history
from app.voice.controller import VoiceController
from ui.face import FACE_COLOUR, INK, FaceRenderer, layout_for

BG = '#153e37'
PANEL = '#edf2df'
MUTED = '#5b7361'
ACCENT = '#f2c65c'


class BMOWindow:
    def __init__(self, bmo, controller=None, root=None):
        self.bmo = bmo
        self.config = load_config()
        self.controller = controller or VoiceController(bmo, self.config['voice'])
        self.root = root or tk.Tk()
        self.root.title('BMO')
        self.root.configure(bg=BG)
        screen_w, screen_h = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        width, height = min(1200, max(320, screen_w - 40)), max(300, screen_h - 80) if screen_w < 900 else min(900, max(300, screen_h - 80))
        self.root.geometry(f'{width}x{height}+{max(0, (screen_w-width)//2)}+{max(0, (screen_h-height)//2)}')
        self.root.minsize(min(360, screen_w), min(300, screen_h))
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.closed = False
        self.poll_timer = self.draw_timer = self.layout_timer = None
        self.voice_state = 'Ready'
        self.reply_open = False
        self.reply_start = None
        self.last_reply = ''
        self.metrics = {}
        self.streaming_reply = ''
        self.unread = False
        self.settings_window = None
        self.started = time.monotonic()
        ui = self.config['ui']
        self.mode = tk.StringVar(value=ui.get('mode', 'auto'))
        self.speak_replies = tk.BooleanVar(value=ui.get('speak_replies', True))
        self.face_only = tk.BooleanVar(value=ui.get('face_only', False))
        self.fullscreen = tk.BooleanVar(value=ui.get('fullscreen', False))
        self.reduced_motion = tk.BooleanVar(value=ui.get('reduced_motion', False))
        self.font_size = max(10, min(20, int(ui.get('font_size', 12))))
        self.fps = max(15, min(60, int(ui.get('fps', 40))))
        self._build()
        self.root.bind('<Configure>', self.schedule_layout)
        self.root.bind('<F11>', self.toggle_fullscreen)
        self.root.bind('<Escape>', self.escape)
        self.root.bind('<Control-l>', lambda event: self.entry.focus_set())
        self.root.bind('<Control-space>', self.toggle_recording)
        self.root.bind('<Control-period>', lambda event: self.controller.stop())
        self.root.attributes('-fullscreen', self.fullscreen.get())
        self.root.after_idle(self.relayout)
        self.animate()
        self.poll_events()
        self.entry.focus_set()

    def button(self, parent, text, command, accent=False):
        return tk.Button(parent, text=text, command=command, bg=ACCENT if accent else '#d7e5c9',
                         fg=INK, activebackground='#c4dcb7', activeforeground=INK,
                         relief='flat', bd=0, padx=10, pady=7, cursor='hand2',
                         font=('DejaVu Sans', 10), highlightthickness=0)

    def _build(self):
        self.header = tk.Frame(self.root, bg=BG)
        self.header.place(x=12, y=8, relwidth=1, width=-24, height=36)
        tk.Label(self.header, text='BMO', bg=BG, fg=PANEL,
                 font=('DejaVu Sans', 16, 'bold')).pack(side='left')
        self.status = tk.Label(self.header, text='Ready', bg=BG, fg='#afc6a9', font=('DejaVu Sans', 10))
        self.status.pack(side='left', padx=14)
        self.settings_button = self.button(self.header, 'Settings', self.open_settings)
        self.settings_button.pack(side='right')
        self.view_button = self.button(self.header, 'Face', self.toggle_face)
        self.view_button.pack(side='right', padx=5)
        self.face_panel = tk.Frame(self.root, bg=FACE_COLOUR)
        self.face = tk.Canvas(self.face_panel, bg=FACE_COLOUR, highlightthickness=0)
        self.face.pack(fill='both', expand=True)
        self.renderer = FaceRenderer(self.face)
        self.face.bind('<Motion>', self.look_at)
        self.face.bind('<Button-1>', self.face_tap)
        self.face_hint = tk.Label(self.face_panel, text='Here with you.', bg=FACE_COLOUR,
                                  fg=MUTED, font=('DejaVu Sans', 10))
        self.face_hint.place(relx=.5, rely=.95, anchor='s')
        self.face_talk = self.button(self.face_panel, 'Talk', self.toggle_recording, True)
        self.conversation = tk.Frame(self.root, bg=PANEL)
        self.conversation.grid_columnconfigure(0, weight=1)
        self.conversation.grid_rowconfigure(1, weight=1)
        top = tk.Frame(self.conversation, bg=PANEL)
        self.conversation_header = top
        top.grid(row=0, column=0, sticky='ew', padx=12, pady=(10, 3))
        tk.Label(top, text='OUR CONVERSATION', bg=PANEL, fg=MUTED,
                 font=('DejaVu Sans', 9, 'bold')).pack(side='left')
        self.copy_button = self.button(top, 'Copy', self.copy_reply)
        self.copy_button.pack(side='right')
        self.transcript_frame = tk.Frame(self.conversation, bg=PANEL)
        self.transcript_frame.grid(row=1, column=0, sticky='nsew', padx=12, pady=4)
        self.transcript = tk.Text(self.transcript_frame, wrap='word', height=1, width=1,
                                  font=('DejaVu Sans', self.font_size), bg=PANEL, fg=INK,
                                  relief='flat', bd=0, padx=2, pady=5, spacing3=6,
                                  insertbackground=INK, selectbackground='#c0d8ad', state='disabled')
        scrollbar = ttk.Scrollbar(self.transcript_frame, orient='vertical', command=self.transcript.yview)
        self.transcript.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side='right', fill='y')
        self.transcript.pack(side='left', fill='both', expand=True)
        self.transcript.tag_configure('role', foreground=MUTED, font=('DejaVu Sans', 9, 'bold'), spacing1=12)
        self.transcript.tag_configure('notice', foreground='#805127', font=('DejaVu Sans', 10))
        self.transcript.tag_configure('code', background='#e0e8d3', font=('DejaVu Sans Mono', max(10, self.font_size - 1)))
        self.notice = tk.Label(self.conversation, text='', bg=PANEL, fg='#805127',
                               justify='left', anchor='w', font=('DejaVu Sans', 9))
        self.notice.grid(row=2, column=0, sticky='ew', padx=12)
        compose = tk.Frame(self.conversation, bg='#d8e4cb')
        compose.grid(row=3, column=0, sticky='ew', padx=12, pady=(4, 6))
        compose.grid_columnconfigure(0, weight=1)
        self.entry = tk.Text(compose, height=2, width=1, wrap='word', font=('DejaVu Sans', self.font_size),
                             bg='#f9faef', fg=INK, relief='flat', padx=8, pady=8, undo=True)
        self.entry.grid(row=0, column=0, sticky='ew')
        self.entry.bind('<Return>', self.send_message)
        self.entry.bind('<Shift-Return>', lambda event: None)
        self.send_button = self.button(compose, 'Send', self.send_message, True)
        self.send_button.grid(row=0, column=1, sticky='ns')
        controls = tk.Frame(self.conversation, bg=PANEL)
        controls.grid(row=4, column=0, sticky='ew', padx=12, pady=(0, 10))
        self.talk_button = self.button(controls, 'Talk', self.toggle_recording, True)
        self.talk_button.pack(side='left')
        self.stop_button = self.button(controls, 'Stop', self.controller.stop)
        self.stop_button.pack(side='left', padx=4)
        self.stop_button.configure(state='disabled')
        self.mode_box = ttk.Combobox(controls, textvariable=self.mode,
                                     values=('auto', 'focus', 'play'), state='readonly', width=7)
        self.mode_box.pack(side='right')
        self.mode_box.bind('<<ComboboxSelected>>', lambda event: self.persist())
        history = get_recent_history(12)
        if history:
            for role, content in history:
                self.add_message('YOU' if role == 'user' else 'BMO', content)
                if role == 'assistant':
                    self.last_reply = content
        else:
            self.add_notice('Tap Talk, or write a message. Shift+Enter adds a new line.')

    def persist(self):
        try:
            save_preferences('ui', {'mode': self.mode.get(), 'speak_replies': self.speak_replies.get(),
                                     'face_only': self.face_only.get(), 'fullscreen': self.fullscreen.get(),
                                     'reduced_motion': self.reduced_motion.get()})
        except (OSError, ValueError) as exc:
            self.show_notice(f'Could not save preferences: {exc}')

    def schedule_layout(self, event):
        if event.widget is not self.root or self.closed:
            return
        if self.layout_timer is not None:
            self.root.after_cancel(self.layout_timer)
        self.layout_timer = self.root.after(60, self.relayout)

    def relayout(self):
        self.layout_timer = None
        layout = layout_for(self.root.winfo_width(), self.root.winfo_height(), self.face_only.get())
        x, y, width, height = layout.face
        self.face_panel.place(x=x, y=y, width=width, height=height)
        if self.face_only.get():
            self.conversation.place_forget()
            self.face_talk.place(relx=.5, rely=1., y=-16, anchor='s')
            self.face_hint.place_forget()
        else:
            x, y, width, height = layout.conversation
            self.conversation.place(x=x, y=y, width=width, height=height)
            self.face_talk.place_forget()
            self.face_hint.place(relx=.5, rely=.95, anchor='s')
            self.notice.configure(wraplength=max(100, width - 28))
            self.entry.configure(height=1 if height < 300 else 2)
            if height < 260:
                self.conversation_header.grid_remove()
                self.notice.grid_remove()
            else:
                self.conversation_header.grid()
                self.notice.grid()
        self.view_button.configure(text='Chat' if self.face_only.get() else 'Face')
        self.settings_button.configure(text='⋯' if self.root.winfo_width() < 450 else 'Settings')

    def toggle_face(self):
        self.face_only.set(not self.face_only.get())
        self.unread = False
        self.relayout()
        self.persist()

    def toggle_fullscreen(self, event=None):
        self.fullscreen.set(not self.fullscreen.get())
        self.root.attributes('-fullscreen', self.fullscreen.get())
        self.persist()
        return 'break'

    def escape(self, event=None):
        if self.controller.busy:
            self.controller.stop()
        elif self.fullscreen.get():
            self.toggle_fullscreen()
        elif self.face_only.get():
            self.toggle_face()
        return 'break'

    def look_at(self, event):
        width, height = max(1, self.face.winfo_width()), max(1, self.face.winfo_height())
        self.renderer.motion.look_at(event.x / width * 2 - 1, event.y / height * 2 - 1, time.monotonic() - self.started)

    def face_tap(self, event):
        if not self.controller.busy:
            self.renderer.motion.set_expression('warm', time.monotonic() - self.started)

    def animate(self):
        if self.closed:
            return
        self.renderer.motion.reduced = self.reduced_motion.get()
        self.renderer.draw(time.monotonic() - self.started)
        interval = 250 if self.root.state() == 'iconic' else round(1000 / (min(20, self.fps) if self.voice_state == 'Ready' else self.fps))
        self.draw_timer = self.root.after(interval, self.animate)

    def insert(self, text, tag=None):
        bottom = self.transcript.yview()[1] >= .98
        self.transcript.configure(state='normal')
        self.transcript.insert('end', text, tag or ())
        self.transcript.configure(state='disabled')
        if bottom:
            self.transcript.see('end')

    def add_message(self, role, text):
        self.insert(role + '\n', 'role')
        self.insert(text + '\n\n')
        self.trim_transcript()

    def add_notice(self, text):
        self.insert(text + '\n\n', 'notice')

    def trim_transcript(self):
        # bound only the visible widget; persistent history is untouched
        if int(self.transcript.index('end-1c').split('.')[0]) > 2500:
            self.transcript.configure(state='normal')
            self.transcript.delete('1.0', '600.0')
            self.transcript.configure(state='disabled')

    def show_notice(self, text):
        self.notice.configure(text=text[:220])
        if text:
            self.add_notice(text)

    def send_message(self, event=None):
        if event is not None and event.state & 0x0001:
            return None
        message = self.entry.get('1.0', 'end-1c').strip()
        if not message:
            return 'break'
        if self.controller.start(message, self.speak_replies.get(), self.mode.get()):
            self.entry.delete('1.0', 'end')
            self.notice.configure(text='')
            self.update_controls(True)
        return 'break'

    def toggle_recording(self, event=None):
        if self.voice_state == 'Listening':
            self.controller.stop_recording()
        elif not self.controller.busy:
            if self.controller.start(speak=self.speak_replies.get(), mode=self.mode.get()):
                self.notice.configure(text='')
                self.update_controls(True)
        return 'break'

    def update_controls(self, busy):
        self.send_button.configure(state='disabled' if busy else 'normal')
        self.stop_button.configure(state='normal' if busy else 'disabled')
        listening = self.voice_state == 'Listening'
        for button in (self.talk_button, self.face_talk):
            button.configure(text='Finish' if listening else 'Talk',
                             state='normal' if listening or not busy else 'disabled')

    def poll_events(self):
        if self.closed:
            return
        try:
            # process a bounded batch so heavy streaming cannot starve drawing
            for _ in range(400):
                kind, value = self.controller.events.get_nowait()
                self.handle_event(kind, value)
        except Empty:
            pass
        self.poll_timer = self.root.after(30, self.poll_events)

    def handle_event(self, kind, value):
        now = time.monotonic() - self.started
        if kind == 'heard':
            self.add_message('YOU', value)
            self.reply_open = False
            self.streaming_reply = ''
        elif kind == 'token':
            if not self.reply_open:
                self.insert('BMO\n', 'role')
                self.reply_start = self.transcript.index('end-1c')
                self.reply_open = True
            self.streaming_reply += value
            self.insert(value)
        elif kind == 'reply':
            if not self.reply_open:
                self.add_message('BMO', value)
            else:
                self.insert('\n\n')
                self.format_code(self.reply_start, value)
            self.reply_open = False
            self.last_reply = value
            self.trim_transcript()
            if self.face_only.get():
                self.view_button.configure(text='Chat •')
        elif kind == 'state':
            self.voice_state = value
            self.renderer.motion.state = value
            self.status.configure(text=value)
            hints = {'Listening': 'I’m listening.', 'Thinking': 'Let me think.', 'Speaking': '',
                     'Transcribing': 'One moment.', 'Ready': 'Here with you.',
                     'Preparing voice': 'A moment for my voice.', 'Stopping': 'Stopping…'}
            self.face_hint.configure(text=hints.get(value, value))
            if value == 'Ready' and self.reply_open:
                self.insert('\n\n')
                self.reply_open = False
            self.update_controls(value != 'Ready')
        elif kind == 'audio':
            self.renderer.motion.audio(value, now)
        elif kind == 'input_level':
            if self.voice_state == 'Listening':
                bars = '●' * max(1, min(6, round(value * 6)))
                self.face_hint.configure(text='Listening  ' + bars)
        elif kind == 'expression':
            self.renderer.motion.set_expression(value, now)
        elif kind == 'mode':
            self.renderer.motion.mode = value
        elif kind in ('notice', 'error'):
            if self.reply_open:
                self.insert('\n\n')
                self.reply_open = False
            self.show_notice(value)
        elif kind == 'metrics':
            self.metrics = value

    def format_code(self, start, text):
        import re
        for match in re.finditer(r'```[\s\S]*?(?:```|$)', text):
            self.transcript.tag_add('code', f'{start}+{match.start()}c', f'{start}+{match.end()}c')

    def copy_reply(self):
        selection = ''
        try:
            selection = self.transcript.get('sel.first', 'sel.last')
        except tk.TclError:
            pass
        text = selection or self.last_reply
        if text:
            self.root.clipboard_clear()
            self.root.clipboard_append(text)
            self.notice.configure(text='Copied.')

    def export_chat(self):
        filename = filedialog.asksaveasfilename(parent=self.root, defaultextension='.txt',
                                                initialfile='bmo-conversation.txt', filetypes=[('Text', '*.txt')])
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as file:
                    file.write(self.transcript.get('1.0', 'end-1c'))
            except OSError as exc:
                self.show_notice(str(exc))

    def open_settings(self):
        if self.settings_window is not None and self.settings_window.winfo_exists():
            self.settings_window.lift()
            return
        window = tk.Toplevel(self.root)
        self.settings_window = window
        window.title('BMO settings')
        window.configure(bg=PANEL)
        window.transient(self.root)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        window.geometry(f'{min(430, sw-30)}x{min(550, sh-70)}')
        canvas = tk.Canvas(window, bg=PANEL, highlightthickness=0)
        scroll = ttk.Scrollbar(window, orient='vertical', command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right', fill='y')
        canvas.pack(side='left', fill='both', expand=True)
        body = tk.Frame(canvas, bg=PANEL, padx=18, pady=16)
        item = canvas.create_window(0, 0, window=body, anchor='nw')
        canvas.bind('<Configure>', lambda event: canvas.itemconfigure(item, width=event.width))
        body.bind('<Configure>', lambda event: canvas.configure(scrollregion=canvas.bbox('all')))
        tk.Label(body, text='Make yourself comfortable.', bg=PANEL, fg=INK,
                 font=('DejaVu Sans', 13, 'bold')).pack(anchor='w', pady=(0, 12))
        for label, variable in [('Speak replies', self.speak_replies), ('Reduced motion', self.reduced_motion)]:
            tk.Checkbutton(body, text=label, variable=variable, bg=PANEL, fg=INK,
                           command=self.preference_changed).pack(anchor='w')
        self.button(body, 'Fullscreen / window   F11', self.toggle_fullscreen).pack(fill='x', pady=8)
        tk.Label(body, text='Voice', bg=PANEL, fg=MUTED).pack(anchor='w', pady=(10, 3))
        voice = self.config['voice']
        backend = tk.StringVar(value=voice.get('backend', 'kokoro'))
        ttk.Combobox(body, textvariable=backend, values=('kokoro', 'espeak'), state='readonly').pack(fill='x')
        name = tk.StringVar(value=voice.get('kokoro_voice', 'af_sky'))
        ttk.Combobox(body, textvariable=name, values=('af_sky', 'af_bella', 'af_heart'), state='readonly').pack(fill='x', pady=5)
        speed = tk.DoubleVar(value=voice.get('kokoro_speed', .96))
        pitch = tk.DoubleVar(value=voice.get('pitch_semitones', 0))
        for label, variable, low, high, resolution in [('Pace', speed, .7, 1.3, .02), ('Pitch (needs ffmpeg)', pitch, -3, 4, .25)]:
            tk.Scale(body, label=label, variable=variable, from_=low, to=high, resolution=resolution,
                     orient='horizontal', bg=PANEL, fg=INK, highlightthickness=0).pack(fill='x')
        def apply_voice():
            if self.controller.busy:
                self.show_notice('Finish the current reply before changing the voice.')
                return
            changes = dict(backend=backend.get(), kokoro_voice=name.get(), kokoro_speed=speed.get(), pitch_semitones=pitch.get())
            try:
                save_preferences('voice', changes)
                self.config['voice'].update(changes)
                self.controller.settings.update(changes)
                self.controller.speaker.settings.update(changes)
                self.notice.configure(text='Voice settings saved.')
            except (OSError, ValueError) as exc:
                self.show_notice(str(exc))
        self.button(body, 'Apply voice', apply_voice, True).pack(fill='x', pady=8)
        tk.Label(body, text='Kokoro is a natural local voice, not a clone of the show.\nAuto adapts tone; Focus keeps responses practical.\nCtrl+Space: talk / finish. Escape: stop or leave fullscreen.',
                 wraplength=320, justify='left', bg=PANEL, fg=MUTED, font=('DejaVu Sans', 9)).pack(anchor='w', pady=10)
        self.button(body, 'Export visible conversation', self.export_chat).pack(fill='x')
        self.button(body, 'Close settings', window.destroy).pack(fill='x', pady=8)

    def preference_changed(self):
        if not self.speak_replies.get():
            self.controller.stop_speaking()
        self.persist()

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.controller.close()
        for timer in (self.draw_timer, self.poll_timer, self.layout_timer):
            if timer is not None:
                self.root.after_cancel(timer)
        self.root.destroy()

    def run(self):
        self.root.mainloop()

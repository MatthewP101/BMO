"""small native dialogs; background workers never touch these widgets"""
import time
import tkinter as tk
from tkinter import ttk, simpledialog
from app.config import save_preferences
from app.memory.history import list_chats, rename_chat, archive_chat, create_chat, get_recent_history
from app.memory.memory import get_memories, save_memory, remove_memory
from ui.themes import palette
from ui.face import EXPRESSIONS


def window_for(owner, title, width=490, height=630):
    window = tk.Toplevel(owner.root)
    window.title(title)
    window.transient(owner.root)
    window.configure(bg=palette(owner.palette_name)['panel'])
    window.geometry(f'{min(width,owner.root.winfo_screenwidth()-24)}x{min(height,owner.root.winfo_screenheight()-50)}')
    return window


def open_settings(owner):
    if owner.settings_window is not None and owner.settings_window.winfo_exists():
        owner.settings_window.lift(); return
    window = window_for(owner,'BMO settings')
    owner.settings_window = window
    notebook = ttk.Notebook(window)
    notebook.pack(fill='both',expand=True,padx=8,pady=8)
    p = palette(owner.palette_name)
    def tab(title):
        frame = ttk.Frame(notebook); notebook.add(frame,text=title)
        canvas = tk.Canvas(frame,bg=p['panel'],highlightthickness=0)
        scroll = ttk.Scrollbar(frame,orient='vertical',command=canvas.yview)
        canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side='right',fill='y');canvas.pack(side='left',fill='both',expand=True)
        body = tk.Frame(canvas,bg=p['panel'],padx=12,pady=12)
        item = canvas.create_window(0,0,window=body,anchor='nw')
        canvas.bind('<Configure>',lambda e: canvas.itemconfigure(item,width=e.width))
        body.bind('<Configure>',lambda e: canvas.configure(scrollregion=canvas.bbox('all')))
        return body
    def label(body,text):
        tk.Label(body,text=text,bg=p['panel'],fg=p['muted'],anchor='w',justify='left',wraplength=370).pack(fill='x',pady=(10,3))
    def check(body,text,variable):
        tk.Checkbutton(body,text=text,variable=variable,bg=p['panel'],fg=p['ink'],
                       command=owner.preference_changed).pack(anchor='w')
    look = tab('Face & colour')
    label(look,'BMO colour · appearance only')
    theme = ttk.Combobox(look,textvariable=owner.theme,values=('classic','pink'),state='readonly')
    theme.pack(fill='x')
    theme.bind('<<ComboboxSelected>>',lambda e: (owner.apply_theme(owner.theme.get()),owner.persist()))
    label(look,'Blushing')
    blush = ttk.Combobox(look,textvariable=owner.blush,values=('auto','always','off'),state='readonly')
    blush.pack(fill='x');blush.bind('<<ComboboxSelected>>',lambda e: owner.persist())
    tk.Scale(look,label='Blush strength',variable=owner.blush_strength,from_=0,to=1,resolution=.05,
             orient='horizontal',bg=p['panel'],fg=p['ink'],highlightthickness=0,
             command=lambda v: None).pack(fill='x')
    look.winfo_children()[-1].bind('<ButtonRelease-1>',lambda e: owner.persist())
    check(look,'Gentle idle animations',owner.idle_animations)
    check(look,'Reduced motion',owner.reduced_motion)
    label(look,'Try an expression')
    expression = tk.StringVar(value='blush')
    ttk.Combobox(look,textvariable=expression,values=EXPRESSIONS,state='readonly').pack(fill='x')
    def preview():
        if owner.controller.busy:
            owner.show_notice('Try an expression after this reply.'); return
        owner.renderer.motion.mode = 'companion'
        owner.renderer.motion.set_expression(expression.get(),time.monotonic()-owner.started)
    owner.button(look,'Show expression',preview,True).pack(fill='x',pady=8)
    owner.button(look,'Fullscreen / window   F11',owner.toggle_fullscreen).pack(fill='x')
    label(look,'Auto blush follows affection and gentle reactions. Tap BMO’s face for a small blush. Game over and winks are brief gestures.')

    voice_tab = tab('Voice')
    check(voice_tab,'Speak replies',owner.speak_replies)
    settings = owner.config['voice']
    backend = tk.StringVar(value=settings.get('backend','pocket'))
    label(voice_tab,'Speech engine')
    ttk.Combobox(voice_tab,textvariable=backend,values=('pocket','espeak'),state='readonly').pack(fill='x')
    profiles = settings.get('profiles',{})
    current = settings.get('reference_voice','')
    profile_name = next((name for name,path in profiles.items() if path==current),'Current reference' if current else 'Bundled voice')
    choices = {'Bundled voice':'' , **profiles}
    if current and current not in choices.values(): choices['Current reference']=current
    selected = tk.StringVar(value=profile_name)
    label(voice_tab,'Voice reference')
    ttk.Combobox(voice_tab,textvariable=selected,values=tuple(choices),state='readonly').pack(fill='x')
    name = tk.StringVar(value=settings.get('pocket_voice','azelma'))
    label(voice_tab,'Bundled voice (used only when selected above)')
    ttk.Combobox(voice_tab,textvariable=name,values=('azelma','cosette','eponine','alba','fantine'),state='readonly').pack(fill='x')
    pace = tk.DoubleVar(value=settings.get('pace',1.))
    pitch = tk.DoubleVar(value=settings.get('pitch_shift',0.))
    volume = tk.DoubleVar(value=settings.get('volume',.85))
    for title,var,low,high,step in [('Pace',pace,.9,1.1,.01),('Pitch · semitones',pitch,-1.5,1.5,.1),('Volume',volume,0,1,.05)]:
        tk.Scale(voice_tab,label=title,variable=var,from_=low,to=high,resolution=step,orient='horizontal',
                 bg=p['panel'],fg=p['ink'],highlightthickness=0).pack(fill='x')
    def apply_voice():
        if owner.controller.busy or owner.controller.warming.is_set():
            owner.show_notice('Wait for speech or voice warm-up to finish before applying voice settings.');return False
        changes=dict(backend=backend.get(),reference_voice=choices[selected.get()],pocket_voice=name.get(),
                     pace=pace.get(),pitch_shift=pitch.get(),volume=volume.get(),profiles=dict(profiles))
        try:
            save_preferences('voice',changes)
            owner.config['voice'].update(changes)
            owner.controller.settings.update(changes)
            owner.controller.speaker.settings.update(changes)
            owner.notice.configure(text='Voice settings saved.')
            return True
        except (OSError,ValueError) as exc:
            owner.show_notice(str(exc));return False
    def test_voice():
        if apply_voice():
            owner.controller.say('Oh, hello, Matthew. I have a very small adventure in mind.')
    owner.button(voice_tab,'Apply voice',apply_voice,True).pack(fill='x',pady=6)
    owner.button(voice_tab,'Test voice',test_voice).pack(fill='x')
    owner.button(voice_tab,'Replay last reply',lambda: owner.controller.say(owner.last_reply)).pack(fill='x',pady=6)
    label(voice_tab,'Start at pace 1.00 and pitch 0.00. Small changes can help; large changes distort the reference. Tuning needs ffmpeg. Saved references remain available here.')

    chat = tab('Chats & speed')
    owner.button(chat,'Browse conversations',owner.open_chats,True).pack(fill='x',pady=5)
    owner.button(chat,'Notes in this chat',owner.open_notes).pack(fill='x',pady=5)
    owner.button(chat,'Export this chat',owner.export_chat).pack(fill='x',pady=5)
    check(chat,'Warm models when BMO starts',owner.warm_start)
    llm = owner.bmo.llm.settings
    fast = tk.BooleanVar(value=llm.get('fast_replies',True))
    notes = tk.BooleanVar(value=llm.get('include_memories',False))
    history = tk.StringVar(value=str(llm.get('history_messages',2)))
    tk.Checkbutton(chat,text='Fast replies',variable=fast,bg=p['panel'],fg=p['ink']).pack(anchor='w')
    tk.Checkbutton(chat,text='Include this chat’s saved notes',variable=notes,bg=p['panel'],fg=p['ink']).pack(anchor='w')
    label(chat,'Recent messages sent to the model')
    ttk.Combobox(chat,textvariable=history,values=('0','2','4','6','8'),state='readonly').pack(fill='x')
    def apply_speed():
        if owner.controller.busy:
            owner.show_notice('Finish this reply before changing context settings.');return
        changes=dict(fast_replies=fast.get(),include_memories=notes.get(),history_messages=int(history.get()))
        try:
            save_preferences('llm',changes);llm.update(changes)
            owner.notice.configure(text='Reply settings saved.')
        except (OSError,ValueError) as exc: owner.show_notice(str(exc))
    owner.button(chat,'Apply reply settings',apply_speed,True).pack(fill='x',pady=8)
    label(chat,'All messages are stored in their own chat. This setting controls how much recent context is sent to Qwen, not how much is saved. More context can make replies slower.')
    timings=[]
    for key,title in [('first_token_seconds','First text'),('first_audio_seconds','First sound')]:
        value=owner.metrics.get(key)
        if isinstance(value,(int,float)):timings.append(f'{title}: {value:.2f}s')
    if timings:label(chat,'Last reply: '+', '.join(timings))
    owner.apply_theme(owner.theme.get())


def open_chats(owner):
    if owner.chats_window is not None and owner.chats_window.winfo_exists():
        owner.chats_window.lift();return
    window=window_for(owner,'Conversations',560,550);owner.chats_window=window
    p=palette(owner.palette_name)
    search=tk.StringVar();archived=tk.BooleanVar(value=False)
    tk.Label(window,text='Search titles and messages',bg=p['panel'],fg=p['muted']).pack(anchor='w',padx=12,pady=(10,3))
    entry=tk.Entry(window,textvariable=search);entry.pack(fill='x',padx=12)
    listing=tk.Listbox(window,exportselection=False,bg=p['entry'],fg=p['ink'],selectbackground=p['selection'],bd=0)
    listing.pack(fill='both',expand=True,padx=12,pady=8)
    rows=[]
    def refresh(*args):
        rows[:]=list_chats(search.get(),archived.get());listing.delete(0,'end')
        for i,row in enumerate(rows):
            listing.insert('end',f"{row['title']}   ·   {row['messages']} messages")
            if row['id']==owner.bmo.chat_id:listing.selection_set(i)
    def selected():
        indices=listing.curselection();return rows[indices[0]] if indices else None
    def act(action):
        row=selected()
        if not row:return
        if owner.controller.busy:
            owner.show_notice('Finish or stop the current reply before changing chats.');return
        if action=='open':
            if archived.get():archive_chat(row['id'],False)
            owner.switch_chat(row['id']);window.destroy()
        elif action=='rename':
            title=simpledialog.askstring('Rename chat','Chat name:',initialvalue=row['title'],parent=window)
            if title and title.strip():rename_chat(row['id'],title)
            refresh()
        elif action=='archive':
            archive_chat(row['id'],not archived.get())
            if row['id']==owner.bmo.chat_id and not archived.get():
                active=list_chats();owner.switch_chat(active[0]['id'] if active else create_chat())
            refresh()
    entry.bind('<Return>',refresh)
    listing.bind('<Double-Button-1>',lambda e: act('open'))
    options=tk.Frame(window,bg=p['panel']);options.pack(fill='x',padx=12)
    owner.button(options,'Search',refresh).pack(side='left')
    tk.Checkbutton(options,text='Archived',variable=archived,command=refresh,bg=p['panel'],fg=p['ink']).pack(side='right')
    buttons=tk.Frame(window,bg=p['panel']);buttons.pack(fill='x',padx=12,pady=8)
    for text,action in [('Open','open'),('Rename','rename'),('Archive / restore','archive')]:
        owner.button(buttons,text,lambda a=action: act(a),action=='open').pack(fill='x',pady=2)
    def earlier():
        if owner.controller.busy:return
        offset=owner.history_offset+owner.history_limit
        if get_recent_history(1,owner.bmo.chat_id,offset):
            owner.history_offset=offset;owner.load_current_chat()
            owner.transcript.see('1.0');window.destroy()
    owner.button(window,'Earlier messages in the current chat',earlier).pack(fill='x',padx=12,pady=(0,10))
    owner.button(window,'Latest messages in the current chat',lambda: (owner.latest_page(),window.destroy())).pack(fill='x',padx=12,pady=(0,10))
    refresh();owner.apply_theme(owner.theme.get())


def open_notes(owner):
    window=window_for(owner,'Notes in this chat',480,450)
    chat_id=owner.bmo.chat_id;p=palette(owner.palette_name)
    tk.Label(window,text='These notes belong only to this conversation.',bg=p['panel'],fg=p['muted']).pack(padx=12,pady=10)
    listing=tk.Listbox(window,exportselection=False,bg=p['entry'],fg=p['ink']);listing.pack(fill='both',expand=True,padx=12)
    note=tk.StringVar();entry=tk.Entry(window,textvariable=note);entry.pack(fill='x',padx=12,pady=8)
    values=[]
    def refresh():
        values[:]=get_memories(chat_id);listing.delete(0,'end')
        for value in values:listing.insert('end',value)
    def add():
        if note.get().strip():save_memory(note.get()[:2000],chat_id);note.set('');refresh()
    def remove():
        indices=listing.curselection()
        if indices:remove_memory(values[indices[0]],chat_id);refresh()
    controls=tk.Frame(window,bg=p['panel']);controls.pack(fill='x',padx=12,pady=8)
    owner.button(controls,'Save note',add,True).pack(side='left')
    owner.button(controls,'Remove selected',remove).pack(side='right')
    entry.bind('<Return>',lambda e:add());refresh();owner.apply_theme(owner.theme.get())

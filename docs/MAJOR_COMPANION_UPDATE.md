# Expressions, voice controls and separate chats

This update builds on the working Pocket reference voice. Existing voice files,
model selection, audio devices and personal preferences are retained. Python 3.13
and 3.14 remain supported; the requirements have not changed.

## Pull and run

Close BMO, then run on the MACO:

```bash
cd ~/BMO/BMO
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
sudo apt install ffmpeg
python -m app.main
```

ffmpeg is only needed when changing voice pace or pitch. With pace **1.00** and
pitch **0.00**, Pocket audio takes the existing direct playback path. Your current
reference stays selected after pulling. Ollama still runs as its separate service;
BMO sends requests to it. Keep your existing Qwen model.

## Face and personality

Open **Settings → Face & colour**:

- **Classic / pink:** changes the face and interface palette only. Pink does not
  change character instructions, voice, memory or task behaviour.
- **Blushing: auto / always / off**, with an intensity slider. Auto responds to
  affection, thanks and gentle reactions; tapping BMO's face gives a brief blush.
- **Gentle idle animations** and **Reduced motion** control movement. Mouth motion
  still follows speech amplitude. After two quiet minutes, idle BMO becomes sleepy.
- **Try an expression** previews any of the twelve states. Game over and winks
  expire automatically, and the face eases back to its resting expression.

The states are neutral, warm, blush, happy, curious, attentive, gentle, surprised,
sleepy, wink, heart eyes (`love`) and `game_over`. Type or say **game over**, **wink**,
**blush** or **show heart eyes** for an immediate local gesture. These exact commands
work in Auto or Play; Focus reserves the turn for a normal serious response.

BMO reacts at the beginning of a turn instead of waiting for the complete answer.
Affection can bring shy pride, successful moments a small bounce, and questions a
curious look. Serious work and distress suppress playful reactions. Expression
selection uses message cues; it is not an emotion-recognition model and can miss nuance.

The character core adds independence, make-believe jobs, a little vanity, courage,
vulnerability and thoughtful affection. Only the scene direction relevant to the
message is appended, keeping routine prompts compact. Original dialogue examples
encourage short, varied, speakable lines without constant catchphrases or a written
imitation of an accent. Focus prioritises useful, accurate answers over performance.
Qwen's wording and judgement still depend on the model.

The face and transcript remain separate panels. Long answers scroll inside the
conversation. Layout adapts to portrait, landscape and fullscreen; **F11** toggles
fullscreen and **Face** hides the conversation. The animation reuses its canvas
items and runs at a lower frame rate while idle or minimised.

## Voice comparison

Open **Settings → Voice** to select saved references, adjust pace, pitch and volume,
then **Apply voice**. **Test voice** plays a short line without asking Qwen or adding
a chat message. **Replay last reply** uses the current applied voice. Settings cannot
change a voice while it is loading or speaking.

Start with the current reference at pace **1.00**, pitch **0.00**. Adjust one control
at a time in small steps. Pitch ranges from −1.5 to +1.5 semitones and pace from 0.90
to 1.10; the controls are deliberately subtle. This is an audition facility, not a
claim that a particular setting is a closer character match. Processing adds a
small buffer and may increase first-sound latency.

A separately supplied `bmo-reference-expressive.wav` contains 12.84 seconds from the
uploaded clip: 5.40–10.12, 10.82–13.94 and 15.02–19.52, separated by two 0.25-second
pauses. It includes more of BMO's delivery and the final discovery line, stopping
before Jake's closing responses. It is 24 kHz mono, 16-bit PCM with short edge fades
and about −3.1 dBFS peak. Transcription and timing checks support these selections;
subjective listening and a reference-model audition must be done on your device.
The recording is not included in the public repository.

To compare it, download the supplied WAV to Downloads, close BMO and run:

```bash
python -m app.voice --reference "$HOME/Downloads/bmo-reference-expressive.wav" --name "Expressive BMO"
python -m app.voice --test-voice
python -m app.main
```

This prepares and selects the new reference only after export succeeds. **Original
BMO** remains in Settings alongside **Expressive BMO**. Reusing a profile name retains
its previous value under a separate name. Existing Hugging Face model access is
still needed to prepare a new reference; see [reference setup](FAST_VOICE.md).
The working exported voice can continue to run without preparing another one.
A longer reference may improve or worsen similarity; choose by listening.

To audition processing without saving it:

```bash
python -m app.voice --test-voice --pace 0.98 --pitch 0.3
```

## Chats, notes and files

- **+** or **Ctrl+N** starts a separate conversation. The first message names it.
- **Chats** searches titles and saved messages, opens or renames conversations,
  and archives/restores them. Archiving hides a chat; it does not delete its contents.
- **Earlier messages** browses older pages of 200 messages; **Latest messages**
  returns to the present. Sending a message also returns to the latest page.
- **Settings → Chats & speed → Notes in this chat** adds, lists or removes explicit
  notes. “Remember …” and “What do you remember?” use only this chat's notes.
- **Export this chat** exports the complete saved transcript, even when only a
  recent page is displayed. Failed/cancelled model turns are not saved.
- **Attach** reads one selected UTF-8 text/source file into an editable draft,
  limited to a 6,000-character excerpt. Add a question, then Send. It does not execute
  or modify the file. Code stays on screen during speech and replay.

The first launch makes an additive SQLite migration. Old messages and notes appear
under **Earlier conversations**; a `data/bmo-before-chats.db` snapshot is created
before an existing database is upgraded. It is never overwritten by later launches.
All databases, journals, private settings and voice embeddings stay ignored by git.
Each completed user/assistant exchange is committed atomically in its own chat.

This update does not add email account access, remote desktop control, autonomous
file edits or shell execution. Those need separate tool implementations.

## Reply speed

**Settings → Chats & speed** controls how much context Qwen receives. All messages
are saved, but by default only the latest two messages (one exchange, up to 1,800
characters) are sent. Saved notes are excluded from routine prompts unless enabled.
Choose **0** recent messages for minimum history overhead.

**Warm models when BMO starts** loads the selected voice and asks Ollama to load the
configured model in background threads, without creating a chat. Turn it off if you
prefer to defer model loading. Spoken answers still start at sentence boundaries
while Qwen generates the rest. Short repeated utterances have a six-entry PCM cache,
bounded to 20 seconds each; replay and voice comparisons can reuse synthesis.

Fast mode keeps the existing 4,096-token context and 160-token chat / 700-token Focus
limits. Inputs over 6,000 characters use a larger context. Settings shows measured
first-text and first-sound times for the last turn. Long history, long explanations,
CPU contention and initial downloads can still make responses slower.

## Verification

```bash
python -m unittest discover -s tests -v
python scripts/check_setup.py
python -m app.voice --output /tmp/bmo-voice-check.wav --pace 0.98 --pitch 0.3
```

All **81 tests passed on both Python 3.13.14 and 3.14.6**. The checks cover migration/backup preservation, atomic turns,
chat/note isolation, paging, queued UI events during chat switching, early reactions,
serious-mode precedence, every expression's bounds, blush controls, theme separation,
reference-profile preservation, speech caching, pitch/tempo processing, cancellation,
streaming, code suppression and the earlier voice/agent behaviour.

Actual offline Pocket synthesis with pace 0.98 and pitch +0.3 succeeded on CPython
3.13.14 and 3.14.6. For one short test line, first PCM arrived in **0.295 s** and
**0.775 s** respectively after model loading; full synthesis took **1.918 s** and
**2.861 s**. These individual runs are not a Python-version comparison, complete
Qwen-turn measurements, hardware playback tests or MACO benchmarks.

All twelve face states were rendered and inspected in both palettes using the same
geometry as the app. A real display-server launch was blocked by the build workspace,
so live Tkinter appearance, touchscreen behaviour, microphone/speaker output and exact
voice similarity remain local checks. The user's working reference embedding is
only on the MACO; it was not replaced or falsely auditioned on the build machine.

For an optional developer animation preview (requires Pillow):

```bash
python scripts/preview_face.py /tmp/bmo-expressions.gif --sheet /tmp/bmo-expressions.png
```

Audio processing follows [FFmpeg's filter documentation](https://ffmpeg.org/ffmpeg-filters.html#asetrate).
Model preloading uses the [Ollama generate API](https://docs.ollama.com/api/generate).

# Expressive BMO update

Prepared against MatthewP101/BMO commit `6157c8d84798f2b0dcc2e3ab7db36e99bc888d97` (Personality Update).

This is a native Python/Tkinter update. It replaces the rigid face and expanding labels with a responsive animated face and a separate scrollable conversation area. It retains local Qwen, Whisper and SQLite memory.

## Install on the MACO

Close the running BMO app. Extract `BMO-expressive-update.zip` in Downloads. From the repository terminal:

```bash
cd ~/BMO/BMO
git status --short
python3 ~/Downloads/BMO-expressive-update/apply_update.py
source .venv/bin/activate
python --version
python -m pip install -r requirements.txt
sudo apt install libportaudio2 espeak-ng ffmpeg
python -m app.voice --download-voice
python scripts/check_setup.py
python -m app.main
```

The updater first runs `git apply --check`. It stops on conflicting edits and does not force anything, commit, push, edit personal settings, delete files, touch your database, or download software. If the check fails, keep the output and your working files; do not reset the repository. The patch is also included as `BMO-expressive.patch` for manual review and application.

Use Python **3.10–3.13** for the pinned Kokoro package; Ubuntu Python 3.12 is suitable. If your existing environment uses Python 3.14, keep it and create a separate environment with an installed supported interpreter. Do not replace system Python. The new dependency install and the voice model need internet once. The voice download is about **354 MB**. Ollama and the downloaded Qwen model are still required; no new LLM download is necessary.

After reviewing in VS Code and testing:

```bash
git add .gitignore app ui config/config.example.json requirements.txt tests scripts/check_setup.py scripts/preview_face.py docs/EXPRESSIVE_UPDATE.md docs/VOICE_SETUP.md README.md
git commit -m "Add expressive face, responsive chat and neural speech"
git push
```

The patch does not apply these Git commands automatically.

## What changes

- A mint screen with BMO's simple oval eyes and curved mouth. All face features use proportional geometry, so resizing never leaves the eyes behind.
- Time-based motion, eased expression transitions, irregular blinks, small eye movements and restrained head movement. Listening, thinking and speaking produce distinct behaviour. Random angry/sad expression rotation is removed.
- The actual playback signal controls mouth opening and shape. Pauses close the mouth; stopped/stale audio also closes it. This is amplitude-driven animation, not phoneme-accurate lip sync.
- The existing rich personality now lives in `app/agent/personality.py`. Greetings and status questions go through Qwen instead of bypassing it.
- Auto mode uses practical/sensitive-language cues plus model instructions. Focus explicitly suppresses jokes and roleplay; Play invites imagination but practical/distress cues take precedence. This is heuristic tone selection, not emotion detection.
- Model text streams into a selectable transcript. Focus responses have a larger generation allowance for explanations and code. Reaching the limit is reported instead of silently claiming a complete answer.
- Speech uses local Kokoro ONNX with selectable Sky, Bella and Heart voices. The engine stays loaded between turns and its CPU thread count is bounded. No cloud voice service or API key is configured.
- Long answers stay entirely in the transcript. Speech reads a bounded prose portion, skips fenced code and simplifies markdown/links. It begins after the written answer finishes generating; synthesis then works in short chunks.
- Talk starts the microphone explicitly. It can finish after a pause following detected speech, or manually with Finish. The microphone closes before playback; no background wake word or always-listening mode is added.
- Personal configuration merges with new defaults, preserving device selection and other existing keys. UI preferences persist. The old `num_predict` key is replaced by `chat_tokens` and `focus_tokens`.

## Controls

| Control | Result |
| --- | --- |
| Talk / Ctrl+Space | Start recording; press again while Listening to finish |
| Stop / Ctrl+. | Stop capture, request model cancellation and stop speech |
| Enter | Send the written message |
| Shift+Enter | Insert a new line |
| Ctrl+L | Focus the message field |
| Face / Chat | Show the entire face or return to the conversation |
| F11 | Toggle fullscreen |
| Escape | Stop an active turn; otherwise leave fullscreen or face-only mode |
| Copy | Copy selected transcript text, or the latest reply |
| Settings | Voice, pace, pitch, speech mute, reduced motion, fullscreen, transcript export |

In face-only view, Chat gains a dot when a reply arrives. No long text is overlaid on the face. There is a touchable Talk/Finish control below the facial features. On narrow or portrait windows, chat sits below the face; on sufficiently wide windows, it sits alongside. Very short windows hide the conversation heading to preserve input space. Windowed startup fits the display; F11 uses the full screen. Monitor changes/resizing recompute the layout.

Stop is immediate for the microphone and between audio blocks. An in-progress model network read or neural synthesis call must return before the worker becomes ready for a new turn; the face/UI remain responsive. Ollama requests have a timeout. Closing the app requests shutdown and daemon workers do not keep the process open. An interrupted partial answer can remain visible but is not saved as a completed conversation turn.

## Voice realism

Kokoro is a natural stock voice, **not the voice actor's BMO performance and not a trained BMO clone**. The bundled dialogue examples are original. No show recordings, cloned voices or copyrighted audio are included. Sky is a starting point, not a guarantee that it sounds closest on your speakers.

Compare on your actual speaker:

```bash
python -m app.voice --test-voice --voice af_sky
python -m app.voice --test-voice --voice af_bella
python -m app.voice --test-voice --voice af_heart
```

Choose the best base in Settings. Adjust pace first; try small pitch changes only if useful. Pitch uses ffmpeg and preserves approximate duration, but large shifts can sound artificial. Matching the recognisable original timbre requires a suitable custom voice model or reference-driven speech backend, which is beyond a stock-voice preset. This update deliberately does not claim that goal has already been achieved.

If neural model files are missing, BMO keeps displaying replies and shows the download command. It does not silently revert to the old robotic voice. You can explicitly select `espeak` in Settings if needed.

## Performance and tuning

The default model remains `qwen3.5:4b`. CPU inference is assumed; Radeon acceleration is not promised. The existing deep personality requires at least an 8192-token context; messages over 6000 characters use at least 16384. More context needs more memory and time. Shorter questions help on CPU. Normal replies allow 360 generated tokens; Focus allows 1400. Adjust `llm.chat_tokens`, `llm.focus_tokens` and `llm.timeout` in personal config as needed. No default setting can guarantee a particular tokens-per-second rate on your machine.

The face reuses six canvas items instead of deleting/recreating them. It runs at up to 40 frames/s during interaction, 20 when ready, and throttles when minimised. Reduced motion removes drifting, tilting and leaning. It keeps essential blink/speech feedback.

Voice settings: `kokoro_speed`, `pitch_semitones`, `volume`, `max_spoken_chars`, `auto_finish`, `speech_threshold`, `silence_seconds`. If recordings end prematurely, raise `silence_seconds` or disable `auto_finish`. If the microphone never detects speech, check its selected input and gain before adjusting the threshold. Quiet rooms and close microphones produce better results than changing a number blindly.

## Validation and limits

Run the functional suite:

```bash
python -m unittest discover -s tests -v
```

Automated checks cover streamed responses, cancellation and disconnects, saved history, serious-tone routing, configuration merging, silence filtering, recording bounds, voice failure recovery, playback lifecycle, speech text cleanup, finite face geometry, audio-driven mouth closure, reduced motion and non-overlapping layout rectangles at six display sizes. Neural synthesis and hardware are mocked; these tests do not establish perceived voice similarity or live model quality.

The included GIF is a rendering of the actual face geometry and animation using a synthetic audio envelope. It is a motion preview, not a screenshot of a live conversation. To reproduce it, install Pillow in a development environment and run `python scripts/preview_face.py preview.gif`.

This build environment has no usable graphical display or audio devices, and could not install/download the neural runtime/models. Live Tkinter font/layout appearance, neural voice inference, microphone/speaker quality and MACO speed still require a real-device smoke test. In particular, check F11 at 1560×720, the portrait orientation, a long fenced code response, and Stop during speech.

File/email/desktop execution tools remain unimplemented; the persona is explicitly told not to claim those abilities. Automatic humour selection and Qwen's character consistency are best-effort, not guarantees.

## Sources

- [Kokoro ONNX engine and installation](https://github.com/thewh1teagle/kokoro-onnx)
- [Pinned voice model files](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0)
- [Kokoro voice descriptions](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)
- [Ollama chat streaming API](https://docs.ollama.com/api/chat)

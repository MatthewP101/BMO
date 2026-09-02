# BMO voice — first local version

This patch adds local conversation, click-to-record microphone input and spoken replies to the existing Python/Tkinter face. It targets MatthewP101/BMO main tree `4a904d4cd4d9f1aac7f31517198f9758ba1cc878`. No GitHub branch or remote files were changed to produce it.

## What runs where

- **Brain:** Qwen3.5:4b through Ollama on this PC, at `http://127.0.0.1:11434`.
- **Hearing:** faster-whisper `base.en`, running on the CPU with int8 computation.
- **Speech:** eSpeak NG, an adjustable synthetic robot voice. This is a functional placeholder, not the original BMO voice or a voice clone.
- **Memory:** the existing local SQLite database. Recent conversation and saved memories are included in model requests.
- After the initial software/model downloads, this configured conversation path runs locally without an API key. No cloud fallback is configured. Latency and audio quality must be measured on the MACO; GPU acceleration is not assumed.

The LLM produces the words; speech recognition and speech synthesis are separate components. The face keeps animating during inference. Mouth animation runs during playback, but is not phoneme-level lip sync.

## 1. Apply the code patch

Save `BMO-voice.patch` to Downloads, then in VS Code's terminal:

```bash
cd ~/BMO/BMO
git status --short
git apply --check ~/Downloads/BMO-voice.patch
git apply ~/Downloads/BMO-voice.patch
```

The check is read-only and should print nothing on success. **If it reports an error, stop and share that output.** Do not force the patch or reset your files. The apply command changes your working files only; it does not commit, push or overwrite your database. Review the modifications in VS Code Source Control.

## 2. Install Ubuntu dependencies

```bash
sudo apt update
sudo apt install python3-venv python3-tk libportaudio2 espeak-ng curl
```

Create the virtual environment only if `.venv` does not already exist:

```bash
python3 -m venv .venv
```

Then activate it and install the Python dependencies:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The package requirements have version bounds rather than a platform lockfile. This implementation was tested with Python 3.12. A successful dependency install and a real-device smoke test are still required on your Ubuntu installation.

## 3. Install Ollama and download the brain

If `ollama --version` works, skip installation. Otherwise use Ollama's documented Linux installer:

```bash
curl -fsSL https://ollama.com/install.sh -o /tmp/bmo-ollama-install.sh
sh /tmp/bmo-ollama-install.sh
```

Download the selected model:

```bash
ollama pull qwen3.5:4b
```

If Ollama reports it cannot connect, start `ollama serve` in another terminal and leave it running, then repeat the pull. Do not start a second server if the service is already running.

The model is a multi-gigabyte download. The first response also needs to load it into memory. Keep Ollama bound to localhost for this first version.

## 4. Download the hearing model and check devices

With the virtual environment active:

```bash
python -m app.voice --download-model
python -m app.voice --devices
```

The first command downloads Whisper into `models/whisper/`, which is ignored by Git. It needs internet access the first time. Set your microphone and speakers in Ubuntu **Settings > Sound**. The MACO needs an actual connected microphone and an audio output device; a display alone does not establish that either exists.

For a quick speaker check:

```bash
espeak-ng -v en+f3 -p 65 -s 155 'Hello, my loyal squire!'
```

## 5. Run BMO

```bash
python -m app.main
```

Or on future launches, from the repository:

```bash
bash scripts/start_bmo.sh
```

1. Type **Explain why the sky is blue in one sentence** and press Send. This exercises the LLM. `hello` still uses the existing built-in greeting.
2. Click **Talk**, wait for **Listening**, say a short sentence, and click **Finish**. Recording also ends automatically at 30 seconds.
3. BMO displays the recognised words, thinks, displays a reply and speaks it.
4. Click **Stop voice** to stop playback. Untick **Speak replies** to make future turns text-only.
5. Say or type **remember My favourite colour is Green**, then ask **what do you remember**. Case is preserved.
6. Close BMO and relaunch; the database remains in `data/bmo.db`.

Only one turn runs at a time. The microphone is closed before playback, and BMO does not listen continuously or activate on a wake word. Long model requests have a timeout. Closing the window requests microphone and playback shutdown; an in-flight model request or model download is not instantly cancelled, but runs in a daemon worker and does not keep the application open.

## Settings

Copy the example once, only if `config/config.json` does not already exist:

```bash
cp -n config/config.example.json config/config.json
```

Edit `config/config.json` in VS Code, then restart BMO. Personal config is ignored by Git. If you already had a personal config, merge the new `voice` settings and `llm.url` into it using the example.

- `llm.model`: starts at `qwen3.5:4b`. If too slow, download `qwen3.5:2b` and set that exact name here.
- `llm.timeout`: maximum wait for a model response, initially 120 seconds.
- `voice.input_device` / `voice.output_device`: `null` uses defaults. An integer from `--devices` or a unique device-name string selects a device. Device indexes can change after reconnecting hardware.
- `voice.pitch`: eSpeak pitch from 0 to 99; starts at 65.
- `voice.speed`: words per minute; starts at 155.
- `voice.espeak_voice`: starts at `en+f3`. Use `espeak-ng --voices` to inspect installed languages.
- `voice.max_record_seconds`: initially 30, capped at 60 by the recorder.
- `voice.whisper_model`: starts at `base.en`; changing it can require another download.

## Troubleshooting

- **`python` not found:** run `source .venv/bin/activate` first.
- **`No module named tkinter`:** install `python3-tk` for your Ubuntu Python.
- **Model unavailable:** run `ollama list`, then `ollama pull qwen3.5:4b`.
- **Cannot reach Ollama / timeout:** check the service, `ollama list`, and selected model. Try the smaller model if CPU inference is too slow.
- **No microphone:** select the actual input in Ubuntu Sound settings, check mute, then inspect `python -m app.voice --devices`.
- **Didn't catch speech:** try closer to the mic. Very quiet input and speech rejected by Whisper are ignored rather than sent to the LLM.
- **Speaker failure:** the written reply remains visible. Correct the output device and try again.
- **Patch doesn't apply:** share the exact error and `git status --short`; do not use a destructive reset.

## Validation and scope

27 automated tests exercise the HTTP request contract with a local fake Ollama server, case preservation, persistent memory, failed requests, silence, transcript filtering, turn ordering, overlap prevention, muted output, audio failure recovery, bounded capture, playback lifecycle and stopping. Audio hardware and model inference were simulated in tests. No microphone, speakers, running Qwen model or graphical display were available in the build environment, so actual voice quality, GUI appearance and MACO performance remain unverified.

Run the tests without calling a real model or writing your real database:

```bash
python -m unittest discover -s tests -v
```

This first version does not access email, inspect screens, execute commands or edit your projects. Those tools and their permissions are the next implementation stage.

## Implementation references

- [Ollama chat API](https://docs.ollama.com/api/chat)
- [Ollama Linux installation](https://docs.ollama.com/linux)
- [Qwen3.5 on Ollama](https://ollama.com/library/qwen3.5)
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
- [sounddevice](https://python-sounddevice.readthedocs.io/)
- [eSpeak NG](https://github.com/espeak-ng/espeak-ng)

# Fast local voice update

For the latest chat, expression and voice controls, see [the companion update](MAJOR_COMPANION_UPDATE.md).

This replaces Kokoro with **Pocket TTS 3.0.2**, using CPU-only PyTorch 2.10.0.
The application stays native Python/Tkinter. Qwen and Whisper remain local.
Python 3.13 and 3.14 are supported by this dependency set; no downgrade is required.

## Pull and run on the MACO

Close BMO, then run:

```bash
cd ~/BMO/BMO
git pull --ff-only
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
sudo apt install libportaudio2
python -m app.voice --download-voice
python -m app.voice --test-voice
python -m app.main
```

Keep your existing Qwen model. The first voice download needs internet and can take
several minutes; speech runs locally afterwards. No spoken text or microphone audio
is sent to a cloud speech API. Downloaded model files use Hugging Face's local cache.
The CPU wheel avoids installing several gigabytes of NVIDIA libraries on the MACO.
Kokoro can remain installed; this app no longer imports it. An old personal setting
of `backend: kokoro` automatically selects Pocket in memory, preserving your devices.
If pip reports a conflict with old, unrelated packages, a fresh `.venv-voice` using
`python3.13 -m venv .venv-voice` is an alternative; keep your old environment intact.

## What is faster

- System instructions use a compact character core with one relevant scene direction.
- Only the latest exchange is included, bounded to 1,800 characters. Saved memories
  are still stored and explicitly retrievable, but are not injected into every turn.
- Fast replies use a 4,096-token context, 160 output tokens for chat and 700 for focused
  explanations. Inputs over 6,000 characters use an 8,192-token context.
- Complete sentences enter speech synthesis while Qwen continues generating.
  Audio chunks play as the speech model produces them, with a bounded text queue.
- The speech model and voice state stay in memory between turns. Voice inference uses
  two CPU threads by default so it can run alongside Qwen.
- Qwen stays loaded for 30 minutes by default. The fresh-install microphone silence
  interval is 0.85 seconds; a saved personal interval still takes precedence.
- Text and audio failures are independent: a broken speaker does not discard the answer.

This does not promise a particular latency on the MACO. The first turn can still be
slower while models load. Large coding answers take longer, and stopping playback
may leave a short synthesis chunk draining before the next turn is accepted. The
UI stays responsive. Stop requests model cancellation; a blocked Ollama network read
can take until its timeout to return.

To change the tradeoff, edit `config/config.json`:

```json
{
  "llm": {
    "fast_replies": true,
    "history_messages": 2,
    "include_memories": false,
    "keep_alive": "30m"
  }
}
```

Use `history_messages: 0` for no routine chat history. Set `fast_replies: false` to
honour larger `num_ctx`, `chat_tokens` and `focus_tokens` settings. Preserve other
settings already in your personal file. Explicit "remember ..." and "what do you
remember" still work.

## Voice identity: listen before deciding

**The bundled voice is a starting voice, not a verified BMO clone.** No clean BMO
reference recording was available in the repository. The update implements a local
reference-voice path so a suitable recording can supply timbre, accent and delivery,
instead of trying to create BMO by raising an unrelated voice's pitch.

Audition these on BMO's actual speaker. Each command also saves the selection and
clears any custom reference. Settings contains the same choices.

```bash
python -m app.voice --voice azelma --test-voice
python -m app.voice --voice cosette --test-voice
python -m app.voice --voice eponine --test-voice
```

Alba and Fantine are also available. Azelma is the provisional default; a subjective
similarity ranking needs listening with your reference and actual speaker.
Neutral pace/pitch preserves the reference. Optional tuning is now available in Settings; no fake written accent is used.

For a closer voice, choose a clean **6–20 second 16-bit PCM WAV**, preferably 10–15
seconds, of one speaker delivering normal English dialogue. Avoid background music,
other characters, overlapping speech and long silences. Match the desired speaking
style: a shouted clip tends to produce a shouted voice. Reference quality matters.

Pocket's reference encoder requires access to the gated
[Kyutai model](https://huggingface.co/kyutai/pocket-tts). Review and accept its conditions
in your own account if applicable to your use, then authenticate locally:

```bash
hf auth login
python -m app.voice --reference /absolute/path/to/voice-reference.wav
python -m app.voice --test-voice
```

The command validates the WAV, processes it once and stores a small voice-state file
under ignored `models/pocket/voices/`. It selects the new voice only after preparation
succeeds. Neither recordings nor voice-state files are committed. Restart BMO after
changing the voice from the terminal. The bundled voices work without enabling the
reference encoder. If access is missing, BMO reports it instead of pretending to use
the reference. Similarity is not guaranteed by any short-reference model.

If conversion is needed (requires `sudo apt install ffmpeg`):

```bash
ffmpeg -i input.wav -t 15 -ac 1 -ar 24000 -c:a pcm_s16le voice-reference.wav
```

To return to the starting voice:

```bash
python -m app.voice --voice azelma
```

## Character and cadence

The compact prompt concentrates on BMO's earnest curiosity, small imaginary
occupations, sudden confidence, affection, independence and occasional vanity.
Sentences are short and speakable; punctuation supplies pauses. The model gets one
brief direct show reference, “Who wants to play video games?”, from *Rainy Day
Daydream*, as a cadence cue. The other examples are original dialogue, not show quotes.
It is instructed to vary its phrasing rather than repeat catchphrases.
[Clip reference](https://getyarn.io/yarn-clip/f92ec790-b31a-4628-b519-4f65bb907712)

Auto mode prioritises practical and sensitive needs; Focus explicitly suppresses jokes
and roleplay. Qwen can still miss nuance. Personality instructions shape wording;
a suitable voice reference shapes sound. Neither alone reproduces the full performance.

## Checks and measurements

```bash
python scripts/check_setup.py
python -m unittest discover -s tests -v
python -m app.voice --output /tmp/bmo-voice-test.wav
```

The WAV command uses the actual speech backend without requiring an audio device. It
prints model-load time separately from first-audio time, synthesis duration and audio
length. During conversation, controller metrics include `first_token_seconds`,
`first_audio_seconds`, prompt tokens and generation rate; Settings shows the last
first-text and first-sound timings. The audio metric starts
at turn submission and includes hearing when applicable.

Verification for the earlier voice update: the 57-test suite passed on CPython 3.13.14 and
3.14.6. The actual Pocket backend generated 24 kHz mono WAV files on both versions,
including a Python 3.14 run with `HF_HUB_OFFLINE=1`. On this build machine, warm first
chunks arrived in 0.14–0.17 seconds; about 7 seconds of audio took 2.8–4.9 seconds to
synthesise. These are voice-only measurements, not full Qwen-turn timings or MACO
benchmarks. Initial download/load took around 171 seconds; cached offline startup
was about 4.8 seconds. The reference encoder could not be tested without model access
and a suitable recording. Its validation, access-error and cached-state paths have
functional coverage.

Tests cover streaming before the final response, fence splits, cancellation, mute,
voice failure recovery, persistent voice-state reuse, legacy settings migration,
short context, history storage and the existing face/layout behaviour. Hardware
microphone/speaker quality, exact BMO similarity and MACO inference speed require
local listening and timing. See [interface controls](EXPRESSIVE_UPDATE.md).

## Sources

- [Pocket TTS installation, streaming and reference voices](https://github.com/kyutai-labs/pocket-tts)
- [Pocket TTS 3.0.2 package](https://pypi.org/project/pocket-tts/3.0.2/)
- [Bundled voice catalogue](https://huggingface.co/kyutai/tts-voices)
- [Ollama chat API](https://docs.ollama.com/api/chat)

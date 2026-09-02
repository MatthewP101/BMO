"""Download, audition and measure the same voice path used by the desktop app."""
import argparse
import json
import sys
import wave
from pathlib import Path
from threading import Event
from time import monotonic

from app.config import ROOT, load_config, save_preferences
from app.voice.speech_to_text import SpeechToText
from app.voice.text_to_speech import TextToSpeech

VOICES = ('azelma', 'cosette', 'eponine', 'alba', 'fantine')
TEST_TEXT = 'Oh, hello, Matthew. What are we doing today? I have a very small adventure in mind.'


def use_reference(path, settings, name="BMO reference"):
    """Export once; subsequent startups load the small cached voice state."""
    import hashlib
    import numpy as np
    from pocket_tts import export_model_state
    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise ValueError('Reference file does not exist.')
    if source.stat().st_size > 20_000_000:
        raise ValueError('Use a short WAV reference, under 20 MB.')
    try:
        with wave.open(str(source), 'rb') as wav:
            duration = wav.getnframes() / wav.getframerate()
            if wav.getsampwidth() != 2 or not 6 <= duration <= 20:
                raise ValueError('Use a clean 6–20 second, 16-bit PCM WAV with one speaker.')
            raw = wav.readframes(wav.getnframes())
            if len(raw) != wav.getnframes() * wav.getnchannels() * 2:
                raise ValueError('Reference WAV is incomplete.')
            samples = np.frombuffer(raw, dtype='<i2').astype(np.float32) / 32768
            if float(np.sqrt(np.mean(samples * samples))) < 0.003:
                raise ValueError('Reference WAV is silent or too quiet. Choose clear dialogue.')
    except wave.Error as exc:
        raise ValueError('Reference must be a 16-bit PCM WAV. See docs/FAST_VOICE.md for conversion.') from exc
    speaker = TextToSpeech(dict(settings, backend='pocket', reference_voice=str(source)))
    speaker.load()
    directory = ROOT / 'models/pocket/voices'
    directory.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()[:20]
    target = directory / f'english-3.0.2-{digest}.safetensors'
    temporary = target.with_suffix('.tmp.safetensors')
    try:
        export_model_state(speaker.voice_state, str(temporary))
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    profiles = dict(settings.get('profiles', {}))
    if settings.get('reference_voice'):
        profiles.setdefault('Original BMO',settings['reference_voice'])
    label = name.strip()[:60] or 'BMO reference'
    new_path = str(target.relative_to(ROOT))
    if label in profiles and profiles[label] != new_path:
        previous = label + ' (previous)'
        number = 2
        while previous in profiles:
            previous = f'{label} (previous {number})'
            number += 1
        profiles[previous] = profiles[label]
    profiles[label] = new_path
    changes = dict(backend='pocket', reference_voice=str(target.relative_to(ROOT)),profiles=profiles)
    save_preferences('voice', changes)
    settings.update(changes)
    print('Reference voice prepared and selected. Restart BMO to use it.')


def write_audio(speaker, text, output):
    import numpy as np
    started, first, count = monotonic(), None, 0
    # Opening the file before inference also catches unwritable paths early.
    with wave.open(str(output), 'wb') as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        for samples, rate in speaker.audio_chunks(text):
            if first is None:
                first = monotonic() - started
                wav.setframerate(rate)
            wav.writeframes((np.clip(samples, -1, 1) * 32767).astype('<i2').tobytes())
            count += len(samples)
    if not count:
        raise RuntimeError('Voice generated no audio.')
    return dict(first_audio_seconds=round(first, 3), synthesis_seconds=round(monotonic()-started, 3),
                audio_seconds=round(count/rate, 3))


def main():
    parser = argparse.ArgumentParser(description='BMO local voice setup and checks')
    parser.add_argument('--download-model', action='store_true', help='download the hearing model')
    parser.add_argument('--download-voice', action='store_true', help='download and load Pocket TTS')
    parser.add_argument('--devices', action='store_true')
    parser.add_argument('--test-voice', action='store_true')
    parser.add_argument('--voice', choices=VOICES, help='select and save a bundled voice; clears a custom reference')
    parser.add_argument('--reference', type=Path, help='prepare and select a clean 6–20 second PCM WAV')
    parser.add_argument('--name', default='BMO reference', help='name for a prepared reference in Settings')
    parser.add_argument('--pace', type=float, help='audition pace, 0.9 to 1.1 (not saved)')
    parser.add_argument('--pitch', type=float, help='audition pitch in semitones, -1.5 to 1.5 (not saved)')
    parser.add_argument('--clear-reference', action='store_true')
    parser.add_argument('--output', type=Path, help='save a voice test to WAV instead of playing it')
    parser.add_argument('--text', default=TEST_TEXT)
    args = parser.parse_args()
    settings = load_config()['voice']
    try:
        if args.voice or args.clear_reference:
            changes = dict(backend='pocket', reference_voice='',profiles=dict(settings.get('profiles',{})))
            if args.voice:
                changes['pocket_voice'] = args.voice
            save_preferences('voice', changes)
            settings.update(changes)
        if args.reference:
            use_reference(args.reference, settings, args.name)
        if args.pace is not None: settings['pace']=args.pace
        if args.pitch is not None: settings['pitch_shift']=args.pitch
        speaker = TextToSpeech(settings)
        if args.download_voice:
            print('Loading local voice (the first download can take a few minutes)...', flush=True)
            speaker.load()
            print('Local voice ready.')
        if args.download_model:
            SpeechToText(settings).load()
        if args.devices:
            import sounddevice
            print(sounddevice.query_devices())
        if args.test_voice or args.output:
            started = monotonic()
            speaker.load()
            print(f'Voice loaded in {monotonic()-started:.2f}s. Measuring warm synthesis.', flush=True)
            if args.output:
                print(json.dumps(write_audio(speaker, args.text, args.output), indent=2))
            else:
                speaker.speak(args.text, Event(), lambda: None, lambda: None)
        if not any((args.download_model, args.download_voice, args.devices, args.test_voice,
                    args.voice, args.reference, args.clear_reference, args.output)):
            parser.print_help()
    except (OSError, RuntimeError, ValueError) as exc:
        print(f'Voice setup: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

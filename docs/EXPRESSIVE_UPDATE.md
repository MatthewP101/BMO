# BMO face and conversation controls

For current installation, Python compatibility, voice selection and performance,
read [Fast local voice setup](FAST_VOICE.md). Kokoro and the earlier ZIP updater are
superseded; pull the current GitHub code instead.

The native Tkinter interface separates the animated face from the scrollable
conversation. Long output stays in the transcript and never expands over the face.
Portrait layouts put chat below the face; wide layouts put it alongside. Startup
fits the display, and resizing recomputes both panels.

| Control | Result |
| --- | --- |
| Talk / Ctrl+Space | Start recording; press again while Listening to finish |
| Stop / Ctrl+. | Stop capture, request model cancellation and stop speech |
| Enter / Shift+Enter | Send / insert a line break |
| Ctrl+L | Focus the message field |
| Face / Chat | Show the whole face / return to conversation |
| F11 | Toggle fullscreen |
| Escape | Stop an active turn; otherwise leave fullscreen or face-only mode |
| Copy | Copy selected text or the latest reply |
| Settings | Voice, speech mute, reduced motion, fullscreen and transcript export |

The face uses proportional eyes and mouth, eased expression changes, irregular blinks,
small eye movements and restrained body motion. Listening, thinking and speaking have
different states. Playback amplitude drives the mouth; pauses and stale audio close it.
This is amplitude-based animation, not phoneme lip sync. Six persistent canvas items
are updated rather than recreated. Animation throttles while idle or minimised.

Auto mode adapts tone, Focus keeps responses practical, and Play invites imagination.
Practical or distressed messages take precedence over Play, using language cues and
model instructions. This is a heuristic, not emotion detection.

Fenced code stays on screen. Speech reads a bounded prose portion and starts while
the answer is still generating. Muting stops playback without losing the text. A turn
stays busy until speech generation has drained, preventing overlapping voices.

The UI has automated geometry and state checks. Test portrait and landscape modes,
long code output, Stop during speech and the real microphone/speaker on the MACO.
File, email and desktop-control tools remain future work.

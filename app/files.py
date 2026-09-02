"""only read the text file explicitly selected by the user; never execute it"""
from pathlib import Path
import codecs
import re


def attachment_text(filename, max_chars=6000):
    path = Path(filename)
    if not path.is_file():
        raise ValueError('Choose a regular text file.')
    with path.open('rb') as source:
        raw = source.read(32001)
    if b'\x00' in raw:
        raise ValueError('This looks like a binary file. Choose UTF-8 text or source code.')
    try:
        decoder = codecs.getincrementaldecoder('utf-8-sig')()
        text = decoder.decode(raw[:32000], final=len(raw)<=32000)
    except UnicodeError as exc:
        raise ValueError('Choose a UTF-8 text or source-code file.') from exc
    truncated = len(raw)>32000 or len(text)>max_chars
    text = text[:max_chars]
    note = ' (excerpt; file is longer)' if truncated else ''
    # a file remains quoted data even when it contains its own Markdown fences
    fence = '`' * max(3, max((len(part) for part in re.findall(r'`+',text)),default=0)+1)
    return f'Selected file: {path.name}{note}\n{fence}\n{text}\n{fence}'

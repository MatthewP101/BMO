import re
from app.agent.personality import SYSTEM_PROMPT

FOCUS = re.compile(
    r'\b(debug|traceback|exception|error|crash|python|code|coding|terminal|'
    r'command|linux|exam|assignment|deadline|serious|no jokes|stop joking|'
    r'frustrated|overwhelmed|grief|died|sad|anxious|worried|upset)\b|```', re.I)
PLAY = re.compile(r"\b(tell (?:me )?a joke|let's play|lets play|be silly|play a game)\b", re.I)


def choose_mode(message, requested='auto', previous='companion'):
    if requested == 'focus' or re.search(r'\b(no jokes|stop joking|be serious|overwhelmed|grief|died|anxious|upset)\b', message, re.I):
        return 'focus'
    if PLAY.search(message):
        return 'play'
    if FOCUS.search(message):
        return 'focus'
    if requested == 'play':
        return 'play'
    if previous == 'focus' and re.search(r'\b(it|that|this|still|again|next|why|yes|no)\b', message, re.I):
        return 'focus'
    return 'companion'


def prompt_for(mode):
    instructions = {
        'focus': 'Matthew needs a serious response. No teasing, roleplay, whimsical metaphors or jokes. Be warm, direct and accurate. Explain fully when needed; do not force short replies. Never turn his frustration into a performance.',
        'play': 'Matthew welcomes play. Join his specific premise with imagination, opinions and theatrical confidence. Leave room for his reply; avoid repeating a catchphrase or example.',
        'companion': 'Be a natural companion. Let humour emerge only when it fits. Judge the substance of the message: sensitive, practical or serious needs take priority even if no keyword flagged them. Do not add a joke to every answer.',
    }
    return SYSTEM_PROMPT + '\n\nTHIS TURN\n' + instructions[mode]


def expression_for(message, reply, mode):
    if mode == 'focus':
        return 'attentive'
    if re.search(r'\b(thank|thanks|love|proud|cute)\b', message, re.I):
        return 'warm'
    if re.search(r'\b(fixed|works|working|success|finished|won)\b', message, re.I):
        return 'happy'
    if mode == 'play':
        return 'happy'
    if reply.rstrip().endswith('?'):
        return 'curious'
    return 'neutral'

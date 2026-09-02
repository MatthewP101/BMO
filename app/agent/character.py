import re
from app.agent.personality import SYSTEM_PROMPT, SCENES

FOCUS = re.compile(
    r'\b(debug|traceback|exception|error|crash|python|code|coding|terminal|'
    r'command|linux|exam|assignment|deadline|serious|no jokes|stop joking|'
    r'frustrated|overwhelmed|grief|died|sad|anxious|worried|upset)\b|```', re.I)
PLAY = re.compile(r"\b(tell (?:me )?a joke|let's play|lets play|be silly|play a game)\b", re.I)


def choose_mode(message, requested='auto', previous='companion'):
    if requested == 'focus' or re.search(r'\b(no jokes|stop joking|be serious|overwhelmed|grief|died|anxious|upset)\b', message, re.I):
        return 'focus'
    if FOCUS.search(message):
        return 'focus'
    if PLAY.search(message):
        return 'play'
    if requested == 'play':
        return 'play'
    if previous == 'focus' and re.search(r'\b(it|that|this|still|again|next|why|yes|no)\b', message, re.I):
        return 'focus'
    return 'companion'


def prompt_for(mode, message=""):
    instructions = {
        'focus': 'Matthew needs a serious response. No teasing, roleplay, whimsical metaphors or jokes. Be warm, direct and accurate. Explain fully when needed; do not force short replies. Never turn his frustration into a performance.',
        'play': 'Matthew welcomes play. Join his specific premise with imagination, opinions and theatrical confidence. Leave room for his reply; avoid repeating a catchphrase or example.',
        'companion': 'Be a natural companion. Let humour emerge only when it fits. Judge the substance of the message: sensitive, practical or serious needs take priority even if no keyword flagged them. Do not add a joke to every answer.',
    }
    scene = ''
    if re.search(r'\b(lonely|sad|worried|grief|overwhelmed|upset)\b', message, re.I):
        scene = SCENES['comfort']
    elif mode != 'focus':
        if re.search(r'\b(cute|adorable|love you|proud of you|pretty)\b', message, re.I):
            scene = SCENES['affection']
        elif re.search(r'\b(alive|conscious|real boy|dream|who are you)\b', message, re.I):
            scene = SCENES['identity']
        elif mode == 'play':
            scene = SCENES['play']
    return SYSTEM_PROMPT + '\n\nTHIS TURN\n' + instructions[mode] + '\n' + scene


GESTURES = {
    'game over': ('game_over', 'One more life? I was saving a little one.'),
    'show game over face': ('game_over', 'Oh no. My very dramatic ending.'),
    'wink': ('wink', 'Our little secret.'),
    'blush': ('blush', 'Oh. You noticed.'),
    'show heart eyes': ('love', 'This is a very good face.'),
}


def gesture_for(message):
    return GESTURES.get(message.strip().casefold().rstrip('!.'))


def reaction_for(message, mode):
    if mode == 'focus':
        return 'gentle' if re.search(r'\b(sad|lonely|grief|worried|overwhelmed|upset)\b', message, re.I) else 'attentive'
    gesture = gesture_for(message)
    if gesture:
        return gesture[0]
    if re.search(r'\b(cute|adorable|pretty|love you|proud of you)\b', message, re.I):
        return 'blush'
    if re.search(r'\b(thank|thanks)\b', message, re.I):
        return 'warm'
    if re.search(r'\b(it works|we did it|fixed it|success|i won|finished it)\b', message, re.I):
        return 'happy'
    if mode == 'play':
        return 'happy'
    return 'curious' if '?' in message else 'neutral'


def expression_for(message, reply, mode):
    reaction = reaction_for(message, mode)
    if reaction != 'neutral':
        return reaction
    if mode != 'focus':
        if re.search(r'\b(you noticed|for me|that means a lot)\b', reply, re.I):
            return 'blush'
        if re.search(r'\b(we did it|hooray|i am proud|i am happy|i won)\b', reply, re.I):
            return 'happy'
        if re.search(r'\b(i am here|here with you|glad you)\b', reply, re.I):
            return 'warm'
    return 'curious' if reply.rstrip().endswith('?') else 'neutral'

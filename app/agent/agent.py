from app.agent.character import choose_mode, expression_for, gesture_for
from app.llm.llm_client import LLMClient, TurnCancelled
from app.memory.history import get_recent_history, initialise_history, save_turn, get_chat
from app.memory.memory import get_memories, initialise_memory, save_memory
from app.tools.tool_registry import run_tool


class BMOAgent:
    def __init__(self, llm=None, chat_id="legacy"):
        initialise_memory()
        initialise_history()
        self.llm = llm if llm is not None else LLMClient()
        self.chat_id = chat_id if get_chat(chat_id) else 'legacy'
        self.last_mode = 'companion'
        self.last_expression = 'neutral'

    def set_chat(self, chat_id):
        if not get_chat(chat_id):
            raise ValueError('This chat no longer exists.')
        self.chat_id = chat_id
        self.last_mode = 'companion'
        self.last_expression = 'neutral'

    def start(self):
        print('BMO agent online.')

    def respond(self, message, mode='auto', on_token=None, cancel_event=None):
        chat_id = self.chat_id
        message = message.strip()
        if not message:
            raise ValueError('Please say or type a message.')
        if len(message) > 12000:
            raise ValueError('Please keep each message under 12,000 characters.')
        if cancel_event is not None and cancel_event.is_set():
            raise TurnCancelled()
        self.last_mode = choose_mode(message, mode, self.last_mode)
        self.llm.last_metrics = {}
        command = message.casefold().rstrip('?')
        gesture = gesture_for(message) if mode != 'focus' else None
        if gesture:
            self.last_mode = 'play'
            response = gesture[1]
        elif command in {'what time is it', 'current time', "what's the time"}:
            response = f"It is {run_tool('get_current_time')}."
        elif command.startswith('remember '):
            save_memory(message[len('remember '):].strip(), chat_id)
            response = "I've saved that."
        elif command == 'what do you remember':
            memories = get_memories(chat_id)
            response = 'I remember: ' + ', '.join(memories) if memories else 'Nothing saved yet. Tell me something to remember.'
        else:
            settings = getattr(self.llm, 'settings', {})
            settings = settings if isinstance(settings, dict) else {}
            history_count = min(16, max(0, int(settings.get('history_messages', 2))))
            history = get_recent_history(history_count, chat_id) if history_count else []
            memories = get_memories(chat_id) if settings.get('include_memories', False) else []
            response = self.llm.generate(message, history=history, memories=memories,
                                         mode=self.last_mode, on_token=on_token, cancel_event=cancel_event)
            if cancel_event is not None and cancel_event.is_set():
                raise TurnCancelled()
            self._remember_turn(message, response, chat_id)
            return response
        if on_token is not None:
            on_token(response)
        self._remember_turn(message, response, chat_id)
        return response

    def _remember_turn(self, message, response, chat_id):
        self.last_expression = expression_for(message, response, self.last_mode)
        save_turn(message, response, chat_id)

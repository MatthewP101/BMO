from app.agent.character import choose_mode, expression_for
from app.llm.llm_client import LLMClient, TurnCancelled
from app.memory.history import get_recent_history, initialise_history, save_message
from app.memory.memory import get_memories, initialise_memory, save_memory
from app.tools.tool_registry import run_tool


class BMOAgent:
    def __init__(self, llm=None):
        initialise_memory()
        initialise_history()
        self.llm = llm if llm is not None else LLMClient()
        self.last_mode = 'companion'
        self.last_expression = 'neutral'

    def start(self):
        print('BMO agent online.')

    def respond(self, message, mode='auto', on_token=None, cancel_event=None):
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
        if command in {'what time is it', 'current time', "what's the time"}:
            response = f"It is {run_tool('get_current_time')}."
        elif command.startswith('remember '):
            save_memory(message[len('remember '):].strip())
            response = "I've saved that."
        elif command == 'what do you remember':
            memories = get_memories()
            response = 'I remember: ' + ', '.join(memories) if memories else 'Nothing saved yet. Tell me something to remember.'
        else:
            response = self.llm.generate(message, history=get_recent_history(16), memories=get_memories(),
                                         mode=self.last_mode, on_token=on_token, cancel_event=cancel_event)
            if cancel_event is not None and cancel_event.is_set():
                raise TurnCancelled()
            self._remember_turn(message, response)
            return response
        if on_token is not None:
            on_token(response)
        self._remember_turn(message, response)
        return response

    def _remember_turn(self, message, response):
        self.last_expression = expression_for(message, response, self.last_mode)
        save_message('user', message)
        save_message('assistant', response)

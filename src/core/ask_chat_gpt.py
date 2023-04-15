import openai

from datetime import datetime

from typing import Tuple
from peewee import AutoField,CharField,IntegerField,DateTimeField


from core import log
from core.util import run_in_thread_pool
from core.database.plugin import PluginConfiguration

fields = {
    'id':  AutoField(),
    'exec_id': CharField(),
    'channel_id': CharField(null=True),
    'model_name': CharField(),
    'prompt_tokens': IntegerField(),
    'completion_tokens': IntegerField(),
    'total_tokens': IntegerField(),
    'exec_time': DateTimeField()
}


def create_new_model(name, fields, base_model,table_name):
    model_attrs = {k: v for k, v in fields.items()}
    model_attrs['Meta'] = type(
        'Meta', (), {'database': base_model._meta.database,'table_name':table_name})
    new_model = type(name, (base_model,), model_attrs)
    return new_model


AmiyaBotHsyhhssyyChatgptTokenConsumeModel = create_new_model(
    'AmiyaBotHsyhhssyyChatgptTokenConsume', fields, PluginConfiguration,'amiyabot-hsyhhssyy-chatgpt-token-consume')

class ChatGPTDelegate:
    def __init__(self) -> None:
        self.context_holder = {}
        self.user_lock = []
        self.bot = None
        
        AmiyaBotHsyhhssyyChatgptTokenConsumeModel.create_table(safe=True)

    def get_config(self, configName, channel_id=None):
        conf = self.bot.get_config(configName, channel_id)
        return conf

    async def ask_chatgpt_raw(self, prompt: list, channel_id: str = None) -> Tuple[bool, str]:

        self.bot.debug_log(f'ask_chatgpt_raw: {prompt}')

        openai.api_key = self.get_config('api_key', channel_id)

        proxy = self.get_config('proxy', channel_id)
        if proxy:
            self.bot.debug_log(f"proxy set: {proxy}")
            openai.proxy = proxy

        base_url = self.get_config('base_url', channel_id)
        if base_url:
            self.bot.debug_log(f"base_url set: {base_url}")
            openai.api_base = base_url

        response = None

        model = self.get_config('model', channel_id) or "gpt-3.5-turbo"

        try:
            response = await run_in_thread_pool(
                openai.ChatCompletion.create,
                **{'model': model, 'messages': prompt}
            )

        except openai.error.RateLimitError as e:
            self.bot.debug_log(f"RateLimitError: {e}")
            return False, "RateLimitError"
        except openai.error.InvalidRequestError as e:
            self.bot.debug_log(f"InvalidRequestError: {e}")
            return False, "InvalidRequestError"
        except Exception as e:
            self.bot.debug_log(f"Exception: {e}")
            return False, "UnknownError"

        text: str = response['choices'][0]['message']['content']
        role: str = response['choices'][0]['message']['role']

        id = response['id']
        usage = response['usage']

        AmiyaBotHsyhhssyyChatgptTokenConsumeModel.create(
            channel_id=channel_id, model_name=model, exec_id=id,
            prompt_tokens=int(usage['prompt_tokens']),
            completion_tokens=int(usage['completion_tokens']),
            total_tokens=int(usage['total_tokens']), exec_time=datetime.now())

        return True,f"{text}".strip()
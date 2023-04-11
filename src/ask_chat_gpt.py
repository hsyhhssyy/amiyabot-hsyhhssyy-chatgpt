import openai

from datetime import datetime

from typing import Optional, Tuple, Union
from peewee import AutoField,CharField,IntegerField,DateTimeField

from amiyabot import Message

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

    def get_context(self, context_id):
        if context_id in self.context_holder.keys():
            self.bot.debug_log(f'context get :\n{self.context_holder[context_id]}')
            return self.context_holder[context_id]
        else:
            self.bot.debug_log(f'context get : [Null]')
            return []

    def set_context(self, context_id, context_object):
        self.bot.debug_log(f'context set :\n{context_object}')
        self.context_holder[context_id] = context_object

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
            return False, "RateLimitError"
        except openai.error.InvalidRequestError as e:
            log.error(e)
            return False, "InvalidRequestError"
        except Exception as e:
            log.error(e)
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

    async def ask_amiya(self, prompt : Union[str, list],context_id : Optional[str] = None, channel_id :str = None, use_friendly_error:bool = True,
                     use_conext_prefix : bool = True, use_stop_words : bool = True) -> str :
        self.bot.debug_log(f'{prompt} {context_id} {use_friendly_error} {use_conext_prefix} {use_stop_words}')

        actual_context_id = f'AskAmiya-{context_id}'
        
        if actual_context_id in self.user_lock:
            return "博士，我还在想上一个问题...>.<"
        self.user_lock.append(actual_context_id)

        request_obj = []

        if context_id is not None:
            context = self.get_context(actual_context_id)
            # 尝试确定context
            if context is not None:
                request_obj = request_obj + context
            else:
                self.clear_context(actual_context_id)
                if use_conext_prefix:
                    predef_context = self.get_config('predef_context',channel_id)
                    if predef_context:
                        request_obj.extend([{"role": "system", "content": s} for s in predef_context])
        
        if isinstance(prompt,str):
            request_obj.append({"role":"user","content":prompt})
        
        if isinstance(prompt,list):
            for str_prompt in prompt:
                request_obj.append({"role":"user","content":str_prompt})

        self.bot.debug_log(f'{request_obj}')

        success,response = await self.ask_chatgpt_raw(request_obj,channel_id)
        
        self.user_lock.remove(f'AskAmiya-{context_id}')
        
        if success:
            if use_stop_words:
                stop_words = self.get_config('stop_words')
                if stop_words:
                    for sw in self.get_config('stop_words'):
                        if sw in response :
                            return "很抱歉博士，但是我不能回答您的这个问题。是否可以请博士换一个问题呢？"

            request_obj.append({"role":'assistant',"content":response})
            self.set_context(actual_context_id,request_obj)
            return f"{response}".strip()
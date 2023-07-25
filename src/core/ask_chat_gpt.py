import traceback
import openai
import time
import os

from datetime import datetime

from typing import Any, Dict, List, Tuple
from peewee import AutoField,CharField,IntegerField,DateTimeField


from core import log
from core.util import run_in_thread_pool
from core.database.plugin import PluginConfiguration

from ..util.string_operation import extract_json

curr_dir = os.path.dirname(__file__)


dir_path = f"{curr_dir}/../../../../resource/chatgpt"
dir_path = os.path.abspath(dir_path)
if not os.path.exists(dir_path):
    os.makedirs(dir_path)

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

    Model3 = "gpt-3.5-turbo"
    Model4 = "gpt-4"

    def get_config(self, configName, channel_id=None):
        conf = self.bot.get_config(configName, channel_id)
        return conf

    async def ask_chatgpt_raw(self, prompt: list, channel_id: str = None, model:str = None) -> Tuple[bool, str]:

        openai.api_key = self.get_config('api_key', channel_id)

        proxy = self.get_config('proxy', channel_id)
        if proxy:
            self.bot.debug_log(f"proxy set: {proxy}")
            openai.proxy = proxy

        if model is None:
            model = self.get_config('model', channel_id) or "gpt-3.5-turbo"

        base_url = self.get_config('base_url', channel_id)
        if base_url:
            openai.api_base = base_url

        response = None

        self.bot.debug_log(f"base_url: {base_url} proxy: {proxy} model: {model}")
        
        combined_message = ''.join(obj['content'] for obj in prompt)

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
        
        self.bot.debug_log(f'Chatgpt Raw: \n{combined_message}\n------------------------\n{text}')

         # 出于调试目的，写入请求数据
        formatted_file_timestamp = time.strftime('%Y%m%d', time.localtime(time.time()))
        sent_file = f'{dir_path}/{channel_id}.{formatted_file_timestamp}.txt'
        with open(sent_file, 'a', encoding='utf-8') as file:
            file.write('-'*20)
            formatted_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
            file.write(f'{formatted_timestamp}')
            file.write('-'*20)
            file.write('\n')
            all_contents = "\n".join([item["content"] for item in prompt])
            file.write(f'{all_contents}')
            file.write('\n')
            file.write('-'*20)
            file.write('\n')
            file.write(f'{text}')
            file.write('\n')

        id = response['id']
        usage = response['usage']

        if channel_id is None:
            channel_id = "-"

        if model is None:
            model = "-"

        AmiyaBotHsyhhssyyChatgptTokenConsumeModel.create(
            plugin_id="-",json_config="-",version="-",
            channel_id=channel_id, model_name=model, exec_id=id,
            prompt_tokens=int(usage['prompt_tokens']),
            completion_tokens=int(usage['completion_tokens']),
            total_tokens=int(usage['total_tokens']), exec_time=datetime.now())

        return True,f"{text}".strip()
    
    async def ask_chatgpt_with_json(self, command: str, channel_id: str = None,  model:str = None) -> List[Dict[str, Any]]:

        if model == "gpt-4":
            max_retries = 1
        else:
            max_retries = 3
        
        retry_count = 0 

        self.bot.debug_log(f'ChatGPT Max Retry: {max_retries}')

        json_objects = []

        try:
            successful_sent = False
            
            while retry_count < max_retries:
                success, response = await self.ask_chatgpt_raw([{"role": "user", "content": command}], channel_id ,model=model)
                if success:
                    json_objects = extract_json(response)    
                            
                    if len(json_objects) > 3:
                        # 有时候， API会发疯一样的返回N多行，这里检测到超过3句话就强制拦截不让他说了
                        # 尤其用3.5的时候更是这样
                        json_objects = json_objects[:3]

                    successful_sent = True

                if successful_sent:
                    break
                else:
                    self.bot.debug_log(f'未读到Json，重试第{retry_count+1}次')
                    retry_count += 1

            if not successful_sent:
                # 如果重试次数用完仍然没有成功，返回错误信息
                return False,[]

        except Exception as e:
            self.bot.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')
            return False,[]
        
        return True,json_objects
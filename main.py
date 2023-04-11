import os
import shutil
import openai
import json
import asyncio

from typing import Optional, Union
from types import SimpleNamespace

from amiyabot import Message, Chain
from amiyabot.factory.factoryTyping import MessageHandlerItem

from core.util import create_dir, read_yaml, run_in_thread_pool
from core.customPluginInstance import AmiyaBotPluginInstance
from core import log
from core import bot as main_bot

from .src.supress_other_plugin import suppress_other_plugin
from .src.ask_chat_gpt import ChatGPTDelegate
from .src.deep_cosplay import DeepCosplay

curr_dir = os.path.dirname(__file__)

class ChatGPTPluginInstance(AmiyaBotPluginInstance):
    def install(self):
        config_file = 'resource/plugins/chatGPT/config.yaml'
        if os.path.exists(config_file):
            # 清理旧的配置文件
            yamlConfig = read_yaml(config_file, _dict=True)
            if "api_key" in yamlConfig: self.set_config("api_key", yamlConfig["api_key"],None)
            if "predef_context" in yamlConfig: self.set_config("predef_context", yamlConfig["predef_context"],None)
            if "base_url" in yamlConfig: self.set_config("base_url", yamlConfig["base_url"],None)
            if "proxy" in yamlConfig: self.set_config("proxy", yamlConfig["proxy"],None)
            if "model" in yamlConfig: self.set_config("model", yamlConfig["model"],None)
            if "stop_words" in yamlConfig: self.set_config("stop_words", yamlConfig["stop_words"],None)
            os.remove(config_file)

    def load(self):
        loop = asyncio.get_event_loop()
        loop.create_task(suppress_other_plugin(self))

    def get_prefix(self):
        return self._prefix_keywords

    def debug_log(self, message):
        show_log = bot.get_config("show_log")
        if show_log == True:
            log.info(f'[ChatGPT]{message}')

    def ask_amiya( prompt : Union[str, list],context_id : Optional[str] = None, use_friendly_error:bool = True,
                     use_conext_prefix : bool = True, use_stop_words : bool = True) -> Optional[str] :
        ...

bot = ChatGPTPluginInstance(
    name='ChatGPT 智能回复',
    version='2.6',
    plugin_id='amiyabot-hsyhhssyy-chatgpt',
    plugin_type='',
    description='调用 OpenAI ChatGPT 智能回复普通对话',
    document=f'{curr_dir}/README.md',
    channel_config_default=f'{curr_dir}/accessories/config_channel.yaml',
    channel_config_schema=f'{curr_dir}/accessories/channel_config_schema.json', 
    global_config_default=f'{curr_dir}/accessories/config.yaml',
    global_config_schema=f'{curr_dir}/accessories/config_schema.json', 
)

delegate = ChatGPTDelegate()
delegate.bot = bot

async def check_talk(data: Message):
    if 'chat' in data.text.lower():
        return True, 10
    return True, 0

def format_request(text):

    # 首先移除先导关键词

    if text.startswith('兔兔chat'):
        text=text.replace('兔兔chat','',1)
        bot.debug_log(f'[ChatGPT]移除先导词 兔兔chat')
    elif text.startswith('兔兔CHAT'):
        text=text.replace('兔兔CHAT','',1)
        bot.debug_log(f'[ChatGPT]移除先导词 兔兔CHAT')    
    elif text.startswith('兔兔'):
        text=text.replace('兔兔','',1)
        bot.debug_log(f'[ChatGPT]移除先导词 兔兔')
    elif text.startswith('阿米娅'):
        text=text.replace('阿米娅','',1)
        bot.debug_log(f'[ChatGPT]移除先导词 阿米娅')
    elif text.startswith('Amiya'):
        text=text.replace('Amiya','',1)
        bot.debug_log(f'[ChatGPT]移除先导词 Amiya')
    elif text.startswith('amiya'):
        text=text.replace('amiya','',1)
        bot.debug_log(f'[ChatGPT]移除先导词 amiya')

    return text

def get_quote_id(data):
    message = data.message
    if 'messageChain' in message.keys():
        for msg in message['messageChain']:
            bot.debug_log(f'{msg}')
            if msg['type']=='Quote':
                sender = msg['senderId']
                bot.debug_log(f'{sender}')
                if f'{sender}' == f'{data.instance.appid}':
                    bot.debug_log('find quote')
                    return msg['id']
    
    return 0


async def ask_amiya( prompt : Union[str, list],context_id : Optional[str] = None, use_friendly_error:bool = True,
                     use_conext_prefix : bool = True, use_stop_words : bool = True) -> Optional[str] :
    return await delegate.ask_amiya(prompt,context_id,None,use_friendly_error,use_conext_prefix,use_stop_words)
    
bot.ask_amiya = ask_amiya
del ask_amiya

deep_cosplay_context = {}

@bot.on_message(verify=check_talk,check_prefix=False,allow_direct=True)
async def _(data: Message):
    if not data.text:
        return


    prefix = ['阿米娅', '阿米兔', '兔兔', '兔子', '小兔子', 'Amiya', 'amiya']

    cosplay = bot.get_config('deep_cosplay',data.channel_id)

    bot.debug_log(f'check_prefix=False --- {cosplay} {prefix}')

    force = False

    if data.is_at == True:
        force = True
    
    if data.text_original.startswith(tuple(prefix)):
        force = True

    if bot.get_config('deep_cosplay',data.channel_id) == True:
        try:
            context = deep_cosplay_context.get(data.channel_id)
            if context is None:
                context = DeepCosplay(delegate,data.channel_id)
                deep_cosplay_context[data.channel_id] = context
        except Exception as e:
            log.error(e)
            return

        await context.on_message(data,force)
    else:
        if force:
            request_text = format_request(data.text)
            context_id = f'{data.channel_id}-{data.user_id}'
            amiya_answer = await delegate.ask_amiya(request_text,context_id,data.channel_id,True,True,True)
            return Chain(data, reference=True).text(amiya_answer)
    
@bot.on_message(verify=check_talk,allow_direct=True)
async def _(data: Message):
    if not data.text:
        return

    bot.debug_log('check_prefix=True')

    if bot.get_config('deep_cosplay',data.channel_id) == True:
        bot.debug_log('deep_cosplay_enter')
        context = deep_cosplay_context.get(data.channel_id)
        if context is None:
            context = DeepCosplay(delegate,data.channel_id)
            deep_cosplay_context[data.channel_id] = context
        
        await context.on_message(data)
    else:
        request_text = format_request(data.text)
        context_id = f'{data.channel_id}-{data.user_id}'
        amiya_answer = await delegate.ask_amiya(request_text,context_id,data.channel_id,True,True,True)
        return Chain(data, reference=True).text(amiya_answer)
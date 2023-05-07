import os
import asyncio

from typing import Optional, Union

from amiyabot import Message,Chain

from core import log

from .src.supress_other_plugin import suppress_other_plugin
from .src.core.ask_chat_gpt import ChatGPTDelegate
from .src.deep_cosplay import DeepCosplay
from .src.ask_amiya import AskAmiya
from .src.core.chatgpt_plugin_instance import ChatGPTPluginInstance

curr_dir = os.path.dirname(__file__)

bot = ChatGPTPluginInstance(
    name='ChatGPT 智能回复',
    version='3.2.1',
    plugin_id='amiyabot-hsyhhssyy-chatgpt',
    plugin_type='',
    description='调用 OpenAI ChatGPT 智能回复普通对话',
    document=f'{curr_dir}/README.md',
    channel_config_default=f'{curr_dir}/accessories/channel_config_default.json',
    channel_config_schema=f'{curr_dir}/accessories/channel_config_schema.json', 
    global_config_default=f'{curr_dir}/accessories/global_config_default.json',
    global_config_schema=f'{curr_dir}/accessories/global_config_schema.json', 
)

delegate = ChatGPTDelegate()
delegate.bot = bot


def load():
    bot.debug_log(f"ChatGPT Plugin Change Other Handler1：{bot.get_config('override_other_plugin')}")
    loop = asyncio.get_event_loop()
    loop.create_task(suppress_other_plugin(bot))

async def ask_amiya(prompt : Union[str, list],context_id : Optional[str] = None, use_friendly_error:bool = True,
                     use_conext_prefix : bool = True, use_stop_words : bool = True) -> Optional[str] :
    temp_amiya = AskAmiya(bot,delegate,None)
    return await temp_amiya.ask_amiya(prompt,context_id,None,use_friendly_error,use_conext_prefix,use_stop_words)
    
bot.ask_amiya = ask_amiya
bot.load = load

del ask_amiya
del load

channel_hander_context = {}

def format_request(text):
    # 首先移除先导关键词
    for prefix_str in prefix:
        # 检查文本是否以prefix开头
        if text.startswith(prefix_str):
            text = text[len(prefix_str):]
            bot.debug_log(f'[ChatGPT]移除先导词 {prefix_str}')
            break
        # 检查文本是否以prefix + "chat"开头
        elif text.startswith(prefix_str + "chat"):
            text = text[len(prefix_str + "chat"):]
            bot.debug_log(f'[ChatGPT]移除先导词 {prefix_str + "chat"}')
            break

    return text

async def check_talk(data: Message):
    
    # 临时排除纯阿拉伯数字的消息，等待兔妈修复
    if data.text.isdigit():
        return False,0

    if 'chat' in data.text.lower():
        return True, 10
        
    if data.text.upper().startswith("CHATGPT请问"):
        return True, 10
    
    return True, -99999

prefix = ['阿米娅', '阿米兔', '兔兔', '兔子', '小兔子', 'Amiya', 'amiya']

@bot.on_message(verify=check_talk,check_prefix=False,allow_direct=True)
async def _(data: Message):
# @bot.message_before_handle
# async def _(data: Message, factory_name: str, instance):
    # bot.debug_log(f'[ChatGPT]factory_name{factory_name}')
    #if factory_name is not None:
    #    return True

    if not data.text:
        return

    bot.debug_log(f'[ChatGPT]on_message{data.text_original}')
    
    mode = bot.get_config('mode',data.channel_id)

    prefixed_call = False
    if data.is_at == True:
        prefixed_call = True
    if data.text_original.startswith(tuple(prefix)):
        prefixed_call = True

    request_text = format_request(data.text_original)

    if request_text.upper().startswith("CHATGPT请问"):
        success, raw_answer = await delegate.ask_chatgpt_raw([{"role": "user", "content":data.text}])
        if success:
            return Chain(data).text(raw_answer)
        else:
            return Chain(data).text(raw_answer)
    elif mode == "角色扮演" and data.channel_id is not None:
        try:
            context = channel_hander_context.get(data.channel_id)
            if context is None or not isinstance(context, DeepCosplay):
                context = DeepCosplay(bot,delegate,data.channel_id,data.instance)
                channel_hander_context[data.channel_id] = context
        except Exception as e:
            log.error(e)
            return

        await context.on_message(data,prefixed_call)
    else:
        if prefixed_call or data.channel_id is None:
            try:
                context = channel_hander_context.get(data.channel_id)
                if context is None or not isinstance(context, AskAmiya):
                    context = AskAmiya(bot,delegate,data.channel_id)
                    channel_hander_context[data.channel_id] = context
            except Exception as e:
                log.error(e)
                return

            await context.on_message(data,request_text,prefixed_call)

    return
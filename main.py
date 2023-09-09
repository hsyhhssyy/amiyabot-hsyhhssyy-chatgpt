import os
import asyncio
import traceback

from typing import Optional, Union

from amiyabot import Message,Chain

from core import log

from .src.supress_other_plugin import suppress_other_plugin
from .src.core.ask_chat_gpt import ChatGPTDelegate
from .src.core.chatgpt_plugin_instance import ChatGPTPluginInstance
from .src.deep_cosplay import DeepCosplay
from .src.trpg import TRPGMode
from .src.online_troll import OnlineTrollMode
from .src.ask_amiya import AskAmiya
from .src.util.complex_math import frequency_controller

curr_dir = os.path.dirname(__file__)

bot = ChatGPTPluginInstance(
    name='ChatGPT 智能回复',
    version='3.4.5',
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

async def check_talk(data: Message):
        
    enabled = bot.get_config('enable_in_this_channel',data.channel_id)
    bot.debug_log(f'[{data.channel_id:<10}]在本频道启用: {enabled}')
    if enabled != True:
        return False, 0

    # 临时排除纯阿拉伯数字的消息，等待兔妈修复
    # 已修复，但是就先不移除了，以防万一
    if data.text.isdigit():
        return False,0

    # 黑名单

    black_list = bot.get_config('black_list',data.channel_id)
    if black_list:
        if str(data.user_id) in black_list:
            bot.debug_log(f'[{data.channel_id:<10}]用户被黑名单屏蔽: {data.user_id}')
            return False,0

    if 'chat' in data.text.lower():
        return True, 10
        
    if data.text.upper().startswith("CHATGPT请问"):
        if next(frequency_controller):
            return True, 10
    
    return True, -99999

@bot.on_message(verify=check_talk,check_prefix=False,allow_direct=True)
async def _(data: Message):

    # bot.debug_log(f"触发进入ChatGPT插件 {not data.text}")

    if not data.text:
        return
    
    try:
        mode = bot.get_config('mode',data.channel_id)
    except Exception as e:
            bot.debug_log(
                f'Unknown Error {e} \n {traceback.format_exc()}')

    bot.debug_log(f'[{data.channel_id:<10}] 模式:{mode} 消息:{data.text_original}')

    if data.text_original.upper().startswith("CHATGPT请问"):
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

        await context.on_message(data)
    elif mode == "典孝急模式" and data.channel_id is not None:
        try:
            context = channel_hander_context.get(data.channel_id)
            if context is None or not isinstance(context, OnlineTrollMode):
                context = OnlineTrollMode(bot,delegate,data.channel_id,data.instance)
                channel_hander_context[data.channel_id] = context
        except Exception as e:
            log.error(e)
            return

        await context.on_message(data)
    elif mode == "跑团模式" and data.channel_id is not None:
        try:
            context = channel_hander_context.get(data.channel_id)
            if context is None or not isinstance(context, TRPGMode):
                context = TRPGMode(bot,delegate,data.channel_id,data.instance)
                channel_hander_context[data.channel_id] = context
        except Exception as e:
            log.error(e)
            return

        await context.on_message(data)
    else:
        channel = data.channel_id
        if channel is None:
            channel = f'User:{data.user_id}'
        try:
            context = channel_hander_context.get(channel)
            if context is None or not isinstance(context, AskAmiya):
                context = AskAmiya(bot,delegate,channel)
                channel_hander_context[channel] = context
        except Exception as e:
            log.error(e)
            return
        
        await context.on_message(data)

    return
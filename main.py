import os
import asyncio
import traceback

from typing import Optional, Union

from amiyabot import Message,Chain

from core import log,Requirement
from core import bot as main_bot

from .src.supress_other_plugin import suppress_other_plugin

from .src.core.trpg_storage import AmiyaBotChatGPTParamHistory,AmiyaBotChatGPTTRPGSpeechLog,AmiyaBotChatGPTExecutionLog
from .src.core.chatgpt_plugin_instance import ChatGPTPluginInstance
from .src.core.developer_types import BLMAdapter

from .src.deep_cosplay import DeepCosplay
from .src.trpg import TRPGMode
from .src.online_troll import OnlineTrollMode
from .src.ask_amiya import AskAmiya

from .src.server.trpg_server import TRPGAPI # 导入Server类从而启动服务器

from .src.util.complex_math import frequency_controller

curr_dir = os.path.dirname(__file__)

bot : ChatGPTPluginInstance = None

def dynamic_get_global_config_schema_data():
    if bot:
        return bot.generate_global_schema()
    else:
        return f'{curr_dir}/global_config_default.json'
    
def dynamic_get_channel_config_schema_data():
    if bot:
        return bot.generate_channel_schema()
    else:
        return f'{curr_dir}/global_config_default.json'

bot = ChatGPTPluginInstance(
    name='ChatGPT 智能回复',
    version='4.1.0',
    plugin_id='amiyabot-hsyhhssyy-chatgpt',
    plugin_type='',
    description='调用 OpenAI ChatGPT 智能回复普通对话',
    document=f'{curr_dir}/README.md',
    requirements=[
        Requirement("amiyabot-blm-library")
    ],
    channel_config_default=f'{curr_dir}/accessories/channel_config_default.json',
    channel_config_schema=dynamic_get_channel_config_schema_data, 
    global_config_default=f'{curr_dir}/accessories/global_config_default.json',
    global_config_schema=dynamic_get_global_config_schema_data, 
)

def load():

    AmiyaBotChatGPTParamHistory.create_table(safe=True)
    AmiyaBotChatGPTTRPGSpeechLog.create_table(safe=True)
    AmiyaBotChatGPTExecutionLog.create_table(safe=True)

    bot.debug_log(f"ChatGPT Plugin Override other plugins：{bot.get_config('override_other_plugin')}")
    loop = asyncio.get_event_loop()
    loop.create_task(suppress_other_plugin(bot))

bot.load = load

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

    blm_lib : BLMAdapter = main_bot.plugins['amiyabot-blm-library']
                    
    if blm_lib is None:
        bot.debug_log("未加载blm库，无法使用ChatGPT")
        return

    # bot.debug_log(f"触发进入ChatGPT插件 {not data.text}")

    if not data.text and not data.image:
        return
    
    try:
        mode = bot.get_config('mode',data.channel_id)
    except Exception as e:
            bot.debug_log(
                f'Unknown Error {e} \n {traceback.format_exc()}')

    if data.text_original.upper().startswith("CHATGPT请问") or data.text_original.upper().startswith("文心一言请问"):
        mode = "请问模式"

    bot.debug_log(f'[{data.channel_id:<10}] 模式:{mode} 消息:{data.text_original}')

    if mode == "请问模式":
        model = bot.get_model_in_config('high_cost_model_name',data.channel_id)
        content_to_send =[{ "type": "text", "text": data.text }]
        vision = bot.get_config('vision_enabled',data.channel_id)
        if vision == True:
            if data.image and len(data.image) > 0:                
                content_to_send = content_to_send +  [{"type":"image_url","url":imgPath} for imgPath in data.image]
                bot.debug_log(content_to_send)
                model = bot.get_model_in_config('vision_model_name',data.channel_id)

        raw_answer = await blm_lib.chat_flow(
            prompt=content_to_send,
            channel_id = data.channel_id,
            model=model
        )
        return Chain(data).text(raw_answer)
    elif mode == "角色扮演" and data.channel_id is not None:
        try:
            context = channel_hander_context.get(data.channel_id)
            if context is None or not isinstance(context, DeepCosplay):
                context = DeepCosplay(bot,blm_lib,data.channel_id,data.instance)
                channel_hander_context[data.channel_id] = context
        except Exception as e:
            log.error(e)
            return

        await context.on_message(data)
    elif mode == "典孝急模式" and data.channel_id is not None:
        try:
            context = channel_hander_context.get(data.channel_id)
            if context is None or not isinstance(context, OnlineTrollMode):
                context = OnlineTrollMode(bot,blm_lib,data.channel_id,data.instance)
                channel_hander_context[data.channel_id] = context
        except Exception as e:
            log.error(e)
            return

        await context.on_message(data)
    elif mode == "跑团模式" and data.channel_id is not None:
        try:
            context = channel_hander_context.get(data.channel_id)
            if context is None or not isinstance(context, TRPGMode):
                context = TRPGMode(bot,blm_lib,data.channel_id,data.instance)
                channel_hander_context[data.channel_id] = context
        except Exception as e:
            log.error(e)
            return

        await context.on_message(data)
    else:
        # 经典模式
        channel = data.channel_id
        if channel is None:
            channel = f'User:{data.user_id}'
        try:
            context = channel_hander_context.get(channel)
            if context is None or not isinstance(context, AskAmiya):
                context = AskAmiya(bot,blm_lib,channel)
                channel_hander_context[channel] = context
        except Exception as e:
            log.error(e)
            return
        
        await context.on_message(data)

    return
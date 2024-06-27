from typing import Optional, Union

from amiyabot import Message, Chain

from .core.chatgpt_plugin_instance import ChatGPTPluginInstance, ChatGPTMessageHandler
from .core.message_context import format_request, prefix

# 两个问题，context  和 私聊

class AskAmiya(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, blm_lib, channel_id) -> None:
        super().__init__(bot, blm_lib, channel_id, "normal_mode_config")
        self.context_map = {} # context_id -> context_array
        self.user_lock = []

    async def on_message(self, data: Message):
        prefixed_call = False
        if data.is_at == True:
            prefixed_call = True
        if data.text_original.startswith(tuple(prefix)):
            prefixed_call = True

        if prefixed_call or data.channel_id is None:

            context_id = f'{data.channel_id}-{data.user_id}'
            
            if context_id in self.user_lock:
                await data.send(Chain(data).text("博士，我还在想上一个问题...>.<"))
                return 
            
            self.user_lock.append(context_id)

            try:

                request_text = format_request(data.text_original)

                if self.get_handler_config("amiya_thinking", True) == True:
                    await data.send(Chain(data).text('阿米娅思考中'))

                channel_id = data.channel_id
                if channel_id is None:
                    channel_id = f"User:{data.user_id}"

                model = self.bot.get_model_in_config('high_cost_model_name', channel_id)
                model_obj = self.blm_lib.get_model(model)

                if model_obj is None:
                    await data.send(Chain(data, reference=True).text("很抱歉博士，但是我现在暂时无法回答您的问题。"))
                    return
                
                if context_id not in self.context_map.keys():
                    context = []
                else:
                    context = self.context_map[context_id]
                
                predef_context_conf = "\n".join(self.get_handler_config('predef_context', []))
                if len(predef_context_conf) > 0:
                    predef_context = [
                        {"type":"text","text":predef_context_conf+"\n接下来是对话：\n\n"},
                    ]
                else:
                    predef_context = []
                
                content_to_send = []

                if len(context) > 0:
                    # 只保留最近20个
                    content_to_send = content_to_send + context[-10:]
                
                vision = self.bot.get_config('vision_enabled',channel_id)
                if vision == True:
                    if data.image and len(data.image) > 0:                
                        content_to_send = content_to_send +  [{"type":"image_url","url":imgPath} for imgPath in data.image]
                        self.bot.debug_log(content_to_send)
                        model = self.bot.get_model_in_config('vision_model_name',data.channel_id)

                content_to_send = predef_context + content_to_send + [{"type":"text","text":"博士："+request_text}]

                amiya_answer = await self.blm_lib.chat_flow(prompt=content_to_send,
                                                    model=model,
                                                    channel_id=channel_id)

                if amiya_answer:
                    stop_words = self.get_handler_config('stop_words')
                    if stop_words:
                        for sw in self.get_handler_config('stop_words'):
                            if sw in amiya_answer:
                                amiya_answer = "很抱歉博士，但是我不能回答您的这个问题。是否可以请博士换一个问题呢？"

                    amiya_answer = f"{amiya_answer}".strip()
                    # 剔除开头的阿米娅:
                    if amiya_answer.startswith("阿米娅：") or amiya_answer.startswith("阿米娅:"):
                        amiya_answer = amiya_answer[4:]
                else:
                    await data.send(Chain(data, reference=True).text("很抱歉博士，但是我现在暂时无法回答您的问题。"))
                    return

                context = context + [
                    {"type":"text","text":"博士："+request_text},
                    {"type":"text","text":"阿米娅："+amiya_answer}
                    ]

                self.context_map[context_id] = context

            finally:
                self.user_lock.remove(context_id)

            if amiya_answer:
                await data.send(Chain(data, reference=True).text(amiya_answer))
            else:
                await data.send(Chain(data, reference=True).text("很抱歉博士，但是我现在暂时无法回答您的问题。"))

        return

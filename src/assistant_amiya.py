from typing import Optional, Union

from amiyabot import Message, Chain

from .core.chatgpt_plugin_instance import ChatGPTPluginInstance, ChatGPTMessageHandler
from .core.message_context import format_request, prefix

# 两个问题，context  和 私聊

class AssistantAmiya(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, blm_lib, channel_id) -> None:
        super().__init__(bot, blm_lib, channel_id, "assistant_mode_config")
        self.context_map = {}

    async def on_message(self, data: Message):
        prefixed_call = False
        if data.is_at == True:
            prefixed_call = True
        if data.text_original.startswith(tuple(prefix)):
            prefixed_call = True

        if prefixed_call or data.channel_id is None:

            context_id = f'{data.channel_id}-{data.user_id}'
            
            try:
                request_text = format_request(data.text_original)

                channel_id = data.channel_id
                if channel_id is None:
                    channel_id = f"User:{data.user_id}"
                                
                assistant_id = self.bot.get_config('assistant_id',channel_id)

                if not assistant_id:
                    self.debug_log(f"Assistant ID not found! channel_id: {channel_id}")
                    await data.send(Chain(data, reference=True).text("很抱歉博士，但是我现在暂时无法回答您的问题。"))
                    return

                # 处理一下assistant_id, 配置文件里 是 name[id] 的形式
                assistant_id = assistant_id.split("[")[1].split("]")[0]
                
                assistant = self.blm_lib.get_assistant(assistant_id)

                if not assistant:
                    self.debug_log(f"Assistant not found! assistant_id: {assistant_id}, channel_id: {channel_id}")
                    await data.send(Chain(data, reference=True).text("很抱歉博士，但是我现在暂时无法回答您的问题。"))
                    return
                
                context_id = f'AssistantAmiya-{channel_id}'

                if context_id not in self.context_map.keys():
                    self.context_map[context_id] = await self.blm_lib.assistant_thread_create(
                        assistant_id=assistant_id,
                    )

                thread_id = self.context_map[context_id]

                if not await self.blm_lib.assistant_thread_touch(
                    thread_id=thread_id,
                    assistant_id=assistant_id
                ):
                    self.debug_log(f"Thread timeout! hread_id: {thread_id}, channel_id: {channel_id}")
                    self.context_map[context_id] = await self.blm_lib.assistant_thread_create(
                        assistant_id=assistant_id,
                    )
                    thread_id = self.context_map[context_id]

                content_to_send = [{"type":"text","role":"user","text":request_text}]

                self.debug_log(f"assistant_id: {assistant_id}, thread_id: {thread_id}, channel_id: {channel_id}")

                if len(data.image)>0:
                    if assistant["vision"]:
                        content_to_send.append({"type":"image_url","role":"user","url":data.image[0]})

                amiya_answer = await self.blm_lib.assistant_run(
                    assistant_id=assistant_id,
                    thread_id=thread_id,
                    messages=content_to_send,
                    channel_id=channel_id
                )

                if amiya_answer:                   
                    amiya_answer = f"{amiya_answer}".strip()
                    # 剔除开头的阿米娅:
                    if amiya_answer.startswith("阿米娅：") or amiya_answer.startswith("阿米娅:"):
                        amiya_answer = amiya_answer[4:]
                else:
                    await data.send(Chain(data, reference=True).text("很抱歉博士，但是我现在暂时无法回答您的问题。"))
                    return

            finally:
                ...

            if amiya_answer:
                await data.send(Chain(data, reference=True).text(amiya_answer))
            else:
                await data.send(Chain(data, reference=True).text("很抱歉博士，但是我现在暂时无法回答您的问题。"))

        return

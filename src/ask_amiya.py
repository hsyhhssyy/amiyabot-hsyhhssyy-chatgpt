from typing import Optional, Union

from amiyabot import Message, Chain

from .core.chatgpt_plugin_instance import ChatGPTPluginInstance, ChatGPTMessageHandler
from .core.message_context import format_request, prefix


class AskAmiya(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, blm_lib, channel_id) -> None:
        super().__init__(bot, blm_lib, channel_id, "normal_mode_config")
        self.context_holder = []
        self.user_lock = []

    def clear_context(self, context_id):
        actual_context_id = f'AskAmiya-{context_id}'
        if actual_context_id in self.context_holder:
            self.context_holder.remove(actual_context_id)
    
    def has_context(self, context_id):
        actual_context_id = f'AskAmiya-{context_id}'
        return actual_context_id in self.context_holder
    
    def add_context(self, context_id):
        actual_context_id = f'AskAmiya-{context_id}'
        if actual_context_id not in self.context_holder:
            self.context_holder.append(actual_context_id)
    

    async def ask_amiya(self, prompt: Union[str, list], context_id: Optional[str] = None, channel_id: str = None, model: str = None) -> str:
        self.bot.debug_log(
            f'{prompt} {context_id}')

        actual_context_id = f'AskAmiya-{context_id}'

        if actual_context_id in self.user_lock:
            return "博士，我还在想上一个问题...>.<"
        self.user_lock.append(actual_context_id)


        response = await self.blm_lib.chat_flow(prompt=prompt,
                                                model=model,
                                                channel_id=channel_id,
                                                context_id=actual_context_id)

        self.user_lock.remove(f'AskAmiya-{context_id}')

        if response:
            stop_words = self.get_handler_config('stop_words')
            if stop_words:
                for sw in self.get_handler_config('stop_words'):
                    if sw in response:
                        return "很抱歉博士，但是我不能回答您的这个问题。是否可以请博士换一个问题呢？"

            return f"{response}".strip()

        return "很抱歉博士，但是我现在暂时无法回答您的问题。"

    async def on_message(self, data: Message):
        prefixed_call = False
        if data.is_at == True:
            prefixed_call = True
        if data.text_original.startswith(tuple(prefix)):
            prefixed_call = True

        if prefixed_call or data.channel_id is None:

            request_text = format_request(data.text_original)

            context_id = f'{data.channel_id}-{data.user_id}'
            if self.bot.get_quote_id(data) == 0:
                self.clear_context(context_id)
          
            if self.get_handler_config("amiya_thinking", True) == True:
                await data.send(Chain(data).text('阿米娅思考中'))

            channel_id = data.channel_id
            if channel_id is None:
                channel_id = f"User:{data.user_id}"

            predef_context = ""

            if not self.has_context(context_id):
                predef_context = "\n".join(self.get_handler_config('predef_context', []))

            content_to_send = [{"type":"text","text":predef_context+"\n"+request_text}]
            
            model = self.bot.get_model_in_config('high_cost_model_name', channel_id)
            vision = self.bot.get_config('vision_enabled',channel_id)
            if vision == True:
                if data.image and len(data.image) > 0:                
                    content_to_send = content_to_send +  [{"type":"image_url","url":imgPath} for imgPath in data.image]
                    self.bot.debug_log(content_to_send)
                    model = self.bot.get_model_in_config('vision_model_name',data.channel_id)

            amiya_answer = await self.ask_amiya(content_to_send, context_id, channel_id, model)

            if amiya_answer:
                self.add_context(context_id)
                await data.send(Chain(data, reference=True).text(amiya_answer))
            else:
                await data.send(Chain(data, reference=True).text("很抱歉博士，但是我现在暂时无法回答您的问题。"))

        return

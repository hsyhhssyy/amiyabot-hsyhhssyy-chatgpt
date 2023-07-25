from typing import Optional, Union

from amiyabot import Message,Chain

from .core.ask_chat_gpt import ChatGPTDelegate
from .core.chatgpt_plugin_instance import ChatGPTPluginInstance,ChatGPTMessageHandler
from .core.message_context import format_request,prefix

class AskAmiya(ChatGPTMessageHandler):
    def __init__(self, bot:ChatGPTPluginInstance,delegate:ChatGPTDelegate, channel_id) -> None:
        super().__init__(bot,delegate,channel_id,"normal_mode_config")
        self.context_holder = {}
        self.user_lock = []
    

    def __get_context(self, context_id):
        if context_id in self.context_holder.keys():
            self.bot.debug_log(f'context get : {self.context_holder[context_id]}')
            return self.context_holder[context_id]
        else:
            self.bot.debug_log(f'context get : [None]')
            return []

    def __set_context(self, context_id, context_object):
        self.bot.debug_log(f'context set : {context_object}')
        self.context_holder[context_id] = context_object

    def clear_context(self, context_id):
        actual_context_id = f'AskAmiya-{context_id}'
        if actual_context_id in self.context_holder:
            self.context_holder.pop(actual_context_id)

    async def ask_amiya(self, prompt : Union[str, list],context_id : Optional[str] = None, channel_id :str = None, use_friendly_error:bool = True,
                     use_conext_prefix : bool = True, use_stop_words : bool = True) -> str :
        self.bot.debug_log(f'{prompt} {context_id} {use_friendly_error} {use_conext_prefix} {use_stop_words}')

        actual_context_id = f'AskAmiya-{context_id}'
        
        if actual_context_id in self.user_lock:
            return "博士，我还在想上一个问题...>.<"
        self.user_lock.append(actual_context_id)
        
        request_obj = []

        if context_id is not None:
            context = self.__get_context(actual_context_id)
            # 尝试确定context
            if context is not None and context != []:
                request_obj = request_obj + context
            else:
                context = self.__set_context(actual_context_id,[])
                if use_conext_prefix:
                    predef_context = self.get_handler_config('predef_context')
                    if predef_context:
                        request_obj.extend([{"role": "system", "content": s} for s in predef_context])
        
        if isinstance(prompt,str):
            request_obj.append({"role":"user","content":prompt})
        
        if isinstance(prompt,list):
            for str_prompt in prompt:
                request_obj.append({"role":"user","content":str_prompt})

        self.bot.debug_log(f'{request_obj}')

        success,response = await self.delegate.ask_chatgpt_raw(request_obj,channel_id)
        
        self.user_lock.remove(f'AskAmiya-{context_id}')
        
        if success:
            if use_stop_words:
                stop_words = self.get_handler_config('stop_words')
                if stop_words:
                    for sw in self.get_handler_config('stop_words'):
                        if sw in response :
                            return "很抱歉博士，但是我不能回答您的这个问题。是否可以请博士换一个问题呢？"

            request_obj.append({"role":'assistant',"content":response})
            self.__set_context(actual_context_id,request_obj)
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
            
            if self.get_handler_config("amiya_thinking",True) == True:
                await data.send(Chain(data).text('阿米娅思考中'))

            channel_id = data.channel_id
            if channel_id is None:
                channel_id = f"User:{data.user_id}"

            amiya_answer = await self.ask_amiya(request_text,context_id,channel_id,True,True,True)
            await data.send(Chain(data, reference=True).text(amiya_answer))
        
        return
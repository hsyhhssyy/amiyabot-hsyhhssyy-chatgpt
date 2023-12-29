import json
import time
import os
import traceback

from amiyabot import Message,Chain

from .core.developer_types import BLMAdapter
from .core.chatgpt_plugin_instance import ChatGPTPluginInstance, ChatGPTMessageHandler
from .core.message_context import ChatGPTMessageContext
from .core.chat_log_storage import ChatLogStorage

curr_dir = os.path.dirname(__file__)
chat_log_storages = {}

class OnlineTrollMode(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, blm_lib: BLMAdapter, channel_id: int, instance) -> None:
        super().__init__(bot, blm_lib, channel_id, "trpg_mode_config", instance)

        self.storage = ChatLogStorage(bot, blm_lib, self.channel_id, False)
        self.last_process_time = time.time()
        chat_log_storages[channel_id] = self.storage

    async def on_message(self, data: Message):

        try:
            
            if data.text == "":
                return


            self.storage.enqueue(data)

            if len(self.storage.recent_messages) < 2:
                return
            
            if self.storage.recent_messages[-1].user_id == self.storage.recent_messages[-2].user_id:
                # 触发
                with open(f'{curr_dir}/../templates/online-troll/online-troll.v1.txt', 'r', encoding='utf-8') as file:
                    command = file.read()
                
                user_messages = [msg for msg in reversed(self.storage.recent_messages) if msg.user_id == self.storage.recent_messages[-1].user_id]

                last_word = ""

                for i in range(1, len(user_messages) + 1):
                    context = user_messages[-i]
                    text_to_append = f'{context.text}'
                    last_word = last_word + "\n" + text_to_append

                command = command.replace("<<LASTWORD>>",last_word)

                model_name = self.bot.get_model_in_config('low_cost_model_name',self.channel_id)

                json_str =  await self.blm_lib.chat_flow(
                    command,model=model_name,
                    channel_id= self.channel_id,
                    json_mode=True)
                
                if json_str == None:
                    return

                json_objects = json.loads(json_str)
                
                if isinstance(json_object,list):
                    if len(json_objects) < 1:
                        return                
                    json_object = json_objects[0]
                    
                word = json_object.get('OptionText', None)

                if word == None:
                    return
                
                await self.instance.send_message(Chain().at(user=data.user_id).text(f'{word}'), channel_id=self.channel_id)

        except Exception as e:
            self.debug_log(
                f'Unknown Error {e} \n {traceback.format_exc()}')

        return
    
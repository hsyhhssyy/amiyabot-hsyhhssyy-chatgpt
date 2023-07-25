import time
import os
import traceback

from amiyabot import Message,Chain

from .core.ask_chat_gpt import ChatGPTDelegate
from .core.chatgpt_plugin_instance import ChatGPTPluginInstance, ChatGPTMessageHandler
from .core.message_context import ChatGPTMessageContext
from .core.chat_log_storage import ChatLogStorage

curr_dir = os.path.dirname(__file__)
chat_log_storages = {}

class OnlineTrollMode(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, delegate: ChatGPTDelegate, channel_id: int, instance) -> None:
        super().__init__(bot, delegate, channel_id, "trpg_mode_config", instance)

        self.storage = ChatLogStorage(bot, delegate, self.channel_id, False)
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

                success, json_objects = await self.delegate.ask_chatgpt_with_json(command, self.channel_id, ChatGPTDelegate.Model3)
                if not success or len(json_objects) < 1:
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
    
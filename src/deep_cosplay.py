import time
import random
import asyncio
import os
import re

from typing import List, Tuple

from amiyabot import Message, Chain
from .core.ask_chat_gpt import ChatGPTDelegate
from .core.chatgpt_plugin_instance import ChatGPTPluginInstance,ChatGPTMessageHandler
from .core.message_context import ChatGPTMessageContext
from .util.string_operation import extract_json
from .util.datetime_operation import calculate_timestamp_factor

curr_dir = os.path.dirname(__file__)

class DeepCosplay(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, delegate: ChatGPTDelegate, channel_id: int,instance) -> None:
        super().__init__(bot, delegate, channel_id, "deep_cosplay_mode_config",instance)

        self.recent_messages: List[ChatGPTMessageContext] = []

        self._ask_amiya_in_progress = False
        self.topic_active = False
        self.topic_users = set()
        self.last_reply_time = time.time()
        self.topic_messages : List[ChatGPTMessageContext] = []

        self.amiya_memory : List[ChatGPTMessageContext] = []
        self._queued_messages : List[ChatGPTMessageContext] = []

        self.interest : float = 0

    def new_topic(self, messages_in_conversation = None):
        self.last_reply_time = time.time()
        
        if self.topic_active == False:
            self.bot.debug_log(f'创建新话题')
            self.topic_active = True
            self.amiya_memory = []
            self.interest = float(self.get_handler_config('interest_initial',1000.0))
        
        if messages_in_conversation is not None:
            self.topic_messages.extend(messages_in_conversation)
            for mess in messages_in_conversation:
                if mess.user_id not in self.topic_users:
                    self.topic_users.add(mess.user_id)

    def close_topic(self):
        self.bot.debug_log(f'话题超时，恢复静默')
        self.topic_active = False
        self.topic_users.clear()

    def load_template(self,template_name):
        with open(f'{curr_dir}/../templates/{template_name}', 'r', encoding='utf-8') as file:
            content = file.read()
        return content

    async def on_message(self, data: Message, force: bool = False):

        message_context = ChatGPTMessageContext.from_message(data)
        self.recent_messages.append(message_context)

        if force:
            self.bot.debug_log(f'force')
            self.new_topic([message_context])
            await self.send_message(await self.ask_amiya([message_context]))
            return

        if not self.topic_active:
            self.bot.debug_log(
                            f'当前未过时消息的长度是: {len(self.recent_messages)}')
            if len(self.recent_messages) >= float(self.get_handler_config("conversation_length", 10)):
                messages_in_conversation = self.recent_messages[-int(
                    self.get_handler_config("conversation_length", 10)):]
                if await self.check_conversation(messages_in_conversation):
                    if random.random() < float(self.get_handler_config('conversation_probability', 0.1)):                    
                        self.bot.debug_log(
                            f'确定加入对话')
                        self.new_topic(messages_in_conversation)
                        await self.send_message(await self.ask_amiya_with_queue(messages_in_conversation))
                else:
                    self.recent_messages = self.recent_messages[-int(
                        float(self.get_handler_config("conversation_length", 10))/2):]
                    self.bot.debug_log(
                        f'检测话题失败，话题存储折半')
                    
            if not self.topic_active and len(data.text_original) > 4:
                async def check_reply():
                    await asyncio.sleep(float(self.get_handler_config('no_reply_timeout', 60)))
                    recent_messages_duration = [
                        msg for msg in self.recent_messages
                        if time.time() - msg.timestamp <= float(self.get_handler_config('no_reply_timeout', 60))
                    ]

                    
                    if not recent_messages_duration and not self.topic_active:                        
                        self.bot.debug_log(
                            f'进行冷场判定 {message_context.text}')
                        if random.random() < float(self.get_handler_config('reply_probability', 0.1)):
                            self.bot.debug_log(
                                f'冷场判定成功')
                            self.new_topic([message_context])
                            await self.send_message(await self.ask_amiya_with_queue([message_context]))
                    else:
                        self.bot.debug_log(
                            f'该条消息已被真人回复')

                asyncio.create_task(check_reply())
        else:

            if message_context.is_quote:
                self.bot.debug_log(f'用户加入话题')
                self.topic_users.add(data.user_id)
                self.interest = self.interest + 200
            else:
                if time.time() - self.last_reply_time > float(self.get_handler_config('topic_timeout', 30)):
                    self.close_topic()

            self.bot.debug_log(f'持续对话判断:{data.user_id} -> {self.topic_users} ')

            if data.user_id in self.topic_users:
                if random.random() < float(self.get_handler_config('topic_reply_probability', 0.1)):   
                    self.bot.debug_log(f'概率命中，将产生一条Topic回复')
                    self.topic_messages.append(message_context)
                    await self.send_message(await self.ask_amiya_with_queue([message_context]))
                    self.last_reply_time = time.time()
                else:
                    self.bot.debug_log(f'概率未命中，但增加50兴趣')
                    self.interest = self.interest + 50
                    self._queued_messages.extend([message_context])
                    self.last_reply_time = time.time()

        # 清理过期的消息 但是至少保留一条
        if len(self.recent_messages) > 1:
            discard_time = self.get_handler_config('old_message_discard_time', 60)
            self.recent_messages = [self.recent_messages[-1]] + [msg for msg in self.recent_messages[:-1]
                                                                 if time.time() - msg.timestamp <= float(discard_time)]

    def pick_prompt(self, context_list: List[ChatGPTMessageContext], max_chars=1000) -> Tuple[list, str, list]:

        request_obj = []
        
        picked_context = []

        result = ""
        for i in range(1, len(context_list) + 1):
            context = context_list[-i]
            if context.user_id != ChatGPTMessageContext.AMIYA_USER_ID:
                text_to_append = f'博士:{context.text}'
                # text_to_append = f'{context.nickname}博士:{context.text}'
            else:
                text_to_append = f'阿米娅:{context.text}'
            if len(result) + len(text_to_append) + 1 <= max_chars:
                # 如果拼接后的长度还没有超过1000个字符，就继续拼接
                result = text_to_append + "\n" + result
                if context.user_id != 0:
                    request_obj.append({"role": "user", "content": context.text})
                else:
                    request_obj.append({"role": "assistant", "content": context.text})
                picked_context.append(context)
            else:
                break
        request_obj.reverse()
        picked_context.reverse()
        return request_obj, result, picked_context

    # 根据一大堆话生成一个回复
    async def ask_amiya(self, context_list: List[ChatGPTMessageContext]) -> str:

        max_prompt_chars = 1000

        _,result,memory_to_add = self.pick_prompt(context_list,max_prompt_chars)

        command = self.load_template('amiya-template-v1.txt')

        command = command.replace("<<QUERY>>", result)

        max_memory_chars = 4000-len(command)

        _,memory_str,_ = self.pick_prompt(self.amiya_memory,max_memory_chars)

        self.bot.debug_log(f'当前Amiya记忆字符串: {memory_str}')
        command = command.replace("<<MEMORY>>", memory_str)

        success, response = await self.delegate.ask_chatgpt_raw([{"role": "user", "content": command}], self.channel_id)

        self.bot.debug_log(f'ChatGPT原始回复:{response}')

        json_objects = extract_json(response)

        cut_response = None
        for json_obj in json_objects:
            if json_obj.get('role', None) == '阿米娅':
                cut_response = json_obj.get('reply', None)
                break

        self.amiya_memory.extend(memory_to_add)

        self.bot.debug_log(f'memory:{self.amiya_memory}')

        if success and cut_response is not None:
            amiya_context = ChatGPTMessageContext(cut_response, '阿米娅')
        else:
            amiya_context = ChatGPTMessageContext('抱歉博士，阿米娅有点不明白。', '阿米娅')


        interest_decrease = random.randint(1, 100)

        time = None
        for previou_msg in reversed(self.recent_messages):
            if previou_msg.user_id == ChatGPTMessageContext.AMIYA_USER_ID:
                time = previou_msg.timestamp

        interest_factor = calculate_timestamp_factor(time,amiya_context.timestamp)

        self.interest = self.interest -interest_decrease * interest_factor
        self.bot.debug_log(f'兴趣变化{self.interest} -= {interest_decrease} * {interest_factor}')

        if self.interest <0 :
            self.bot.debug_log(f'兴趣耗尽')
            self.close_topic()
        
        
        self.amiya_memory.append(amiya_context)
        self.recent_messages.append(amiya_context)
        return amiya_context.text

    async def ask_amiya_with_queue(self,  message_context_list: List[ChatGPTMessageContext]):
        self._queued_messages.extend(message_context_list)

        if not self._ask_amiya_in_progress:
            self._ask_amiya_in_progress = True

            while self._queued_messages:
                messages_to_process = self._queued_messages.copy()
                self._queued_messages.clear()
                await self.send_message(await self.ask_amiya(messages_to_process))

            self._ask_amiya_in_progress = False

    # 可以判断一个str的列表是否属于同一个话题
    async def check_conversation(self, context_list: List[ChatGPTMessageContext]):

        _, request_text,_ = self.pick_prompt(context_list)

        command = self.load_template('conversation-probablity-template-v1.txt')

        command = command.replace('<<CONVERSATION>>',request_text)

        success, response = await self.delegate.ask_chatgpt_raw([{"role": "user", "content": command}], self.channel_id)
        
        self.bot.debug_log(f"检查对话是否为同一话题:\n{command}\n----------\n{response}")

        json_objects = extract_json(response)

        if not json_objects:
            return False

        # Assuming you want to check if 'conversation' is True in any of the JSON objects
        for json_obj in json_objects:
            if json_obj.get('conversation', False) == True:
                return True

        return False


    # 发送消息到指定频道
    async def send_message(self, message: str):
        if message is None:
            return

        message = Chain().text(f'{message}')
        await self.instance.send_message(message,channel_id=self.channel_id)

import time
import random
from threading import Timer
from typing import List

from amiyabot import Message, Chain
from .ask_chat_gpt import ChatGPTDelegate


class ChatGPTMessageContext:
    def __init__(self, data: Message, timestamp: float, user_id: int):
        self.data = data
        self.timestamp = timestamp
        self.user_id = user_id


class DeepCosplay:
    def __init__(self, delegate:ChatGPTDelegate, channel_id: int) -> None:
        self.delegate = delegate
        self.channel_id = channel_id

        self.recent_messages: List[ChatGPTMessageContext] = []
        self.conversation_timeout = 30
        self.conversation_length = 10
        self.no_reply_timeout = 60
        self.reply_probability = 0.1
        self.topic_active = False
        self.topic_users = set()
        self.last_reply_time = time.time()
        self.topic_messages = []

    async def on_message(self, data: Message, force: bool = False):
        message_context = ChatGPTMessageContext(data, time.time(), data.user_id)
        self.recent_messages.append(message_context)

        if force:
            self.topic_messages.append(message_context)
            await self.send_message(self.ask_amiya([message_context]))
            self.topic_active = True
            self.topic_users.add(data.user_id)
            self.last_reply_time = time.time()
            return

        if not self.topic_active:
            if len(data.text_original) > 4 and time.time() - message_context.timestamp > self.no_reply_timeout:
                if random.random() < self.reply_probability:
                    self.topic_messages.append(message_context)
                    await self.send_message(self.ask_amiya([message_context]))
                    self.topic_active = True
                    self.topic_users.add(data.user_id)
                    self.last_reply_time = time.time()

            if len(self.recent_messages) >= self.conversation_length:
                messages_in_conversation = self.recent_messages[-self.conversation_length:]
                if self.check_conversation(messages_in_conversation):
                    self.topic_messages.extend(messages_in_conversation)
                    await self.send_message(self.ask_amiya(messages_in_conversation))
                    self.topic_active = True
                    self.topic_users.add(data.user_id)
                    self.last_reply_time = time.time()

        else:
            if data.user_id in self.topic_users:
                self.topic_messages.append(message_context)
                await self.send_message(self.ask_amiya(self.topic_messages + [message_context]))
                self.last_reply_time = time.time()

            if self.is_quoting(message_context):
                self.topic_users.add(data.user_id)

            if time.time() - self.last_reply_time > self.conversation_timeout:
                self.topic_active = False
                self.topic_users.clear()
                self.topic_messages.clear()

        # 清理过期的消息
        self.recent_messages = [msg for msg in self.recent_messages if time.time() - msg.timestamp <= self.no_reply_timeout]


    # 根据一大堆话生成一个回复
    def ask_amiya(self, context_list: List[ChatGPTMessageContext]) -> str:
        max_chars = 1000
        result = ""
        for i in range(1, len(context_list) + 1):
            context = context_list[-i]
            text_to_append = context.data.user_id + ":" + context.data.text_original
            if len(result) + len(text_to_append) + 1 <= max_chars:
                # 如果拼接后的长度还没有超过1000个字符，就继续拼接
                result = text_to_append + "\n" + result
            else:
                break
        return "deep_cosplay:"+"\n"+result

    # 可以判断一个str的列表是否属于同一个话题
    def check_conversation(self, context_list: List[ChatGPTMessageContext]):
        return True

    # 发送消息到指定频道
    async def send_message(self, message: str):
        data = self.topic_messages[-1]
        await data.send(message)

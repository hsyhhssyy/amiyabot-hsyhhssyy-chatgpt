import time
import random
import asyncio
import os
import re
import math
import time

from typing import List, Tuple
from statistics import median

from amiyabot import Message, Chain

from ..core.message_context import ChatGPTMessageContext
from ..core.chatgpt_plugin_instance import ChatGPTPluginInstance
from ..core.ask_chat_gpt import ChatGPTDelegate

from ..util.string_operation import extract_json
from ..util.complex_math import find_most_recent_cluster,dbscan

curr_dir = os.path.dirname(__file__)

class ChatLogStorage():
    def __init__(self, bot: ChatGPTPluginInstance, delegate: ChatGPTDelegate, channel_id):
        self.recent_messages: List[ChatGPTMessageContext] = []
        self.bot = bot
        self.delegate = delegate
        self.channel_id = channel_id

        self.average_message_in_60_sec = 0
        self.mediua_freq = 60
        
        self.topic = None

        self.__collect_data()


    def __collect_data(self):
        asyncio.create_task(self.__collect_average_message_in_60_sec())
        asyncio.create_task(self.__collect_topic())
        asyncio.create_task(self.__collect_average_message_freq_in_1_day())

    async def __collect_average_message_in_60_sec(self):
        while True:
            start_time = time.time()
            end_time = start_time + 60
            total_items = 0
            while time.time() < end_time:
                total_items += len(self.recent_messages)
                await asyncio.sleep(0.1)
            average = total_items / 60

            self.average_message_in_60_sec = average
            
            await asyncio.sleep(5)

    def messages_to_string(self,messages:List[List[ChatGPTMessageContext]]):
        """把一个List[List[ChatGPTMessageContext]]转化为可读的字符串"""
        
        result = []
        for sublist in messages:
            formatted_sublist = [f"{context.nickname}: {context.text} ({context.timestamp})\n"  for context in sublist]
            result.append(" ".join(formatted_sublist))
        return "\n---\n".join(result)

    async def __collect_topic(self):

        eps = 120 # 单位是 秒
        min_samples = 5 # 最少聚类

        while True:
            await asyncio.sleep(2)

            clusters = dbscan(self.recent_messages, eps, min_samples)

            if len(clusters) == 0:
                continue

            recent_cluster = find_most_recent_cluster(clusters)
            
            # self.bot.debug_log(f'clusters:\n{self.messages_to_string(clusters)}')
            # self.bot.debug_log(f'recent cluster:\n{len(recent_cluster)}')

            if recent_cluster and len(recent_cluster)>0:
                # 计算列表长度的一半
                half_length = len(recent_cluster) // 2
                # 统计具有非空topic属性的元素数量                
                non_empty_topic_count = 0

                topic_content = None
                for message in recent_cluster:
                    if hasattr(message, 'topic') and message.topic is not None:
                        topic_content = message.topic
                        non_empty_topic_count = non_empty_topic_count+1

                non_empty_topic_count = len(recent_cluster) - non_empty_topic_count

                # self.bot.debug_log(f'N: {half_length} {non_empty_topic_count} {topic_content}')

                if non_empty_topic_count >= half_length:
                    # 有一半以上元素没有被判断topic
                    success ,topic = await self.check_conversation(recent_cluster)
                    
                    if success:
                        self.topic = topic
                    else:
                        self.topic = None

                    for msg in recent_cluster:
                        if success:
                            msg.topic = topic
                        else:
                            msg.topic = "None"

    async def __collect_average_message_freq_in_1_day(self):

        while True:
            await asyncio.sleep(60*60)

            avg_frequencies = self.average_freq_per_user(recent_messages)
            if avg_frequencies:
                mediua_freq = median(avg_frequencies)
                self.mediua_freq = mediua_freq
            else:
                self.mediua_freq = 60

    def average_freq_per_user(self):
        current_time = time.time()
        one_day_seconds = 86400
        start_time = current_time - one_day_seconds

        recent_day_messages = [message for message in self.recent_messages if message.timestamp >= start_time]

        user_messages = {}
        for message in recent_day_messages:
            if message.user_id not in user_messages:
                user_messages[message.user_id] = []
            user_messages[message.user_id].append(message.timestamp)
        
        avg_frequencies = []
        for user_id, timestamps in user_messages.items():
            sorted_timestamps = sorted(timestamps)
            time_diffs = [sorted_timestamps[i+1] - sorted_timestamps[i] for i in range(len(sorted_timestamps) - 1)]
            if time_diffs:
                avg_frequencies.append(sum(time_diffs) / len(time_diffs))
        return avg_frequencies
        

    # 可以判断一个str的列表是否属于同一个话题
    async def check_conversation(self, context_list: List[ChatGPTMessageContext]):

        topic_content = None
        for message in context_list:
            if hasattr(message, 'topic') and message.topic is not None:
                topic_content = message.topic

        _, request_text,_ = ChatGPTMessageContext.pick_prompt(context_list,1000,True)

        if topic_content is not None:
            with open(f'{curr_dir}/../../templates/conversation-probablity-template-v2.txt', 'r', encoding='utf-8') as file:
                command = file.read()
            
            command = command.replace('<<TOPIC>>',topic_content)

        else:        
            with open(f'{curr_dir}/../../templates/conversation-probablity-template-v1.txt', 'r', encoding='utf-8') as file:
                command = file.read()

        command = command.replace('<<CONVERSATION>>',request_text)

        # 因为3.5 API 在这个场景下表现也很好，因此这里就不浪费钱调用4的API了
        success, response = await self.delegate.ask_chatgpt_raw([{"role": "user", "content": command}], self.channel_id,"gpt-3.5-turbo")
        
        # self.bot.debug_log(f"检查对话是否为同一话题:\n{command}\n----------\n{response}")

        json_objects = extract_json(response)

        if not json_objects:
            return False,""

        # Assuming you want to check if 'conversation' is True in any of the JSON objects
        for json_obj in json_objects:
            if json_obj.get('conversation', False) == True:

                probability = json_obj.get('similarity', 0)

                if probability < 0.8:
                    return False,""

                similarity = json_obj.get('similarity', 0)
                
                if topic_content is not None and similarity > 0.85:
                    return True,topic_content
                
                return True,json_obj.get('topic', "")

        return False,""

    def enqueue(self, data: Message):
        message_context = ChatGPTMessageContext.from_message(data)
        self.recent_messages.append(message_context)

    def message_after(self,timestamp:float) -> List[ChatGPTMessageContext]:
        result = []
        for context in self.recent_messages:
            if context.timestamp > timestamp:
                result.append(context)
        return result
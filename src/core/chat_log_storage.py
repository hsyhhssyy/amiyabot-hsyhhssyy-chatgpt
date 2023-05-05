import time
import random
import asyncio
import os
import re
import math
import time

from typing import List, Tuple

from amiyabot import Message, Chain

from ..core.message_context import ChatGPTMessageContext

from ..util.string_operation import extract_json
from ..util.complex_math import find_most_recent_cluster,dbscan

curr_dir = os.path.dirname(__file__)

class ChatLogStorage():
    def __init__(self):
        self.recent_messages: List[ChatGPTMessageContext] = []
        
        self.average_message_in_60_sec = 0

        self.topic = None

        self.__collect_data()


    def __collect_data(self):
        asyncio.create_task(self.__collect_average_message_in_60_sec())

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

    async def __collect_topic(self):

        eps = 30 # 单位是 秒
        min_samples = 10 # 最少聚类

        while True:
            await asyncio.sleep(30)

            clusters = dbscan(self.recent_messages, eps, min_samples)
            recent_cluster = find_most_recent_cluster(clusters)
            if recent_cluster:
                # 计算列表长度的一半
                half_length = len(recent_cluster) // 2
                # 统计具有非空topic属性的元素数量
                non_empty_topic_count = sum(1 for message in recent_cluster if hasattr(message, 'topic') and getattr(message, 'topic'))

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


    # 可以判断一个str的列表是否属于同一个话题
    async def check_conversation(self, context_list: List[ChatGPTMessageContext]):

        _, request_text,_ = self.pick_prompt(context_list,1000,True)

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
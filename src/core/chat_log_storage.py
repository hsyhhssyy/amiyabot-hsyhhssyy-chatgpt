import json
import time
import random
import asyncio
import os
import re
import math
import time
import traceback

from collections import Counter,deque
from typing import List, Tuple

from amiyabot import Message, Chain

from amiyabot.log import LoggerManager

from ..core.message_context import ChatGPTMessageContext
from ..core.chatgpt_plugin_instance import ChatGPTPluginInstance
from ..core.developer_types import BLMAdapter

from ..util.string_operation import convert_to_float
from ..util.complex_math import find_most_recent_cluster,dbscan,median

curr_dir = os.path.dirname(__file__)

logger = LoggerManager('ChatGPT')

class ChatLogStorage():
    def __init__(self, bot: ChatGPTPluginInstance, blm_lib: BLMAdapter, channel_id,collect_data:bool = True):
        self.recent_messages: List[ChatGPTMessageContext] = []
        self.bot = bot
        self.blm_lib = blm_lib
        self.channel_id = channel_id

        self.average_message_in_60_sec = 0
        self.mediua_freq = 60
        
        self.topic = None

        self.eps = 120

        self.assistant_thread = ""

        if collect_data:
            self.__collect_data()

    NoTopic = 'NOTOPIC'

    def debug_log(self, message):
        show_log = self.bot.get_config("show_log")
        if show_log == True:
            logger.info(f'[{self.channel_id:<10}]{message}')

    def __collect_data(self):
        asyncio.create_task(self.__collect_average_message_in_60_sec())
        asyncio.create_task(self.__collect_topic())
        asyncio.create_task(self.__collect_average_message_freq_in_1_day())

    async def __collect_average_message_in_60_sec(self):
        """每隔5秒统计过去60秒内的消息数量，然后将计算得到的平均值存储到self.average_message_in_60_sec中"""
        window_size = 5
        message_count_window = deque(maxlen=window_size)

        while True:
            now = time.time()
            one_minute_ago = now - 60
            message_count = sum(1 for msg in self.recent_messages if msg.timestamp > one_minute_ago)
            message_count_window.append(message_count)
            
            if len(message_count_window) == window_size:
                self.average_message_in_60_sec = int (sum(message_count_window) / window_size)

            await asyncio.sleep(5)

    def messages_to_string(self,messages:List[List[ChatGPTMessageContext]]):
        """把一个List[List[ChatGPTMessageContext]]转化为可读的字符串"""
        
        result = []
        for sublist in messages:
            formatted_sublist = [f"{context.nickname}: {context.text} ({context.timestamp})\n"  for context in sublist]
            result.append(" ".join(formatted_sublist))
        return "\n---\n".join(result)

    async def __collect_topic(self):

        # 因为使用 low_cost_model 的API没必要考虑富哥问题
        # eps = self.mediua_freq * (1 - 0.5 *random.random())  # 单位是 秒

        while True:
            await asyncio.sleep(2)

            # 如果半小时还没有人说话，则丢弃当前话题
            if self.topic != ChatLogStorage.NoTopic:
                last_message = self.recent_messages[-1]
                if last_message.timestamp < time.time() - 1800:
                    self.topic = ChatLogStorage.NoTopic
                    self.debug_log(f'因长时间无人说话，丢弃当前话题{self.topic}')
                    continue

            if self.eps==0:
                self.topic = ChatLogStorage.NoTopic
                continue

            min_samples = self.average_message_in_60_sec # 最少聚类

            min_samples_factor = 5

            # 因为使用 low_cost_model 的API没必要考虑富哥问题
            # if self.bot.get_config("model",self.channel_id) == "gpt-4" and self.bot.get_config("im_rich",self.channel_id) != True:
            #    min_samples_factor = 10

            if min_samples < min_samples_factor:
                min_samples = min_samples_factor
            
            if min_samples > 50:
                min_samples = 50
                
            clusters = dbscan(self.recent_messages, self.eps, min_samples)

            if len(clusters) <=0:
                continue
        
            recent_cluster = find_most_recent_cluster(clusters)

            # self.debug_log(f'60秒内平均聊天{self.average_message_in_60_sec}: Cluster数量:{len(clusters)} 最近Cluser长度:{len(recent_cluster)} 最小取样:{min_samples}')

            if recent_cluster and len(recent_cluster)>=self.average_message_in_60_sec:
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

                # self.debug_log(f'尝试判断Topic是否出现/继续存在: if {non_empty_topic_count}(当前新增聊天) >= {half_length}(最近聊天聚类/2)  当前话题:{topic_content}')

                if non_empty_topic_count >= half_length:
                    # 有一半以上元素没有被判断topic
                    try:
                        success ,topic = await self.check_conversation(recent_cluster)
                    except Exception as e:
                        self.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')
                        success = False

                    if success and topic is not None and topic != ChatLogStorage.NoTopic:
                        if self.topic != topic:                        
                            self.debug_log(f'新话题诞生:{topic}')
                        self.topic = topic
                    else:
                        if self.topic != ChatLogStorage.NoTopic:
                            self.debug_log(f'因跑题，丢弃当前话题{self.topic}')
                        self.topic = ChatLogStorage.NoTopic

                    for msg in recent_cluster:
                        if success:
                            msg.topic = topic
                        else:
                            msg.topic = ChatLogStorage.NoTopic
            else:
                recent_recent_message = self.recent_messages[-self.average_message_in_60_sec:]
                if all(((not hasattr(msg, 'topic')) or (msg.topic ==  ChatLogStorage.NoTopic) ) for msg in recent_recent_message):
                    if self.topic is not None and self.topic != ChatLogStorage.NoTopic:                        
                        self.debug_log(f'长时间跑题，回归静默')
                        self.topic = ChatLogStorage.NoTopic

    async def __collect_average_message_freq_in_1_day(self):

        while True:
            await asyncio.sleep(60)

            try:
                avg_frequencies = self.average_freq_per_user()
                if avg_frequencies:
                    self.debug_log(f'avg_frequencies:{avg_frequencies}')
                    
                    mediua_freq = median(avg_frequencies)
                    self.mediua_freq = mediua_freq
                else:
                    self.mediua_freq = 60

            except Exception as e:
                # 如果重试次数用完仍然没有成功，返回错误信息
                self.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')
            

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

        topic_counter = Counter()

        for message in context_list:
            if hasattr(message, 'topic') and message.topic is not None:
                topic_counter[f'{message.topic}'] += 1

        most_common_topic = topic_counter.most_common(1)

        topic_content = most_common_topic[0][0] if most_common_topic else None

        _, request_text,_ = ChatGPTMessageContext.pick_prompt(context_list,1000, True)

        if topic_content == ChatLogStorage.NoTopic:
            topic_content = None

        if topic_content is not None:
            with open(f'{curr_dir}/../../templates/conversation-probablity-template-v3-u.txt', 'r', encoding='utf-8') as file:
                command = file.read()
            
            command = command.replace('<<TOPIC>>',topic_content)

        else:        
            with open(f'{curr_dir}/../../templates/conversation-probablity-template-v3-c.txt', 'r', encoding='utf-8') as file:
                command = file.read()

        command = command.replace('<<CONVERSATION>>',request_text)

        low_cost_model = self.bot.get_model_in_config('low_cost_model_name',self.channel_id)
        
        json_str = await self.blm_lib.chat_flow(
            prompt=command, 
            model=low_cost_model ,
            channel_id=self.channel_id,
            json_mode=True,
            )
        
        if not json_str:
            return False,""
        
        json_objects = json.loads(json_str)
        
        if not isinstance(json_objects,list):
            json_objects = [json_objects]

        for json_obj in json_objects:
            if json_obj.get('conversation', False) == True:

                probability = float(convert_to_float(json_obj.get('probability', 0)))

                if probability < 0.8:
                    return False,""

                similarity = float(convert_to_float(json_obj.get('similarity', 0)))
                
                if topic_content is not None and similarity >= 0.8:
                    return True,topic_content
                
                new_topic = json_obj.get('topic', "")

                if isinstance(new_topic, list):
                    new_topic = ','.join(new_topic)

                return True,new_topic

        return False,""

    def enqueue(self, data: Message) -> ChatGPTMessageContext:
        message_context = ChatGPTMessageContext.from_message(data)
        self.recent_messages.append(message_context)
        return message_context

    def message_after(self,timestamp:float) -> List[ChatGPTMessageContext]:
        result = []
        for context in self.recent_messages:
            if context.timestamp > timestamp:
                result.append(context)
        return result
import time
import random
import asyncio
import os
import re
import math
import time

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

        self.last_call_time = 0

        self._ask_amiya_in_progress = False
        self.topic_active = False
        self.topic = ""
        self.average_message_in_60_sec = 10
        self.topic_users = set()
        self.last_reply_time = time.time()
        self.topic_messages : List[ChatGPTMessageContext] = []

        self.amiya_memory : List[ChatGPTMessageContext] = []
        self._queued_messages : List[ChatGPTMessageContext] = []

        self.interest : float = 0

    
    def get_formatted_config(self,config_name):

        if config_name == "topic_reply_probability":
            return float(self.get_handler_config('topic_reply_probability',0.1))

        if config_name == "old_message_discard_time":
            return int(self.get_handler_config('old_message_discard_time',60))
        
        if config_name == "conversation_length":
            if self.average_message_in_60_sec >5:
                self.bot.debug_log(f'当前的平均对话长度值:{self.average_message_in_60_sec}')
                return self.average_message_in_60_sec
            else:
                self.bot.debug_log(f'当前的平均对话长度值:5(默认值)')
                return 5

        self.bot.debug_log(f'代码错误！读取了未配置的变量{config_name}')

        return self.get_handler_config(config_name)

    async def calculate_average(self):
        while True:
            start_time = time.time()
            end_time = start_time + 60
            total_items = 0
            while time.time() < end_time:
                total_items += len(self.recent_messages)
                await asyncio.sleep(0.1)
            average = total_items / 60
            self.average_message_in_60_sec = average
            await asyncio.sleep(5)  # 每5秒输出一次平均数

    def get_reply_probability(self, mean_time:int = 30):
        mean = (time_50_percent + time_100_percent) / 2
        std_dev = (time_100_percent - time_50_percent) / (2 * math.erf(1 / math.sqrt(2)))
        time_interval = time.time() - self.last_call_time
        self.last_call_time = time.time()
        x = time_interval / 60
        z = (x - mean) / std_dev
        p = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        pdf = 1 / (std_dev * math.sqrt(2 * math.pi)) * math.exp(-0.5 * ((x - mean) / std_dev) ** 2)

        # 最后总体乘上一个配置项Factor
        return pdf * 0.5

    def new_topic(self, messages_in_conversation = None,topic = None):
        
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
        
        if topic is None:
            self.topic = ""
        else:
            self.topic = topic

    def close_topic(self):
        self.bot.debug_log(f'话题结束')
        self.topic_active = False
        self.topic_users.clear()
        self.amiya_memory.clear()
        self.recent_messages = [self.recent_messages[-1]]

    def load_template(self,template_name:str):

        template_filename = template_name

        if template_name.startswith("amiya-template"):
            model = self.bot.get_config('model', self.channel_id)
            self.bot.debug_log(f'template select: {model} {template_filename}')
            if(model == "gpt-4"):
                template_filename = "amiya-template-v2.txt"


        with open(f'{curr_dir}/../templates/{template_filename}', 'r', encoding='utf-8') as file:
            content = file.read()
        return content

    async def on_message(self, data: Message, force: bool = False):
        message_context = ChatGPTMessageContext.from_message(data)
        self.recent_messages.append(message_context)

        if not self.topic_active:

            if force:
                self.bot.debug_log(f'force')
                messages_in_conversation = self.recent_messages[(0-self.get_formatted_config("conversation_length")):]
                _,topic = await self.check_conversation(messages_in_conversation)
                self.new_topic([message_context],topic)
                await self.ask_amiya_with_queue([message_context],True)
            else:
                self.bot.debug_log(
                                f'当前未过时消息的长度是: {len(self.recent_messages)}')
                if len(self.recent_messages) >= self.get_formatted_config("conversation_length"):
                    messages_in_conversation = self.recent_messages[(0-self.get_formatted_config("conversation_length")):]
                    is_conversation,topic = await self.check_conversation(messages_in_conversation)
                    if is_conversation == True:
                        self.bot.debug_log(
                            f'确定加入对话')
                        self.new_topic(messages_in_conversation,topic)
                        await self.ask_amiya_with_queue(messages_in_conversation)
                    
                    slice_size = int(0-self.get_formatted_config("conversation_length")/2)
                    self.bot.debug_log(f'slice:{slice_size}')
                    self.recent_messages = self.recent_messages[slice_size:]
                    self.bot.debug_log(f'话题存储折半')
                        
                if not self.topic_active and len(data.text_original) > 4:
                    async def check_reply():
                        timeout = float(self.get_handler_config('no_reply_timeout', 60))
                        await asyncio.sleep(timeout)
                        recent_messages_duration = [
                            msg for msg in self.recent_messages
                            if time.time() - msg.timestamp <= timeout
                        ]
                        
                        if not recent_messages_duration and not self.topic_active:                        
                            self.bot.debug_log(
                                f'进行冷场判定 {message_context.text}')
                            if random.random() < float(self.get_handler_config('reply_probability', 0.1)):
                                self.bot.debug_log(
                                    f'冷场判定成功')
                                # 3.1.0 版本起，冷场判断也要判断话题和对话长度
                                messages_in_conversation = self.recent_messages[(0-self.get_formatted_config("conversation_length")):]
                                if len(messages_in_conversation) >= self.get_formatted_config("conversation_length")/2:
                                    is_conversation,topic = await self.check_conversation(messages_in_conversation)
                                    if is_conversation == True:
                                        self.new_topic(messages_in_conversation,topic)
                                        await self.ask_amiya_with_queue(messages_in_conversation)
                        else:
                            self.bot.debug_log(
                                f'该条消息已被真人回复')

                    asyncio.create_task(check_reply())
        else:

            if message_context.is_quote or force:
                self.bot.debug_log(f'用户{data.nickname}:{data.user_id}加入话题')
                self.topic_users.add(data.user_id)
                self.interest = self.interest + 200
            else:
                if time.time() - self.last_reply_time > float(self.get_handler_config('topic_timeout', 30)):
                    self.bot.debug_log(f'太久无人回复,超过topic_timeout')
                    self.close_topic()

            self.bot.debug_log(f'持续对话判断:{data.user_id} -> {self.topic_users} ')

            if data.user_id in self.topic_users:
                if await self.ask_amiya_with_queue([message_context]):
                    self.topic_messages.append(message_context)                    
                else:
                    self.bot.debug_log(f'概率未命中，但增加兴趣，增加的量和概率成反比')
                    self.interest = self.interest + 50 * (1- self.get_formatted_config("topic_reply_probability"))
                    self._queued_messages.extend([message_context])

        # 清理过期的消息 但是至少保留一条
        if len(self.recent_messages) > 1:
            discard_time = self.get_formatted_config('old_message_discard_time')
            self.recent_messages = [self.recent_messages[-1]] + [msg for msg in self.recent_messages[:-1]
                                                                 if time.time() - msg.timestamp <= float(discard_time)]
        
        self.last_reply_time = time.time()

    def pick_prompt(self, context_list: List[ChatGPTMessageContext], max_chars=1000,distinguish_doc:bool= False) -> Tuple[list, str, list]:

        request_obj = []
        
        picked_context = []

        result = ""
        for i in range(1, len(context_list) + 1):
            context = context_list[-i]
            if context.user_id != ChatGPTMessageContext.AMIYA_USER_ID:
                if distinguish_doc:
                    text_to_append = f'{context.nickname}博士:{context.text}'
                else:
                    text_to_append = f'博士:{context.text}'
            else:
                if context.text != "抱歉博士，阿米娅有点不明白。":
                    text_to_append = f'阿米娅:{context.text}'
                else:
                    text_to_append = ""
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
        max_chatgpt_chars = 4000
        distinguish_doc = False

        if self.bot.get_config("model",self.channel_id) == "gpt-4":
            max_chatgpt_chars = 8000
            distinguish_doc = True

        _,result,memory_to_add = self.pick_prompt(context_list,max_prompt_chars,distinguish_doc)

        command = self.load_template('amiya-template-v1.txt')

        command = command.replace("<<QUERY>>", result)

        command = command.replace("<<Topic>>", self.topic)

        max_prompt_chars = max_chatgpt_chars-len(command)
        self.bot.debug_log(f'加入最多{max_prompt_chars}字的memory')

        _,memory_str,_ = self.pick_prompt(self.amiya_memory,max_prompt_chars,distinguish_doc)

        self.bot.debug_log(f'当前Amiya记忆字符串: {memory_str}')
        command = command.replace("<<MEMORY>>", memory_str)


        success , message_send, content_factor = await self.get_amiya_response(command, self.channel_id)

        self.amiya_memory.extend(memory_to_add)
        self.bot.debug_log(f'memory add:{self.amiya_memory}')

        interest_decrease = random.randint(50, 100)

        time = None
        for previou_msg in reversed(self.recent_messages):
            if previou_msg.user_id == ChatGPTMessageContext.AMIYA_USER_ID:
                time = previou_msg.timestamp

        for amiya_context in message_send:
            interest_factor = calculate_timestamp_factor(time,amiya_context.timestamp)

            self.interest = self.interest - interest_decrease * interest_factor * content_factor
            self.bot.debug_log(f'兴趣变化{self.interest} -= {interest_decrease} * {interest_factor} * {content_factor}')

            if self.interest <0 :
                self.bot.debug_log(f'兴趣耗尽')
                self.close_topic()
                    
            self.amiya_memory.append(amiya_context)
            self.recent_messages.append(amiya_context)
            
        return True

    async def get_amiya_response(self, command: str, channel_id: str) -> Tuple[bool, str]:
        max_retries = int(self.get_handler_config('max_retries', 3))

        if max_retries < 1:
            max_retries = 3
        
        retry_count = 0 

        self.bot.debug_log(f'ChatGPT Max Retry: {max_retries}')

        message_send = []

        corelation_on_topic = 0.8
        corelation_on_conversation = 0.8

        interest_factor = 1

        try:
        
            successful_sent = False
            
            while retry_count < max_retries:
                success, response = await self.delegate.ask_chatgpt_raw([{"role": "user", "content": command}], channel_id)

                # self.bot.debug_log(f'ChatGPT原始回复:{response}')

                json_objects = extract_json(response)


                words_response = None
                response_with_mental = None
                for json_obj in json_objects:
                    if json_obj.get('role', None) == '阿米娅':
                        words_response = json_obj.get('reply', None)
                        response_with_mental = words_response
                        if self.get_handler_config('output_mental', False) == True:
                            mental = json_obj.get('mental', None)
                            if mental is not None and mental != "":
                                response_with_mental = f'({mental})\n{words_response if words_response is not None else ""}'
                        
                        if words_response is None:
                            continue

                        corelation_on_topic = json_obj.get('CorelationOnTopic', 0.8)
                        corelation_on_conversation = json_obj.get('CorelationOnConversation', 0.8)

                        max_factor = 5
                        min_factor = 1

                        if corelation_on_topic <0.8:
                            factor = max_factor - (max_factor - min_factor) * (corelation_on_topic - 0.8) / 0.8
                            interest_factor = interest_factor * factor
                        
                        if corelation_on_conversation < 0.8:
                            factor = max_factor - (max_factor - min_factor) * (corelation_on_conversation - 0.8) / 0.8
                            interest_factor = interest_factor * factor

                        amiya_context = ChatGPTMessageContext(words_response, '阿米娅')
                        await self.send_message(response_with_mental)
                        message_send.append(amiya_context)
                        successful_sent = True

                        if self.get_handler_config('output_activity', False) == True:
                            activity = json_obj.get('activity', None)
                            if activity is not None and activity != "":
                                await self.send_message(f'({activity})')

                if successful_sent:
                    break
                else:
                    self.bot.debug_log(f'未读到Json，重试第{retry_count+1}次')
                    retry_count += 1

            if not successful_sent:
                # 如果重试次数用完仍然没有成功，返回错误信息
                amiya_context = ChatGPTMessageContext('抱歉博士，阿米娅有点不明白。', '阿米娅')
                await self.send_message('抱歉博士，阿米娅有点不明白。')
                message_send.append(amiya_context)
                return False, message_send,interest_factor

        except Exception as e:
            # 如果重试次数用完仍然没有成功，返回错误信息
                self.bot.debug_log(f'Unknown Error {e}')
                amiya_context = ChatGPTMessageContext('抱歉博士，阿米娅有点不明白。', '阿米娅')
                await self.send_message('抱歉博士，阿米娅有点不明白。')
                message_send.append(amiya_context)
                return False, message_send,interest_factor

        return True, message_send,interest_factor


    async def ask_amiya_with_queue(self,  message_context_list: List[ChatGPTMessageContext], force=False):

        if not force:
            probability = self.get_reply_probability()
            rand_float = random.random()
            self.bot.debug_log(f'get_reply_probability:{rand_float} - {probability}')
            if  rand_float > probability:
                return False

        self._queued_messages.extend(message_context_list)

        if not self._ask_amiya_in_progress:
            self._ask_amiya_in_progress = True

            while self._queued_messages:
                messages_to_process = self._queued_messages.copy()
                self._queued_messages.clear()
                self.bot.debug_log(f'ask_amiya_with_queue准备对{len(messages_to_process)}条消息进行处理')
                await self.ask_amiya(messages_to_process)

            self._ask_amiya_in_progress = False
        else:
            self.bot.debug_log(f'ask_amiya_with_queue 正忙，消息已被延后处理')

        return True

    # 可以判断一个str的列表是否属于同一个话题
    async def check_conversation(self, context_list: List[ChatGPTMessageContext]):

        _, request_text,_ = self.pick_prompt(context_list,1000,True)

        command = self.load_template('conversation-probablity-template-v1.txt')

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


    # 发送消息到指定频道
    async def send_message(self, message: str):
        if message is None:
            return

        debug_info =  f'{{Topic:"{self.topic}",Interest:{self.interest}}}'

        self.bot.debug_log(f'show_log_in_chat:{self.get_handler_config("show_log_in_chat")}')

        if self.get_handler_config("show_log_in_chat"):
            message = f"{debug_info}\n{message}"

        messageChain = Chain().text(f'{message}')
        await self.instance.send_message(messageChain,channel_id=self.channel_id)

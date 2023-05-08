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
from .core.chat_log_storage import ChatLogStorage

from .util.string_operation import extract_json
from .util.datetime_operation import calculate_timestamp_factor
from .util.complex_math import scale_to_reverse_exponential

curr_dir = os.path.dirname(__file__)

class DeepCosplay(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, delegate: ChatGPTDelegate, channel_id: int,instance) -> None:
        super().__init__(bot, delegate, channel_id, "deep_cosplay_mode_config",instance)

        self.storage = ChatLogStorage(bot,delegate,self.channel_id)

        self.amiya_topic = ""
        self.interest : float = 0

        self.reply_check = self.__reply_check_gen()

        asyncio.create_task(self.__amiya_loop())

    def __reply_check_gen(self):

        last_true_time = time.time()
        consecutive_false_count = 0

        while True:
            
            try:

                mean_time = self.storage.mediua_freq         
                if mean_time < 30:
                    mean_time = 30
                
                if mean_time > 3600:
                    mean_time = 3600

                current_time = time.time()
                time_elapsed = current_time - last_true_time
                probability = 1 - ((1 - 1/mean_time) ** time_elapsed)

                # 如果当前没有话题，则几率折半
                if self.storage.topic is None:
                    probability = probability * 0.5
                            
                # 如果当前兴趣丢失，则概率归零
                if self.interest <= 0:
                    probability = 0

                rand_value = random.random()

                self.bot.debug_log(f'{time_elapsed}/{mean_time} 秒间隔后的说话概率 : {rand_value} < {probability} ?')
                    
                if rand_value < probability:
                    last_true_time = current_time
                    consecutive_false_count = 0
                    yield True
                else:
                    consecutive_false_count += 1
                    yield False
            
            except Exception as e:
                # 如果重试次数用完仍然没有成功，返回错误信息
                self.bot.debug_log(f'Unknown Error {e}')

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
        self.storage.enqueue(data)

    def generate_minimum_message_interval(self, factor:int):
        if factor < 20:
            raise ValueError("factor 不能小于20.")

        # 定义一个包含所有可能输出值的列表
        numbers = list(range(0, factor + 1))

        # 为每个数字定义权重，以满足题目中的概率要求
        weights = []

        for num in numbers:
            if num < 5:
                weights.append(0.5)  # 非常低的概率
            elif num < 10:
                weights.append(1)    # 较低的概率
            elif num <= 20:
                weights.append(10)   # 大部分情况
            else:
                weights.append(0.5)  # 小概率高于20

        # 使用random.choices()函数根据权重随机选择一个数字
        interval = random.choices(numbers, weights=weights, k=1)[0]

        return interval

    async def __amiya_loop(self):

        last_talk = time.time()

        while True:
            await asyncio.sleep(5)

            try:

                should_talk = False
                no_word_limit = False
                message_in_conversation = self.storage.message_after(last_talk)

                # self.bot.debug_log(f'should_talk check {len(message_in_conversation)}')

                # 下面列出了所有兔兔可能会回复的条件:

                # 在有话题的情况下，命中reply_check，这个是用来控制对话中消息频率的
                if self.storage.topic is not None:
                    
                    if self.storage.topic != self.amiya_topic:
                        self.interest = float(self.get_handler_config('interest_initial',1000.0))
                        self.bot.debug_log(f'话题改变 {self.amiya_topic} -> {self.storage.topic} interest重置:{self.interest}')
                        self.amiya_topic = self.storage.topic
        
                    # f_str = [f"{context.nickname}: {context.text} ({context.timestamp})\n"  for context in self.storage.recent_messages[-5:]]
                    # self.bot.debug_log(f'Last 5: {f_str}')

                    if next(self.reply_check):                        
                        # 最少要间隔 inerval_factor 条消息，不可以连续说话
                        inerval_factor = self.generate_minimum_message_interval(20)
                        if not any(msg.user_id == ChatGPTMessageContext.AMIYA_USER_ID for msg in self.storage.recent_messages[-inerval_factor:]):
                            should_talk = True
                        else:
                            self.bot.debug_log(f'未够 {inerval_factor} 条消息，阻止发话，interest + 5')
                            # 未命中加5，防止一堆人就这一个话题讨论一天，兔兔一直不插话
                            self.interest = self.interest + 5
                
                # 最近的消息里有未处理的quote或者prefix
                if any(obj.is_prefix or obj.is_quote for obj in message_in_conversation):
                    self.bot.debug_log(f'有Quote/Prefix，强制发话')
                    should_talk = True
                    no_word_limit = True

                if should_talk:
                    last_talk = time.time()

                    await self.ask_amiya(message_in_conversation,no_word_limit)

            except Exception as e:
                self.bot.debug_log(f'Unknown Error {e}')


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
                # 如果拼接后的长度还没有超过max_chars个字符，就继续拼接
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
    async def ask_amiya(self, context_list: List[ChatGPTMessageContext],no_word_limit:bool=False) -> str:
        max_prompt_chars = 1000
        max_chatgpt_chars = 4000
        distinguish_doc = False

        if self.bot.get_config("model",self.channel_id) == "gpt-4":
            max_chatgpt_chars = 8000
            distinguish_doc = True

        _,result,_ = self.pick_prompt(context_list,max_prompt_chars,distinguish_doc)

        command = self.load_template('amiya-template-v1.txt')

        command = command.replace("<<QUERY>>", result)

        command = command.replace("<<Topic>>", self.amiya_topic)

        max_prompt_chars = max_chatgpt_chars-len(command)

        if no_word_limit:
            word_limit_count = 1000
        else:
            # 字数 最长是用户平均发言的2倍，方差1倍，高斯分布控制
            filtered_context_list = [context for context in context_list if context.user_id != ChatGPTMessageContext.AMIYA_USER_ID]
            total_length = sum(len(context.text) for context in filtered_context_list)
            average_length = total_length / len(filtered_context_list)
            word_limit_count = int(random.gauss(average_length * 2, average_length))
        
        command = command.replace("<<WordCount>>", f'{word_limit_count}')

        self.bot.debug_log(f'加入最多{max_prompt_chars}字的memory，WordCount是{word_limit_count}/{average_length}')

        # 五分钟内的所有内容
        memory_in_time = self.storage.message_after(time.time()- 5 * 60)
        # 最近20条对话
        memory_in_count = self.storage.recent_messages[-20:]
        # 二者拼一起作为Memory
        memory = list(set(memory_in_time).union(set(memory_in_count)))

        _,memory_str,_ = self.pick_prompt(memory,max_prompt_chars,distinguish_doc)

        command = command.replace("<<MEMORY>>", memory_str)

        success , message_send, content_factor = await self.get_amiya_response(command, self.channel_id)

        interest_decrease = random.randint(50, 100)

        time_factor = None
        for previou_msg in reversed(self.storage.recent_messages):
            if previou_msg.user_id == ChatGPTMessageContext.AMIYA_USER_ID:
                time_factor = previou_msg.timestamp

        for amiya_context in message_send:
            interest_factor = calculate_timestamp_factor(time_factor,amiya_context.timestamp)

            self.interest = self.interest - interest_decrease * interest_factor * content_factor
            self.bot.debug_log(f'当前兴趣: {self.interest} 增减值: - {interest_decrease} * {interest_factor} * {content_factor}')

            if self.interest <0 :
                self.bot.debug_log(f'兴趣耗尽')                 
            
            self.storage.recent_messages.append(amiya_context)

        return True

    async def get_amiya_response(self, command: str, channel_id: str) -> Tuple[bool, List[ChatGPTMessageContext],float]:

        if self.bot.get_config("model",self.channel_id) == "gpt-4":
            max_retries = 1
        else:
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

                        corelation_on_topic = float(json_obj.get('corelation_on_topic', 0.8))
                        corelation_on_conversation = float(json_obj.get('corelation_on_conversation', 0.8))

                        temp_interest_factor =  scale_to_reverse_exponential(
                            corelation_on_topic, 1, 5, 0, 0.8) * scale_to_reverse_exponential(corelation_on_conversation, 1, 5, 0, 0.8)

                        if temp_interest_factor > interest_factor:
                            interest_factor = temp_interest_factor

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

    # 发送消息到指定频道
    async def send_message(self, message: str):
        if message is None:
            return

        debug_info =  f'{{Topic:"{self.amiya_topic}",Interest:{self.interest}}}'

        self.bot.debug_log(f'show_log_in_chat:{self.get_handler_config("show_log_in_chat")}')

        if self.get_handler_config("show_log_in_chat"):
            message = f"{debug_info}\n{message}"

        messageChain = Chain().text(f'{message}')

        if self.get_handler_config("silent_mode"):
            return

        await self.instance.send_message(messageChain,channel_id=self.channel_id)

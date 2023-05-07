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

    async def __amiya_loop(self):

        last_talk = time.time()

        while True:
            await asyncio.sleep(5)

            try:

                should_talk = False
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

                    # 最少要间隔十条消息，不可以连续说话
                    if not any(msg.user_id == ChatGPTMessageContext.AMIYA_USER_ID for msg in self.storage.recent_messages[-10:]):
                        if next(self.reply_check):
                            should_talk = True
                        else:
                            # 未命中加5，防止一堆人就这一个话题讨论一天，兔兔一直不插话
                            self.interest = self.interest + 5
                
                # 最近的消息里有未处理的quote或者prefix
                if any(obj.is_prefix or obj.is_quote for obj in message_in_conversation):
                    should_talk = True

                if should_talk:
                    last_talk = time.time()

                    await self.ask_amiya(message_in_conversation)

            except Exception as e:
                # 如果重试次数用完仍然没有成功，返回错误信息
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
    async def ask_amiya(self, context_list: List[ChatGPTMessageContext]) -> str:
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
        self.bot.debug_log(f'加入最多{max_prompt_chars}字的memory')

        # 字数 最长是用户发言的四倍，方差2倍，高斯分布控制
        filtered_context_list = [context for context in context_list if context.user_id != ChatGPTMessageContext.AMIYA_USER_ID]
        longest_context = max(filtered_context_list, key=lambda context: len(context.text))
        max_word_length = len(longest_context.text)
        word_limit = int(random.gauss(max_word_length*4, max_word_length*2))
        
        command = command.replace("<<WordCount>>", f'{word_limit}')

        # 五分钟内的所有内容
        memory_in_time = self.storage.message_after(time.time()- 5 * 60)
        # 最近20条对话
        memory_in_count = self.storage.recent_messages[-20:]

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
            self.bot.debug_log(f'兴趣变化{self.interest} -= {interest_decrease} * {interest_factor} * {content_factor}')

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

                        corelation_on_topic = json_obj.get('corelation_on_topic', 0.8)
                        corelation_on_conversation = json_obj.get('corelation_on_conversation', 0.8)

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

    # 发送消息到指定频道
    async def send_message(self, message: str):
        if message is None:
            return

        debug_info =  f'{{Topic:"{self.amiya_topic}",Interest:{self.interest}}}'

        self.bot.debug_log(f'show_log_in_chat:{self.get_handler_config("show_log_in_chat")}')

        if self.get_handler_config("show_log_in_chat"):
            message = f"{debug_info}\n{message}"

        messageChain = Chain().text(f'{message}')
        await self.instance.send_message(messageChain,channel_id=self.channel_id)

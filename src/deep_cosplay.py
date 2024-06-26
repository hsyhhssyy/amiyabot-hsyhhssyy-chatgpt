import json
import time
import random
import asyncio
import os
import re
import requests
import time
import traceback

from peewee import DoesNotExist,fn

from typing import Dict, List, Tuple

from datetime import datetime

from amiyabot import Message, Chain

from core import bot as main_bot
from core.resource.arknightsGameData import ArknightsGameData, ArknightsGameDataResource

from .core.developer_types import BLMAdapter
from .core.chatgpt_plugin_instance import ChatGPTPluginInstance,ChatGPTMessageHandler
from .core.message_context import ChatGPTMessageContext
from .core.chat_log_storage import ChatLogStorage

from .core.trpg_storage import AmiyaBotChatGPTParamHistory,AmiyaBotChatGPTExecutionLog

from .util.datetime_operation import calculate_timestamp_factor
from .util.complex_math import scale_to_reverse_exponential

storage_team_name = "deep-cosplay"

template_filename = "deep-cosplay/amiya-template-v6.1.txt"
topic_template_filename = "deep-cosplay/topic-template-v1.1.txt"

curr_dir = os.path.dirname(__file__)
dir_path = f"{curr_dir}/../../../resource/blm_library/img_cache"

class DeepCosplay(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, blm_lib:BLMAdapter, channel_id: int,instance) -> None:
        super().__init__(bot, blm_lib, channel_id, "deep_cosplay_mode_config",instance)

        self.storage = ChatLogStorage(bot,blm_lib,self.channel_id)

        use_topic = self.get_handler_config('use_topic',False)
        if not use_topic:
            self.storage.eps=0

        self.amiya_topic = ""
        self.assistant_thread = None
        self.interest : float = 0

        self.reply_check = self.__reply_check_gen()

        asyncio.create_task(self.__amiya_loop())

    ERROR_REPLY = '抱歉博士，阿米娅有点不明白。'

    def __reply_check_gen(self):
        last_true_time = time.time()
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
                if self.get_handler_config('use_topic',False) and self.storage.topic is None:
                    probability = probability * 0.5
                            
                # 如果当前兴趣丢失，则概率归零，但是每过30分钟加0.1，最高0.5
                if self.interest <= 0:
                    probability = 0 + (time_elapsed / 1800) * 0.1
                    if probability > 0.5:
                        probability = 0.5

                rand_value = random.random()

                self.debug_log(f'{time_elapsed:.2f}/{mean_time:.2f} 秒间隔后的说话概率 : {rand_value} < {probability} ?')
                    
                if rand_value < probability:
                    last_true_time = current_time
                    yield True
                else:
                    yield False
            
            except Exception as e:
                # 如果重试次数用完仍然没有成功，返回错误信息
                self.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')



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

        last_talk = time.time() - 60*5

        while True:
            await asyncio.sleep(5)

            try:

                should_talk = False
                no_word_limit = False
                message_in_conversation = self.storage.message_after(last_talk)

                use_topic = self.get_handler_config('use_topic',False)
                if not use_topic:
                    self.storage.eps=0

                # self.debug_log(f'should_talk check {len(message_in_conversation)}')

                # 下面列出了所有兔兔可能会回复的条件:

                # 在有话题的情况下，命中reply_check，这个是用来控制对话中消息频率的
                if self.storage.topic != self.amiya_topic:
                    if self.storage.topic == ChatLogStorage.NoTopic:
                        self.interest = 0
                        self.debug_log(f'话题改变 {self.amiya_topic} -> {self.storage.topic} interest drop to 0')
                    else:
                        self.interest = float(self.get_handler_config('interest_initial',1000.0))
                        self.debug_log(f'话题改变 {self.amiya_topic} -> {self.storage.topic} interest重置:{self.interest}')
                    self.amiya_topic = self.storage.topic

                # 如果不使用话题，或者话题不为空，且不是NoTopic
                if not use_topic or (self.storage.topic is not None and self.storage.topic != ChatLogStorage.NoTopic):
                    # f_str = [f"{context.nickname}: {context.text} ({context.timestamp})\n"  for context in self.storage.recent_messages[-5:]]
                    # self.debug_log(f'Last 5: {f_str}')

                    if next(self.reply_check):                        
                        # 最少要间隔 inerval_factor 条消息，不可以连续说话
                        inerval_factor = self.generate_minimum_message_interval(20)
                        if not any(msg.user_id == ChatGPTMessageContext.AMIYA_USER_ID for msg in self.storage.recent_messages[-inerval_factor:]):
                            should_talk = True
                        else:
                            self.debug_log(f'未够 {inerval_factor} 条消息，阻止发话，interest + 5')
                            # 未命中加5，防止一堆人就这一个话题讨论一天，兔兔一直不插话
                            self.interest = self.interest + 5



                # 最近的消息里有未处理的quote或者prefix
                if any(obj.is_prefix or obj.is_quote for obj in message_in_conversation):
                    self.debug_log(f'有Quote/Prefix，强制发话,并切换话题为{self.amiya_topic}')
                    self.amiya_topic = self.storage.topic
                    should_talk = True
                    no_word_limit = True

                    if self.interest <= 0:
                        self.interest = float(self.get_handler_config('interest_initial',1000.0))

                if should_talk:
                    last_talk = time.time()
                    
                    self.amiya_topic = self.storage.topic

                    if self.get_handler_config('use_assistant',False):
                        await self.ask_amiya_with_assistant(message_in_conversation)
                    else:
                        await self.ask_amiya_with_model(message_in_conversation,no_word_limit)

            except Exception as e:
                self.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')

    async def merge_operator_detail(self,opt):

        detail_text = ""

        detail_text += "技力每秒恢复1点\n"

        stories = opt.stories()
        real_name = await ArknightsGameData.get_real_name(opt.origin_name)
        detail_text += f'干员代号:{opt.name} 干员真名:{real_name}\n'
        
        race_match = re.search(r'【种族】(.*?)\n', next(story["story_text"] for story in stories if story["story_title"] == "基础档案"))
        if race_match:
            race = race_match.group(1)
        else:
            race = "未知"
        detail_text = detail_text + f'职业:{opt.type} 种族:{race}\n'


        detail_text += next(story["story_text"]+"\n" for story in stories if story["story_title"] == "客观履历")

        opt_detail = opt.detail()[0]

        detail_text += f'最大生命:{opt_detail["maxHp"]} 攻击力:{opt_detail["atk"]} 防御力:{opt_detail["def"]} 法术抗性:{opt_detail["magicResistance"]}% 攻击间隔:{opt_detail["baseAttackTime"]}秒\n'

        detail_text +=f'干员特性:{opt_detail["operator_trait"]}\n'

        talents = opt.talents()

        talent_txt=""
        for i, talent in enumerate(talents, start=1):
            talent_name = talent["talents_name"]
            talent_desc = talent["talents_desc"]
            talent_txt += f"{i}天赋-{talent_name}:{talent_desc}"
            if i < len(talents):
                talent_txt += "。 "

        detail_text += f"{talent_txt}\n"

        skills, skills_id, skills_cost, skills_desc = opt.skills()

        for i in range(1, 4):
            matching_skill = next((skill for skill in skills if skill["skill_index"] == i), None)
            
            skill_txt = ""

            if matching_skill:
                skill_txt=f"{i}技能:"
                skill_txt = f"{matching_skill['skill_name']} "

                skill_desc = skills_desc[matching_skill['skill_no']]

                best_level = max([desc['skill_level'] for desc in skill_desc])
                best_desc = next((desc for desc in skill_desc if desc['skill_level'] == best_level), None)

                desc_text = re.sub(r'\[cl (.*?)@#.*? cle\]', lambda x: x.group(1), best_desc['description'])

                skill_txt+=f"初始技力:{best_desc['sp_init']} 技力消耗:{best_desc['sp_cost']} 持续时间:{best_desc['duration']} {desc_text}"
                
                skill_txt+="\n"
            
            detail_text += skill_txt

        detail_text += "\n"

        return detail_text

    async def get_template(self, template_key,template_filename):
        param_name = f"TEMPLATE-{template_key}"
        
        param_value = AmiyaBotChatGPTParamHistory.get_param(param_name,storage_team_name)

        if param_value is None:
            # 不存在该模板，从磁盘写入并返回
            with open(f'{curr_dir}/../templates/{template_filename}', 'r', encoding='utf-8') as file:
                template = file.read()
                AmiyaBotChatGPTParamHistory.set_param(param_name,template,storage_team_name)
                return template
        else:
            return param_value

    # 根据一大堆话生成一个回复
    async def ask_amiya_with_model(self, context_list: List[ChatGPTMessageContext],no_word_limit:bool) -> bool:

        model_name = self.bot.get_model_in_config('high_cost_model_name',self.channel_id)
        model = self.blm_lib.get_model(model_name)

        speech_data = {}

        # context_list倒着查看,找到第一条阿米娅的消息,然后截断为Query和Memory
        query_context = None
        for context in reversed(context_list):
            if context.user_id == ChatGPTMessageContext.AMIYA_USER_ID:
                query_context = context
                break
        
        if query_context is None:
            query_context_index = 0
        else:
            query_context_index = context_list.index(query_context) + 1
            query_context_index = min(query_context_index, len(context_list))

        self.debug_log(f'query_context_index: {query_context_index}')

        query_context_list = context_list[query_context_index:]
        memory_context_list = context_list[:query_context_index]


        if self.bot.get_config('vision_enabled', self.channel_id) == True:
            self.debug_log(f'vision_enabled')

            # 输出所有的image_url
            for context in query_context_list:
                self.debug_log(f'context.image_url: {context.image_url}')

            # 判断context_list中是否有图片，如果有图片，切换为使用视觉模型
            if any(len(context.image_url)>0 for context in query_context_list):
                self.debug_log(f'检测到图片，切换为使用视觉模型')
                vision_model_name = self.bot.get_model_in_config('vision_model_name',self.channel_id)
                vision_model_info = self.blm_lib.get_model(vision_model_name)
                if vision_model_info is not None:
                    model = vision_model_info
                    model_name = vision_model_name
                    self.debug_log(f'切换为使用视觉模型: {vision_model_name}')
        
        self.debug_log(f'使用模型: {model}')

        max_chatgpt_chars = model["max_token"]
        max_prompt_chars = max_chatgpt_chars / 3

        # 如果用户的性能型模型设置的确实是高性能模型，那就设置为分辨博士名称。
        distinguish_doc = False
        if model["type"] == "high-cost":
            distinguish_doc = True 

        _,doctor_talks,picked_context = ChatGPTMessageContext.pick_prompt(query_context_list,max_prompt_chars,distinguish_doc)

        images = []
        for context in picked_context:
            images = images + context.image_url

        # if(model == "gpt-4"):
        # template_filename = "deep-cosplay/amiya-template-v6.txt"
        # topic_template_filename = "deep-cosplay/topic-template-v1.txt"
        # else:
        #     template_filename = "amiya-template-v2.txt"

        self.debug_log(f'template select: {model} {template_filename}')

        command_template = await self.get_template(template_filename,template_filename)

        command = command_template

        command = command.replace("<<QUERY>>", doctor_talks)
        speech_data["QUERY"]=doctor_talks

        topic_command = await self.get_template(topic_template_filename,topic_template_filename)
        
        if self.amiya_topic is None or self.amiya_topic == ChatLogStorage.NoTopic:
            topic_command = ""
        else:
            topic_command = topic_command.replace("<<TOPIC>>", self.amiya_topic)

        command = command.replace("<<TOPIC>>", topic_command)
        speech_data["TOPIC"]=topic_command

        max_prompt_chars = max_chatgpt_chars-len(command)

        word_limit_count = 100
        average_length = 0
        if not no_word_limit:
            # 字数 最长是用户平均发言的2倍，方差1倍，高斯分布控制
            filtered_context_list = [context for context in context_list if context.user_id != ChatGPTMessageContext.AMIYA_USER_ID]
            total_length = sum(len(context.text) for context in filtered_context_list)
            if len(filtered_context_list)>0:
                average_length = total_length / len(filtered_context_list)
                word_limit_count = int(random.gauss(average_length*4, average_length))
        
            if word_limit_count<10:
                word_limit_count = 10

            if word_limit_count > 100:
                word_limit_count = 100

            command = command.replace("<<WORD_COUNT>>", f'你的回答中所有句子的字数应该限制在{word_limit_count}字以内。')
            speech_data["WORD_COUNT"]=f'你的回答中所有句子的字数应该限制在{word_limit_count}字以内。'
        else:
            command = command.replace("<<WORD_COUNT>>", f'')
            speech_data["WORD_COUNT"]=f''

        self.debug_log(f'加入最多{max_prompt_chars}字的memory，WordCount是{word_limit_count}/{average_length}')

        # # 拼入干员的客观履历
        # operator_detail = ""

        # # 在日志里给下面这一小段代码加一个时间记录，看看执行了多久，单位ms

        # operatorConcatStartTime = time.time()

        # for name,operator in ArknightsGameData.operators.items():
        #     if len(name) > 1:
        #         # 不拼入单字干员，免得经常突然提及，尤其是年，阿，令
        #         # if picked_context中的任何一个Item.text含有name
        #         if any( (name in context.text and context.user_id != ChatGPTMessageContext.AMIYA_USER_ID ) for context in picked_context):
        #             operator_detail += '\n' +  await self.merge_operator_detail(operator)

        # self.debug_log(f'干员详情拼接耗时: {(time.time() - operatorConcatStartTime)*1000:.2f}ms')

        # operator_template = ""
        # if operator_detail is not None and operator_detail != "":
        #     with open(f'{curr_dir}/../templates/deep-cosplay/operator-data-template-v1.txt', 'r', encoding='utf-8') as file:
        #         operator_template = file.read()
        #         operator_template = operator_template.replace("<<OPERATOR_DETAIL>>", f'{operator_detail}')

        # command = command.replace("<<OPERATOR_DETAIL>>", f'{operator_template}')
        # speech_data["OPERATOR_DETAIL"]=f'{operator_template}'

        # 五分钟内的所有内容 + memory_context_list + 最近20条对话 拼一起作为Memory
        memory_in_time = self.storage.message_after(time.time()- 5 * 60)
        memory_in_count = self.storage.recent_messages[-20:]
        memory = list(set(memory_in_time).union(set(memory_in_count)).union(set(memory_context_list)))

        # 排除重复并按照时间排序
        memory = sorted(list(set(memory)),key=lambda x:x.timestamp)

        # 剔除用在Query里的内容
        memory = [context for context in memory if context not in query_context_list]

        _,memory_str,_ = ChatGPTMessageContext.pick_prompt(memory,max_prompt_chars,distinguish_doc)

        command = command.replace("<<MEMORY>>", memory_str)
        speech_data["MEMORY"]=memory_str

        try:
            success , message_send, content_factor, raw_response = await self.get_amiya_response(command,images, self.channel_id,model)
        except Exception as e:
            self.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')
            return False

        AmiyaBotChatGPTExecutionLog.create(
                team_uuid=storage_team_name,
                channel_id=self.channel_id,
                channel_name="",
                template_name="amiya-template-v4",
                template_value=command_template,
                model=model_name,
                data=json.dumps(speech_data),
                raw_request=command,
                raw_response=raw_response,
                create_at=datetime.now()
            )

        interest_decrease = random.randint(50, 100)

        time_factor = None
        for previou_msg in reversed(self.storage.recent_messages):
            if previou_msg.user_id == ChatGPTMessageContext.AMIYA_USER_ID:
                time_factor = previou_msg.timestamp

        for amiya_context in message_send:
            interest_factor = calculate_timestamp_factor(time_factor,amiya_context.timestamp)

            self.interest = self.interest - interest_decrease * interest_factor * content_factor
            self.debug_log(f'当前兴趣: {self.interest} 增减值: - {interest_decrease} * {interest_factor} * {content_factor}')

            if self.interest <0 :
                self.debug_log(f'兴趣耗尽')            
            
            self.storage.recent_messages.append(amiya_context)

        return True

    async def get_amiya_response(self, command: str, image:list, channel_id: str,model:dict) -> Tuple[bool, List[ChatGPTMessageContext],float, str]:

        if model is None:
            return False,[],0,""

        if model["type"]=="high-cost":
            max_retries = 1
        else:
            max_retries = 3
        
        retry_count = 0 

        self.debug_log(f'ChatGPT Max Retry: {max_retries}')

        message_send = []

        response = ""
        corelation_on_topic = 0.8
        corelation_on_conversation = 0.8

        interest_factor = 1

        try:
        
            successful_sent = False
            
            while retry_count < max_retries:
                if self.bot.get_config('vision_enabled', self.channel_id) == True:
                    command = [{"type":"text","text":command}]
                    command = command + [{"type":"image_url","url":imgPath} for imgPath in image]

                json_str = await self.blm_lib.chat_flow(
                    prompt=command, model=model["model_name"],
                    channel_id=channel_id,
                    # functions=self.blm_lib.amiyabot_function_calls,
                    json_mode=True
                )

                if json_str:
                    json_objects = json.loads(json_str)
                else:
                    json_objects = []

                response = json_str
                self.debug_log(f'ChatGPT原始回复:{json_objects}')

                words_response = None
                response_with_mental = None

                if not isinstance(json_objects, list):
                    json_objects = [json_objects]

                for json_obj in json_objects:
                    if json_obj.get('role', None) == '阿米娅':
                        response_type = json_obj.get('type', "text")
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

                        debug_info =  f'{{Topic:"{self.amiya_topic}",Interest:{self.interest},Model:{model}}}'
                        if self.get_handler_config("show_log_in_chat"):
                            response_with_mental = f"{debug_info}\n{response_with_mental}"

                        if response_type == "text":
                            self.debug_log(f'ChatGPT Text回复:{words_response}')
                            await self.send_message(response_with_mental)
                        elif response_type == "image_url":
                            self.debug_log(f'ChatGPT Image回复:{words_response}')
                            await self.send_image(words_response)

                        message_send.append(amiya_context)
                        successful_sent = True

                        if self.get_handler_config('output_activity', False) == True:
                            activity = json_obj.get('activity', None)
                            if activity is not None and activity != "":
                                await self.send_message(f'({activity})')
                        
                        if len(message_send) > 3:
                            if model["type"]!="high-cost":
                                # 有时候， API会发疯一样的返回N多行，这里检测到超过3句话就强制拦截不让他说了
                                # 尤其用3.5的时候更是这样
                                # 因此使用低性能模型时，只允许三句话
                                break

                if successful_sent:
                    break
                else:
                    self.debug_log(f'未读到Json，重试第{retry_count+1}次')
                    retry_count += 1

            if not successful_sent:
                # 如果重试次数用完仍然没有成功，返回错误信息
                return False, message_send,interest_factor,""

        
            if self.get_handler_config("silent_mode"):
                formatted_file_timestamp = time.strftime('%Y%m%d', time.localtime(time.time()))
                sent_file = f'{curr_dir}/../../../resource/chatgpt/{self.channel_id}.{formatted_file_timestamp}.txt'
                with open(sent_file, 'a', encoding='utf-8') as file:
                    file.write('-'*20)
                    file.write('\n')
                    for msg in self.storage.recent_messages[-10:]:
                        formatted_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(msg.timestamp))
                        file.write(f'[{formatted_timestamp}]{msg.nickname}:{msg.text}\n')

                    debug_info =  f'{{Topic:"{self.amiya_topic}",Interest:{self.interest}}}'
                    formatted_current_timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
                    file.write(f'[{formatted_current_timestamp}]{debug_info}\n')
                    for msg in message_send:
                        file.write(f'[{formatted_current_timestamp}]阿米娅(我):{msg.text}\n')

        except Exception as e:
            self.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')
            return False, message_send,interest_factor,""
        

        return True, message_send,interest_factor,response

    async def ask_amiya_with_assistant(self, context_list: List[ChatGPTMessageContext]) -> bool:
        
        # context_list倒着查看,找到第一条阿米娅的消息,然后截断为Query和Memory
        query_context = None
        for context in reversed(context_list):
            if context.user_id == ChatGPTMessageContext.AMIYA_USER_ID:
                query_context = context
                break
        
        if query_context is None:
            query_context_index = 0
        else:
            query_context_index = context_list.index(query_context) + 1
            query_context_index = min(query_context_index, len(context_list))

        self.debug_log(f'query_context_index: {query_context_index}')

        query_context_list = context_list[query_context_index:]
        # memory_context_list = context_list[:query_context_index]


        if self.bot.get_config('vision_enabled', self.channel_id) == True:
            self.debug_log(f'vision_enabled')

            # 输出所有的image_url
            for context in query_context_list:
                self.debug_log(f'context.image_url: {context.image_url}')

        try:
            content_factor, amiya_contexts = await self.get_amiya_assistant_response(query_context_list, self.channel_id)
        except Exception as e:
            self.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')
            return False

        if amiya_contexts:

            for amiya_context in amiya_contexts:

                interest_decrease = random.randint(50, 100)

                time_factor = None
                for previou_msg in reversed(self.storage.recent_messages):
                    if previou_msg.user_id == ChatGPTMessageContext.AMIYA_USER_ID:
                        time_factor = previou_msg.timestamp

                interest_factor = calculate_timestamp_factor(time_factor,amiya_context.timestamp)

                self.interest = self.interest - interest_decrease * interest_factor * content_factor
                self.debug_log(f'当前兴趣: {self.interest} 增减值: - {interest_decrease} * {interest_factor} * {content_factor}')

                if self.interest <0 :
                    self.debug_log(f'兴趣耗尽')
                    self.assistant_thread=None

                self.storage.recent_messages.append(amiya_context)

        return True

    async def get_amiya_assistant_response(self, context_list: List[ChatGPTMessageContext], channel_id: str):

        assistant_id = self.bot.get_config('assistant_id',self.channel_id)

        if not assistant_id:
            self.debug_log(f"Assistant ID not found! channel_id: {self.channel_id}")
            return None,None
        
        # 处理一下assistant_id, 配置文件里 是 name[id] 的形式
        assistant_id = assistant_id.split("[")[1].split("]")[0]

        # 拼接消息
        content = []

        for context in context_list:
            content.append({
                "role": "user",
                "type":"text",
                "text": context.nickname + "博士:" + context.text
            })

            if context.image_url:
                content.append({
                    "role": "user",
                    "type":"image_url",
                    "url": context.image_url
                })

        # 检查Conversation
        if self.assistant_thread != None:
            ret = await self.blm_lib.assistant_thread_touch(self.assistant_thread,assistant_id)
            if not ret:
                # 失效了
                self.debug_log(f"Assistant Thread Touch Failed! channel_id: {self.channel_id} thread_id: {self.assistant_thread} {ret}!")
                self.assistant_thread = None
        
        if self.assistant_thread == None:
            ret = await self.blm_lib.assistant_thread_create(assistant_id)
            if ret:
                self.assistant_thread = ret
                self.debug_log(f"Assistant Thread Create Success! channel_id: {self.channel_id} thread_id: {self.assistant_thread}")
        
        if not self.assistant_thread:
            self.debug_log(f"Assistant Thread Create Failed! channel_id: {self.channel_id}")
            return

        corelation_on_topic = 0.8
        corelation_on_conversation = 0.8

        interest_factor = 1

        try:
            json_str = await self.blm_lib.assistant_run(
                thread_id=self.assistant_thread,
                assistant_id=assistant_id,
                messages=content,
                channel_id=channel_id,
                json_mode=True
            )

            if json_str:
                json_objects = json.loads(json_str)
            else:
                json_objects = []

            response = json_str
            self.debug_log(f'Assistant原始回复:{json_objects}')

            words_response = None
            response_with_mental = None

            if not isinstance(json_objects, list):
                json_objects = [json_objects]

            amiya_contexts = []

            for json_obj in json_objects:
                if json_obj.get('role', None) == '阿米娅':
                    response_type = json_obj.get('type', "text")
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
                    
                    if not self.get_handler_config("use_topic", False):
                        interest_factor = interest_factor / 10

                    amiya_context = ChatGPTMessageContext(words_response, '阿米娅')
                    amiya_contexts.append(amiya_context)

                    if response_type == "text":
                        self.debug_log(f'ChatGPT Text回复:{words_response}')
                        await self.send_message(response_with_mental)
                    elif response_type == "image_url":
                        self.debug_log(f'ChatGPT Image回复:{words_response}')
                        await self.send_image(words_response)

                    if self.get_handler_config('output_activity', False) == True:
                        activity = json_obj.get('activity', None)
                        if activity is not None and activity != "":
                            await self.send_message(f'({activity})')
        
            return interest_factor, amiya_contexts
        
        except Exception as e:
            self.debug_log(f'Unknown Error {e} \n {traceback.format_exc()}')
        
        return None,None

    # 发送消息到指定频道
    async def send_message(self, message: str):
        if message is None:
            return

        messageChain = Chain().text(f'{message}')

        if self.get_handler_config("silent_mode"):
            return

        if message == DeepCosplay.ERROR_REPLY:
            return
        
        await self.instance.send_message(messageChain,channel_id=self.channel_id)
    
    async def send_image(self, image_url: str):
        if image_url is None:
            return
        
        try:

            if image_url.startswith('https://res.amiyabot.com/plugins/'):
                # example: https://res.amiyabot.com/plugins/amiyabot-arknights-operator/aff579021e2049b785b3d68c87116374.png
                # 截取里面的plugin id
                plugin_id = image_url.split('/')[4]

                plugin_instance = main_bot.plugins[plugin_id]

                html = plugin_instance.image_to_html_map[image_url]

                messageChain = Chain().html(html["template"],html["data"])
            else:
                response = requests.head(image_url, timeout=2)
                content_type = response.headers.get('Content-Type')
                if content_type and content_type.startswith('image'):
                    # 下载回本地放到dir_path
                    image_name = image_url.split('/')[-1]
                    image_path = f'{dir_path}/{image_name}'
                    if not os.path.exists(dir_path):
                        os.makedirs(dir_path)
                    
                    response = requests.get(image_url, timeoout=20)
                    with open(image_path, 'wb') as file:
                        file.write(response.content)

                    messageChain = Chain().image(image_path)
                else:
                    self.debug_log(f'给出的Url不是有效的互联网图片: {image_url}')
                    return

            if self.get_handler_config("silent_mode"):
                return

            await self.instance.send_message(messageChain,channel_id=self.channel_id)

        except Exception as e:
            self.debug_log(f'发送图片时出现错误: {e} \n {traceback.format_exc()}')
            return

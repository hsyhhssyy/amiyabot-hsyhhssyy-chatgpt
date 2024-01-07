import time
import asyncio
import json
import os
import re
import math
import time
import traceback

from peewee import DoesNotExist,fn

from datetime import datetime

from typing import Any, Dict, List, Tuple

from amiyabot import Message, Chain

from .core.developer_types import BLMAdapter
from .core.chatgpt_plugin_instance import ChatGPTPluginInstance, ChatGPTMessageHandler
from .core.message_context import ChatGPTMessageContext
from .core.chat_log_storage import ChatLogStorage

from .core.trpg_storage import AmiyaBotChatGPTExecutionLog, AmiyaBotChatGPTParamHistory,AmiyaBotChatGPTTRPGSpeechLog

from .util.datetime_operation import calculate_timestamp_factor
from .util.complex_math import scale_to_reverse_exponential

curr_dir = os.path.dirname(__file__)

chat_log_storages = {}


class TRPGMode(ChatGPTMessageHandler):
    def __init__(self, bot: ChatGPTPluginInstance, blm_lib: BLMAdapter, channel_id: int, instance) -> None:
        super().__init__(bot, blm_lib, channel_id, "trpg_mode_config", instance)

        self.storage = ChatLogStorage(bot, blm_lib, self.channel_id, False)
        self.last_process_time = time.time()
        chat_log_storages[channel_id] = self.storage
        self.group_name = ""

        self.team_uuid = "test-team"

        asyncio.create_task(self.__amiya_loop())


    def get_config(self, conf: str):

        if conf is None:
            raise ValueError("Configuration key cannot be None")
        
        record = AmiyaBotChatGPTParamHistory.select().where(
            (AmiyaBotChatGPTParamHistory.param_name == conf) &
            (AmiyaBotChatGPTParamHistory.team_uuid == "test-team")
        ).order_by(AmiyaBotChatGPTParamHistory.create_at.desc()).first()

        conf_value = None
        if record:
            try:
                conf_value = json.loads(record.param_value)            
            except json.JSONDecodeError:
                conf_value = None

        if conf == "pc_name_mapping":
            map_str = conf_value
            if map_str is None:
                return {}            
            return map_str
        
        if conf == "item_info" or conf == "loc_info" or conf == "character_info" or conf == "task_info":
            map_obj = conf_value
            if map_obj is None:
                return []
            converted_list = []
            for item in map_obj:
                try:
                    converted_item = json.loads(item)
                    converted_list.append(converted_item)
                except json.JSONDecodeError:
                    continue
            return converted_list
        if conf == "env_info":
            value = conf_value
            if value is None:
                return []
            else:
                return value
        if conf == "my_id" or conf == "kp_id" or conf == "curr_loc" or conf == "story" or conf == "output_debug":
            return conf_value

    def set_config(self, conf: str, value):
        if conf is None:
            raise ValueError("Configuration key cannot be None")
        if value is None:
            raise ValueError("Configuration value cannot be None")
        
        AmiyaBotChatGPTParamHistory.create(
                        team_uuid="test-team",
                        param_name=conf,
                        param_value=json.dumps(value, ensure_ascii=False),
                        create_at=datetime.now()
                    )

    async def on_message(self, data: Message):

        # 如果这是一个控制命令，则不进行处理
        if await self.check_command(data):
            return

        self.storage.enqueue(data)

        self.group_name = ""

        kp_id = self.get_config("kp_id")
        my_id = self.get_config("my_id")
        user_type = "OtherPC"
        if f'{data.user_id}' == f'{kp_id}':
            user_type = "KP"
        if f'{data.user_id}' == f'{my_id}':
            user_type = "Me(Human)"

        AmiyaBotChatGPTTRPGSpeechLog.create(
            team_uuid="test-team",
            channel_id=data.channel_id,
            channel_name=self.group_name,
            user_id=data.user_id,
            user_type=user_type,
            irrelevant=False,
            data=data.text,
            create_at=datetime.now()
        )

    async def __amiya_loop(self):

        last_talk = time.time()

        while True:
            await asyncio.sleep(5)

            try:

                talks = self.storage.message_after(last_talk)

                if talks is None or len(talks) == 0:
                    continue

                # self.debug_log(f'talks:{talks}')

                response_sent = False

                for message_context in talks:
                    kp_id = self.get_config("kp_id")
                    if f'{message_context.user_id}' == f'{kp_id}' and len(message_context.text) > 50:
                        # kp说了超过50个字的单段话
                        await self.send_message(f'阿米娅正在整理思绪...')
                        await self.response_to_pc()
                        await self.organize_inventory()
                        response_sent = True
                    elif message_context.is_prefix or message_context.is_quote:
                        # 直接呼叫了阿米娅，对其进行响应。
                        await self.send_message(f'阿米娅思考中...')
                        await self.response_to_pc()
                        await self.organize_inventory()
                        response_sent = True

                    if response_sent == True:
                        break

                if response_sent == False:
                    context_list = self.storage.message_after(
                        self.last_process_time)
                    _, doctor_talks, _ = self.pick_prompt(context_list, 4000)
                    if len(doctor_talks) > 1000:
                        # 积压的消息要超字数了，触发一次说话防止丢消息
                        await self.send_message(f'阿米娅好像想要说点什么...')
                        await self.response_to_pc()
                        await self.organize_inventory()
                        response_sent = True

                if response_sent == True:
                    last_talk = talks[-1].timestamp

            except Exception as e:
                last_talk = time.time()
                self.debug_log(
                    f'Unknown Error {e} \n {traceback.format_exc()}')

    def pick_prompt(self, context_list: List[ChatGPTMessageContext], max_chars=4000) -> Tuple[list, str, list]:

        request_obj = []

        picked_context = []
        text_to_append = ""

        # 获得几个naming相关内容
        my_name = '阿米娅'
        pc_mapping = self.get_config("pc_name_mapping")
        kp_id = self.get_config("kp_id")
        my_id = self.get_config("my_id")

        # self.debug_log(f'kpid {kp_id} my_id {my_id} pc {pc_mapping}')

        result = ""
        for i in range(1, len(context_list) + 1):
            context = context_list[-i]
            if context.user_id != ChatGPTMessageContext.AMIYA_USER_ID:
                if f'{context.user_id}' == f'{kp_id}':
                    text_to_append = f'{context.text}'
                elif f'{context.user_id}' == f'{my_id}':
                    text_to_append = f'{my_name}:{context.text}'
                elif f'{context.user_id}' in pc_mapping.keys():
                    text_to_append = f'{pc_mapping[f"{context.user_id}"]}:{context.text}'
            else:
                text_to_append = f'{my_name}:{context.text}'
            if len(result) + len(text_to_append) + 1 <= max_chars:
                # 如果拼接后的长度还没有超过max_chars个字符，就继续拼接
                result = text_to_append + "\n" + result
                if context.user_id != 0:
                    request_obj.append(
                        {"role": "user", "content": context.text})
                else:
                    request_obj.append(
                        {"role": "assistant", "content": context.text})
                picked_context.append(context)
            else:
                break
        request_obj.reverse()
        picked_context.reverse()
        return request_obj, result, picked_context

    async def check_command(self, data):
        # 使用正则表达式匹配 "(@XXXX)设置PC名称巨神兵" 这种格式的消息
        match = re.search(r"设置PC名称(.+)", data.text)
        if match:
            if data.at_target is not None and len(data.at_target) >= 1:
                qq = data.at_target[0]
                pc_name = match.group(1).strip()  # 提取PC名称
                mapping = self.get_config("pc_name_mapping")  # 获取当前的映射

                if not mapping:
                    mapping = {}  # 如果还没有映射，就创建一个新的字典

                mapping[qq] = pc_name  # 设置新的映射
                self.set_config("pc_name_mapping", mapping)  # 更新配置

                await self.send_message(f'已将{qq}的团内名称设置为{match.group(1).strip()}')

                return True

        # 使用正则表达式匹配 "(@XXXX)设置PC名称巨神兵" 这种格式的消息
        match = re.search(r"设置KP", data.text)
        if match:
            if data.at_target is not None and len(data.at_target) >= 1:
                qq = data.at_target[0]

                self.set_config("kp_id", qq)

                await self.send_message(f'已将{qq}设置为本团KP')

                return True

        match = re.search(r"设置我为代理用户", data.text)
        if match:
            qq = data.user_id

            self.set_config("my_id", qq)

            await self.send_message(f'已将{qq}设置为代理用户')

            return True

        return False

    async def get_template(self, template_key,template_filename):
        param_name = f"TEMPLATE-{template_key}"
        
        param_value = AmiyaBotChatGPTParamHistory.get_param(param_name,self.team_uuid)

        if param_value is None:
            # 不存在该模板，从磁盘写入并返回
            if not os.path.exists(f'{curr_dir}/../templates/{template_filename}'):
                raise ValueError(
                    f"Template file {template_filename} does not exist")
            with open(f'{curr_dir}/../templates/{template_filename}', 'r', encoding='utf-8') as file:
                template = file.read()
                self.bot.debug_log(f'Writing template:\n{template}')
                AmiyaBotChatGPTParamHistory.set_param(param_name,template,self.team_uuid)
                return template
        else:
            # self.bot.debug_log(f'Reading template:\n{param_value}')
            return param_value
        
    async def generate_prompt_shard(self) -> Dict[str, str]:

        prompt_shards: Dict[str, str] = {}

        context_list = self.storage.message_after(self.last_process_time)
        self.last_process_time = time.time()

        self.debug_log(f'{context_list}')

        _, doctor_talks, _ = self.pick_prompt(context_list)

        prompt_shards["CONVERSATION"] = doctor_talks

        curr_loc = self.get_config('curr_loc')
        if curr_loc is None:
            curr_loc = "未知地点"
        prompt_shards["CURRENT_LOCATION"] = curr_loc

        loc_info = self.get_config('loc_info')
        prompt_shards["LOCATION"] = json.dumps(
            loc_info, ensure_ascii=False)

        prompt_shards["LOCATION_NAME"] = ",".join(
            [item["名称"] for item in loc_info if "名称" in item])

        item_info = self.get_config('item_info')
        prompt_shards["INVENTORY"] = json.dumps(
            item_info, ensure_ascii=False)

        prompt_shards["INVENTORY_ITEM_NAME"] = ",".join(
            [item["名称"] for item in item_info if "名称" in item])

        inventory_quantity = [{"名称": item.get("名称"), "数量": item.get("数量"), "单位": item.get(
            "单位")} for item in item_info if "名称" in item and "数量" in item and "单位" in item]
        prompt_shards["INVENTORY_QUANTITY"] = json.dumps(
            inventory_quantity, ensure_ascii=False)

        env_info = self.get_config('env_info')
        prompt_shards["INFORMATION"] = "\n".join(env_info)


        task_info = self.get_config('task_info')
        prompt_shards["TASK"] = json.dumps(
            task_info, ensure_ascii=False)

        chara_info = self.get_config('character_info')
        prompt_shards["CHARACTER"] = json.dumps(
            chara_info, ensure_ascii=False)
        prompt_shards["CHARACTER_NAME"] = ",".join(
            [item["名称"] for item in chara_info if "名称" in item])
        
        story = self.get_config('story')
        prompt_shards["STORY"] = story

        return prompt_shards

    async def format_template(self, template_key: str, template_file: str, shard: Dict[str, str]):
        template_value = await self.get_template(template_key, template_file)

        command = template_value

        for key, val in shard.items():
            if val is None:
                val = ""
            command = command.replace(f'<<{key}>>', val)

        return command, template_value

    async def response_to_pc(self):

        prompt_shards = await self.generate_prompt_shard()
        command,template_value = await self.format_template("trpg-talk-v0","trpg-templates/amiya-trpg-v0.txt", prompt_shards)

        high_cost_model_name = self.bot.get_model_in_config('high_cost_model_name',self.channel_id)

        self.debug_log(f'model:{high_cost_model_name}')

        json_str = await self.blm_lib.chat_flow(
            prompt=command,
                                                             model=high_cost_model_name,
                                                             channel_id=self.channel_id,
                                                             json_mode=True)

        if not json_str:
            return
        
        json_objects = json.loads(json_str)

        if isinstance(json_objects, list) and len(json_objects) > 0:
            amiya_reply = next((json_obj for json_obj in json_objects if json_obj.get(
            'role', None) == '阿米娅'), None)
        else:
            amiya_reply = json_objects
        
        replies = amiya_reply.get('replys', [])

        for reply in replies:
            await self.send_message(f'{reply}')
            amiya_context = ChatGPTMessageContext(reply, '阿米娅')
            self.storage.recent_messages.append(amiya_context)
            
            AmiyaBotChatGPTTRPGSpeechLog.create(
                team_uuid=self.team_uuid,
                channel_id=self.channel_id,
                channel_name=self.group_name,
                user_id="0",
                user_type="Me(Bot)",
                irrelevant=False,
                data=f'{reply}',
                create_at=datetime.now()
            )
            
        AmiyaBotChatGPTExecutionLog.create(
                team_uuid=self.team_uuid,
                channel_id=self.channel_id,
                channel_name="",
                template_name="trpg-talk-v0",
                template_value=template_value,
                model=high_cost_model_name,
                data=json.dumps(prompt_shards),
                raw_request=command,
                raw_response=json_str,
                create_at=datetime.now()
            )

        # ------------------- 单独用Prompt处理信息 -----------------------

        command,template_value = await self.format_template("trpg-process-info-v0","trpg-templates/amiya-template-trpg-process-info-v0.txt", prompt_shards)

        json_str = await self.blm_lib.chat_flow(
            prompt=command, model=high_cost_model_name, channel_id=self.channel_id,
            json_mode=True)
        
        if not json_str:
            return
        
        AmiyaBotChatGPTExecutionLog.create(
                team_uuid=self.team_uuid,
                channel_id=self.channel_id,
                channel_name="",
                template_name="trpg-process-info-v0",
                template_value=template_value,
                model=high_cost_model_name,
                data=json.dumps(prompt_shards),
                raw_request=command,
                raw_response=json_str,
                create_at=datetime.now()
            )

        json_objects = json.loads(json_str)

        if isinstance(json_objects, list) and len(json_objects) > 0:
            json_object = json_objects[0]
        else:
            json_object = json_objects

        # 更新世界观情报
        env_info = self.get_config('env_info')
        env_info_gain = json_object.get('env_info_gain', None)
        env_info.extend(env_info_gain)

        env_info_remove = json_object.get('env_info_remove', None)
        if env_info_remove is not None:
            for item in env_info_remove:
                if item in env_info:
                    env_info.remove(item)
        self.set_config('env_info', env_info)

        message = ""

        if len(env_info_gain) > 0:
            message = f"新增世界观情报: {','.join(env_info_gain)}"

        if env_info_remove is not None and len(env_info_remove) > 0:
            remove_message = f"移除世界观情报: {','.join(env_info_remove)}"
            message += f"\n{remove_message}"

        if message != "" and self.get_config('output_debug')==True:
            await self.send_message(f'{message}')

        # 更新地点情报
        loc_info = self.get_config('loc_info')
        loc_info_gain = json_object.get("loc_info_gain")

        if loc_info_gain is not None:
            for gain in loc_info_gain:
                name = gain["Name"]
                info = gain["Info"]

                # Check if item already exists in loc_info
                existing_item = next(
                    (item for item in loc_info if item["名称"] == name), None)

                if not existing_item:
                    # Add new item to loc_info
                    existing_item = {
                        "名称": name,
                        "情报": []
                    }
                    loc_info.append(existing_item)

                # Update item quantity
                if info is not None:
                    existing_item["情报"].extend(info)
                    message = f"地点【{name}】新增情报:{','.join(info)}"
                    if self.get_config('output_debug')==True:
                        await self.send_message(f'{message}')
                    

        # 更新当前地点情报

        curr_loc = self.get_config('curr_loc')
        curr_loc_response = json_object.get("curr_loc")

        if curr_loc_response is not None and curr_loc_response != "":
            curr_loc_item = next(
                (item for item in loc_info if item["名称"] == curr_loc_response), None)
            if curr_loc_item is None:
                existing_item = {
                    "名称": curr_loc_response,
                    "情报": []
                }
                loc_info.append(existing_item)

            if curr_loc != curr_loc_response:
                message = f"当前地点变更为【{curr_loc_response}】"
                if self.get_config('output_debug')==True:
                    await self.send_message(f'{message}')
                    self.set_config('curr_loc', curr_loc_response)

        self.set_config('loc_info', loc_info)

        # 更新物品
        item_info = self.get_config('item_info')
        item_exchange = json_object.get("item_exchange")
        itm_info_gain = json_object.get("itm_info_gain")

        if item_exchange is not None:
            message = ""
            for exchange in item_exchange:
                name = exchange["Name"]
                amount = exchange["Amount"]
                unit = exchange["Unit"]

                # Check if item already exists in item_info
                existing_item = next(
                    (item for item in item_info if item["名称"] == name), None)

                if existing_item:
                    # Update item quantity
                    existing_item["数量"] += amount
                    if existing_item["数量"] < 0:
                        existing_item["数量"] = 0
                else:
                    # Add new item to item_info
                    existing_item = {
                        "名称": name,
                        "数量": max(amount, 0),
                        "单位": unit,
                        "情报": []
                    }
                    item_info.append(existing_item)

                message += f"物品【{name}】数量已调整为 {existing_item['数量']} {unit} "
            if message != "" and self.get_config('output_debug')==True:
                await self.send_message(f'{message}')

        # 更新物品信息

        if itm_info_gain is not None:
            message = ""
            for name,_ in itm_info_gain.items():
                item_info_item = next(
                    (item for item in item_info if item["名称"] == name))
                
                if item_info_item is None:
                    item_info_item = {
                        "名称": name,
                        "数量": 0,
                        "单位": "",
                        "情报": []
                    }
                    item_info.append(item_info_item)

                item_info_item["情报"].extend(itm_info_gain[name])
                message += f"物品【{name}】新增情报 {','.join(itm_info_gain[name])} "
            if message != "" and self.get_config('output_debug')==True:
                await self.send_message(f'{message}')

        self.set_config('item_info', item_info)

        # 更新人物信息

        chara_info = self.get_config('character_info')
        chara_info_gain = json_object.get("character_info_gain")

        if chara_info_gain is not None:
            for gain in chara_info_gain:
                name = gain["Name"]
                info = gain["Info"]

                existing_item = next(
                    (item for item in chara_info if item["名称"] == name), None)

                if not existing_item:
                    existing_item = {
                        "名称": name,
                        "情报": []
                    }
                    chara_info.append(existing_item)

                if info is not None:
                    existing_item["情报"].extend(info)
                    message = f"人物【{name}】新增情报:{','.join(info)}"
                    if self.get_config('output_debug')==True:
                        await self.send_message(f'{message}')

        self.set_config('character_info', chara_info)

        # 更新任务信息

        task_info = self.get_config('task_info')
        task_info_gain = json_object.get("task_info_gain")

        if task_info_gain is not None:
            message = ""
            for task_gain in task_info_gain:
                content = task_gain["Content"]
                status = task_gain["Status"]

                existing_item = next(
                    (item for item in task_info if item["内容"] == content), None)

                if existing_item:
                    existing_item["状态"] = status
                else:
                    existing_item = {
                        "内容": content,
                        "状态": status
                    }
                    task_info.append(existing_item)

                message += f"任务【{content}】的状态变为 {status} "
            if message != "" and self.get_config('output_debug')==True:
                await self.send_message(f'{message}')

        self.set_config('task_info', task_info)

        story_info =  json_object.get("story")

        if story_info is not None:
            self.set_config('story', story_info)
            if self.get_config('output_debug')==True:
                await self.send_message(f'当前故事：{story_info}')

    async def organize_inventory(self):
        
       # ------------------- 单独用Prompt整理各项信息的长度 -----------------------

        prompt_shards = await self.generate_prompt_shard()
        env_info = self.get_config('env_info')
        # 整理世界观情报
        if len(env_info) > 30:
            prompt_shards["INFORMATION_COUNT"] = "20"
            command = await self.format_template("trpg-organize-information-v0","trpg-templates/amiya-template-trpg-organize-information-v0.txt", prompt_shards)
            success, json_objects = await self.delegate.ask_chatgpt_with_json(command, self.channel_id, self.get_model_with_quota())

            if success:
                if json_objects is not None and len(json_objects) > 1:
                    json_obj = json_objects[0]

                    if isinstance(json_obj, list) and all(isinstance(item, str) for item in json_obj):                        
                        self.set_config('env_info', json_obj)        


    async def send_message(self,str):
        
        my_id = self.get_config("my_id")

        # await self.instance.send_message(Chain().text(f'{str}'), user_id=my_id)
        await self.instance.send_message(Chain().text(f'{str}'), channel_id=self.channel_id)
import asyncio
import json
import os
import threading
import time
import traceback

from typing import List, Optional, Union

from amiyabot.log import LoggerManager

from core import log
from core import bot as main_bot
from core.plugins.customPluginInstance.requirement import Requirement
from core.util import read_yaml
from core import AmiyaBotPluginInstance
from .message_context import get_quote_id

from .developer_types import BLMAdapter

curr_dir = os.path.dirname(__file__)

logger = LoggerManager('ChatGPT')

class ChatGPTPluginInstance(AmiyaBotPluginInstance):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def install(self):
        config_file = 'resource/plugins/chatGPT/config.yaml'
        if os.path.exists(config_file):
            # 清理旧的配置文件
            yamlConfig = read_yaml(config_file, _dict=True)
            if "api_key" in yamlConfig: self.set_config("api_key", yamlConfig["api_key"],None)
            if "predef_context" in yamlConfig: self.set_config("predef_context", yamlConfig["predef_context"],None)
            if "base_url" in yamlConfig: self.set_config("base_url", yamlConfig["base_url"],None)
            if "proxy" in yamlConfig: self.set_config("proxy", yamlConfig["proxy"],None)
            if "model" in yamlConfig: self.set_config("model", yamlConfig["model"],None)
            if "stop_words" in yamlConfig: self.set_config("stop_words", yamlConfig["stop_words"],None)
            os.remove(config_file)

    def generate_global_schema(self):

        filepath = f'{curr_dir}/../../accessories/global_config_schema.json'

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.debug_log(f"Failed to load JSON from {filepath}.")
            return None
        
        if 'amiyabot-blm-library' in main_bot.plugins.keys():
            blm_lib = main_bot.plugins['amiyabot-blm-library']
            
            if blm_lib is not None:
                model_list = blm_lib.model_list()

                try:     
                    data["properties"]["high_cost_model_name"]["enum"] = [model["model_name"] for model in model_list]
                    data["properties"]["low_cost_model_name"]["enum"] =  [model["model_name"] for model in model_list if model["type"] == "low-cost"]
                    data["properties"]["vision_model_name"]["enum"] =  [model["model_name"] for model in model_list if model["supported_feature"].__contains__("vision")]
                except KeyError as e:
                    stack_trace = traceback.format_exc()
                    self.debug_log(f"Expected keys not found in the JSON structure: {e}\n{stack_trace}")
                
                asistant_list = blm_lib.assistant_list()

                try:
                    data["properties"]["assistant_id"]["enum"] =  [model["name"]+"["+model["id"]+"]" for model in asistant_list]
                except KeyError as e:
                    stack_trace = traceback.format_exc()
                    self.debug_log(f"Expected keys not found in the JSON structure: {e}\n{stack_trace}")


        return data

    def generate_channel_schema(self):
        filepath = f'{curr_dir}/../../accessories/channel_config_schema.json'

        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                data = json.load(file)
        except (FileNotFoundError, json.JSONDecodeError):
            self.debug_log(f"Failed to load JSON from {filepath}.")
            return None
        
        if 'amiyabot-blm-library' in main_bot.plugins.keys():
            blm_lib = main_bot.plugins['amiyabot-blm-library']
            
            if blm_lib is not None:
                model_list = blm_lib.model_list()
            
            try:     
                data["properties"]["high_cost_model_name"]["enum"] = [model["model_name"] for model in model_list] + ["跟随全局..."]
                data["properties"]["low_cost_model_name"]["enum"] =  [model["model_name"] for model in model_list if model["type"] == "low-cost"] + ["跟随全局..."]
                data["properties"]["vision_model_name"]["enum"] =  [model["model_name"] for model in model_list if model["supported_feature"].__contains__("vision")] + ["跟随全局..."]
            except KeyError as e:
                stack_trace = traceback.format_exc()
                self.debug_log(f"Expected keys not found in the JSON structure: {e}\n{stack_trace}")

            asistant_list = blm_lib.assistant_list()

            try:
                data["properties"]["assistant_id"]["enum"] =  [model["name"]+"["+model["id"]+"]" for model in asistant_list] + ["跟随全局..."]
            except KeyError as e:
                stack_trace = traceback.format_exc()
                self.debug_log(f"Expected keys not found in the JSON structure: {e}\n{stack_trace}")

        
        return data

    def load(self):
        ...

    def get_prefix(self):
        return self._prefix_keywords

    def debug_log(self, message):
        show_log = self.get_config("show_log")
        if show_log == True:
            logger.info(f'{message}')

    def get_quote_id(self, data):
        return get_quote_id(data)

    def get_model_in_config(self, model_conf_name:str,channel_id:str):
        model = self.get_config(model_conf_name,channel_id)

        if model == '跟随全局...' or model == None:
            model = self.get_config(model_conf_name)

        return model

quota = 0

def call_limit():
    call_count = 0
    reset_time = time.time() + 3600

    while True:
        current_time = time.time()

        # 检查是否需要重置计数器
        if current_time >= reset_time:
            call_count = 0
            reset_time = current_time + 3600

        # 更新调用次数
        call_count += 1
        
        global quota
        
        if not quota:
            quota = 4

        # 如果调用次数小于等于4，则生成True，否则生成False
        yield True if call_count <= quota else False

call_limit_gen = call_limit()

class ChatGPTMessageHandler():
    def __init__(self, bot:ChatGPTPluginInstance,blm_lib:BLMAdapter, channel_id,handler_conf_key,instance=None) -> None:
        self.bot = bot
        self.blm_lib = blm_lib
        self.channel_id = channel_id
        self.handler_conf_key = handler_conf_key
        self.instance = instance
    
    def debug_log(self, message):
        show_log = self.bot.get_config("show_log")
        if show_log == True:
            logger.info(f'[{self.channel_id:<10}]{message}')

    def get_handler_config(self, configName, default = None):
        handler_conf = self.bot.get_config(self.handler_conf_key,self.channel_id)

        if configName in handler_conf.keys():
            if handler_conf[configName] != "" and handler_conf[configName] != []:
                # self.debug_log(f'[GetConfig]{configName} : {handler_conf[configName]}')
                return handler_conf[configName]
        
        handler_conf = self.bot.get_config(self.handler_conf_key)

        if configName in handler_conf.keys():
            if handler_conf[configName] != "" and handler_conf[configName] != []:
                # self.debug_log(f'[GetConfig]{configName} : {handler_conf[configName]}')
                return handler_conf[configName]
            else:
                return default
        
        # self.debug_log(f'[GetConfig]{configName} : None')
        return default
    
    def set_handler_config(self, configName, configValue, channel_id=None):
        # 获取当前的handler配置
        handler_conf = self.bot.get_config(self.handler_conf_key, self.channel_id)

        # 如果handler配置不存在，则创建一个新的空字典
        if handler_conf is None:
            handler_conf = {}

        # 更新配置值
        handler_conf[configName] = configValue

        # 存储更新后的handler配置
        self.bot.set_config(self.handler_conf_key, handler_conf, channel_id)

        # 检查和确认新的配置值
        new_handler_conf = self.bot.get_config(self.handler_conf_key, self.channel_id)

        if configName in new_handler_conf.keys():
            if new_handler_conf[configName] == configValue:
                self.debug_log(f'[SetConfig]{configName} : {new_handler_conf[configName]}')
            else:
                self.debug_log(f'[SetConfig] Failed to set {configName}')
        else:
            self.debug_log(f'[SetConfig] {configName} not found in config')

    # 已废弃, Quota现在由lib确定
    def __get_model_with_quota(self)->str:
        """决定要使用的Model，如果Quora超限则返回3.5"""

        model = self.bot.get_config("model",self.channel_id)

        if model == 'gpt-3.5-turbo':
            return model

        global quota
        quota = self.bot.get_config("gpt_4_quota")

        global call_limit_gen

        if next(call_limit_gen):
            return 'gpt-4'
        else:
            if model == 'gpt-3.5/4 Mixed':
                return 'gpt-3.5-turbo'
            else:
                return None
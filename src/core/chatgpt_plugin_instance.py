import os
import asyncio

from typing import Optional, Union

from core import log
from core.util import read_yaml
from core.customPluginInstance import AmiyaBotPluginInstance

from ..ask_chat_gpt import ChatGPTDelegate


class ChatGPTPluginInstance(AmiyaBotPluginInstance):
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

    def load(self):
        loop = asyncio.get_event_loop()
        loop.create_task(suppress_other_plugin(self))

    def get_prefix(self):
        return self._prefix_keywords

    def debug_log(self, message):
        show_log = self.get_config("show_log")
        if show_log == True:
            log.info(f'[ChatGPT]{message}')

    def get_quote_id(self, data):
        message = data.message
        if 'messageChain' in message.keys():
            for msg in message['messageChain']:
                self.debug_log(f'{msg}')
                if msg['type']=='Quote':
                    sender = msg['senderId']
                    self.debug_log(f'{sender}')
                    if f'{sender}' == f'{data.instance.appid}':
                        self.debug_log('find quote')
                        return msg['id']
        
        return 0

    def ask_amiya( prompt : Union[str, list],context_id : Optional[str] = None, use_friendly_error:bool = True,
                     use_conext_prefix : bool = True, use_stop_words : bool = True) -> Optional[str] :
        ...


class ChatGPTMessageHandler():
    def __init__(self, bot:ChatGPTPluginInstance,delegate:ChatGPTDelegate, channel_id,handler_conf_key) -> None:
        self.bot = bot
        self.delegate = delegate
        self.channel_id = channel_id
        self.handler_conf_key = handler_conf_key
    
    def get_handler_config(self, configName):
        handler_conf = self.bot.get_config(self.handler_conf_key,self.channel_id)

        if configName in handler_conf.keys():
            if handler_conf[configName] != "" and handler_conf[configName] != []:
                self.bot.debug_log(f'[GetConfig]{configName} : {handler_conf[configName]}')
                return handler_conf[configName]
        
        handler_conf = self.bot.get_config(self.handler_conf_key)

        if configName in handler_conf.keys():
            self.bot.debug_log(f'[GetConfig]{configName} : {handler_conf[configName]}')
            return handler_conf[configName]
        
        self.bot.debug_log(f'[GetConfig]{configName} : None')
        return None
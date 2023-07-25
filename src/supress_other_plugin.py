
import re

from types import SimpleNamespace

from amiyabot import Message

from core import log
from core import bot as main_bot

prefixReg = '(阿米娅|阿米兔|兔兔|兔子|小兔子|Amiya|amiya){0,1}'

class OtherPluginSuppressor:
    def __init__(self) -> None:
        self.bot = None

    def debug_log(self, message):
        show_log = self.bot.get_config("show_log")
        if show_log == True:
            log.info(message)

    async def multi_keyword_verify(self,data: Message, keywords:list, level):
        # self.debug_log(f"Suppressed multi_keyword_verify Handler Call keywords = {keywords}")
        if all(substring in data.text for substring in keywords):
            self.debug_log(f"命中该 multi_keyword_verify Handler level = {level}")
            return True, level
        return False, 0

    def make_multi_keyword_verify(self, keywords, handler):
        old_level = handler.level
        handler.custom_verify =  lambda data: self.multi_keyword_verify(data, keywords, old_level)
        handler.keywords = None
        handler.level = None

    async def regexp_verify(self,data: Message, reg, level):
        if level is None:
            level = 0
        # self.debug_log(f"Suppressed regexp_verify Handler Call reg = {reg}")
        if re.match(reg, data.text) is not None:
            self.debug_log(f"命中该 regexp_verify Handler level = {level}")
            return True, level
        return False, 0

    def make_regexp_verify(self, reg, handler):
        old_level = handler.level
        handler.custom_verify = lambda data: self.regexp_verify(data, reg, old_level)
        handler.keywords = None
        handler.level = None


    async def keyword_before_func_verify(self, data: Message, keywords:list, func):
        
        # self.debug_log(f"Suppressed keyword_before_func_verify Handler Call keywords = {keywords}")

        if any(substring in data.text for substring in keywords):
            self.debug_log(f"命中该Handler for:{data.text}，调用后续代码")
            try:
                retval = await func(data)
                self.debug_log(f'{retval}')
                return retval
            except Exception as e:
                log.error(e,"ChatGPT Suppressor")
        return False, 0
    
    def make_keyword_before_func_verify(self, keywords, handler):
        old_func = handler.custom_verify
        handler.custom_verify = lambda data: self.keyword_before_func_verify(data, keywords, old_func)
        handler.keywords = None
        handler.level = None

    async def reg_before_func_verify(self, data: Message, reg, func):
        
        # self.debug_log(f"Suppressed reg_before_func_verify Handler Call Reg = {reg}")
        
        if re.match(reg, data.text) is not None:
            self.debug_log(f"命中该Handler for:{data.text}，调用后续代码")
            try:
                retval = await func(data)
                self.debug_log(f'{retval}')
                return retval
            except Exception as e:
                log.error(e,"ChatGPT Suppressor")
        return False, 0
    
    def make_reg_before_func_verify(self, reg, handler):
        old_func = handler.custom_verify
        handler.custom_verify = lambda data: self.reg_before_func_verify(data, reg, old_func)
        handler.keywords = None
        handler.level = None

    async def disable_verify(self):
        return False,0

    def make_disable_verify(self,handler):
        handler.custom_verify = lambda data: self.disable_verify()
        handler.keywords = None
        handler.level = None

async def suppress_other_plugin(bot):
    suppressor = OtherPluginSuppressor()
    suppressor.bot = bot

    bot.debug_log(f"ChatGPT Plugin Change Other Handler：{bot.get_config('override_other_plugin')}")
    if bot.get_config('override_other_plugin') != True:
        return
    
    # 强制修改其他Bot的MessageHandler
    for _,plugin in main_bot.plugins.items():
        
        # 1. 干员查询 amiyabot-arknights-operator / 干员查询-水月 arknights-operator-m&c  
        if plugin.plugin_id.startswith('arknights-operator') or plugin.plugin_id.startswith('amiyabot-arknights-operator'):
            handlers = plugin.get_container('message_handlers')    
            bot.debug_log(f"正在检查{plugin.plugin_id}的handler")                
            for handler in handlers:                  
                if handler.keywords == ['语音','2.5版本先饶了他这一条，后面再说。']:
                    suppressor.make_multi_keyword_verify(['查询','语音'],handler.level)
                    bot.debug_log(f"调整了{plugin.plugin_id}的handler:语音")
                else:
                    if callable(handler.custom_verify):
                        try:
                            retval = await handler.custom_verify(SimpleNamespace(text="新年好",channel_id=0))
                            bot.debug_log(f'{retval}')
                            if retval[0] == True:
                                suppressor.make_keyword_before_func_verify(['查询'],handler)
                                bot.debug_log(f"调整了{plugin.plugin_id}的handler:'干员名'")
                        except Exception as e:
                            log.error(e,"ChatGPT Error:")

        if plugin.plugin_id.startswith('amiyabot-user'):
            handlers = plugin.get_container('message_handlers')
            bot.debug_log(f"正在检查{plugin.plugin_id}的handler")
            for handler in handlers:
                if handler.keywords is not None:
                    bot.debug_log(f"Keyword:{handler.keywords}")     
                    if "信赖" in handler.keywords and "关系" in handler.keywords:
                        suppressor.make_regexp_verify(fr'^{prefixReg}(关系|信赖|好感|我的信息|个人信息)',handler)
                        bot.debug_log(f"调整了{plugin.plugin_id}的handler")                 
                    elif "签到" in handler.keywords:
                        suppressor.make_regexp_verify(fr'^{prefixReg}(签到)',handler)
                        bot.debug_log(f"调整了{plugin.plugin_id}的handler")
                    elif "我错了" in handler.keywords and "对不起" in handler.keywords:
                        suppressor.make_disable_verify(handler)
                        bot.debug_log(f"调整了{plugin.plugin_id}的handler")                    
                    elif "阿米驴" in handler.keywords and "小驴子" in handler.keywords:
                        suppressor.make_disable_verify(handler)
                        bot.debug_log(f"调整了{plugin.plugin_id}的handler")
        
        if plugin.plugin_id.startswith('amiyabot-functions'):
            handlers = plugin.get_container('message_handlers')
            bot.debug_log(f"正在检查{plugin.plugin_id}的handler")
            for handler in handlers:
                if handler.keywords is not None:
                    bot.debug_log(f"Keyword:{handler.keywords}")     
                    if "功能" in handler.keywords and "说明" in handler.keywords:
                        suppressor.make_regexp_verify(fr'^{prefixReg}(功能|说明|帮助|help)',handler)
                        bot.debug_log(f"调整了{plugin.plugin_id}的handler")
                else:
                    if callable(handler.custom_verify):
                        try:
                            retval = await handler.custom_verify(SimpleNamespace(text="说明",channel_id=0))
                            bot.debug_log(f'{retval}')
                            if retval[0] == True:
                                suppressor.make_reg_before_func_verify(fr'^{prefixReg}(功能|说明|帮助|help)',handler)
                                bot.debug_log(f"调整了{plugin.plugin_id}的custom_verify handler:'功能'")
                        except Exception as e:
                            log.error(e,"ChatGPT Error:")
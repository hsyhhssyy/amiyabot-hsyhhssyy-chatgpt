
from types import SimpleNamespace

from amiyabot import Message

from core import log
from core import bot as main_bot

class OtherPluginSuppressor:
    def __init__(self) -> None:
        self.bot = None

    def debug_log(self, message):
        show_log = self.bot.get_config("show_log")
        if show_log == True:
            log.info(message)

    async def multi_keyword_verify(self,data: Message, keywords:list, level):
        self.debug_log(f"Suppressed multi_keyword_verify Handler Call keywords = {keywords}")
        if all(substring in data.text for substring in keywords):
            self.debug_log(f"命中新的Handler level = {level}")
            return True, level
        return False, 0

    def make_multi_keyword_verify(self, keywords, level):
        return lambda data: self.equal_verify(data, keywords, level)

    async def keyword_before_func_verify(self, data: Message, keywords:list, func):
        
        self.debug_log(f"Suppressed keyword_before_func_verify Handler Call keywords = {keywords}")

        if any(substring in data.text for substring in keywords):
            self.debug_log(f"命中新的Handler for:{data.text}")
            try:
                retval = await func(data)
                self.debug_log(f'{retval}')
                return retval
            except Exception as e:
                log.error(e,"ChatGPT Suppressor")
        return False, 0
    
    def make_keyword_before_func_verify(self, keywords, func):
        return lambda data: self.keyword_before_func_verify(data, keywords, func)

async def suppress_other_plugin(bot):
    suppressor = OtherPluginSuppressor()
    suppressor.bot = bot

    if bot.get_config('override_other_plugin') != True:
        return

    bot.debug_log("ChatGPT Plugin Change Other Handler")
    # 强制修改其他Bot的MessageHandler
    for _,plugin in main_bot.plugins.items():
        
        # 1. 干员查询 amiyabot-arknights-operator / 干员查询-水月 arknights-operator-m&c  
        if plugin.plugin_id.startswith('arknights-operator') or plugin.plugin_id.startswith('amiyabot-arknights-operator'):
            handlers = plugin.get_container('message_handlers')                    
            for handler in handlers:                  
                if handler.keywords == ['语音','2.5版本先饶了他这一条，后面再说。']:
                    handler.custom_verify = suppressor.make_multi_keyword_verify(['查询','语音'],handler.level)
                    handler.keywords = None
                    handler.level = None
                    bot.debug_log(f"调整了{plugin.plugin_id}的handler:语音")
                else:
                    if callable(handler.custom_verify):
                        try:
                            retval = await handler.custom_verify(SimpleNamespace(text="新年好",channel_id=0))
                            bot.debug_log(f'{retval}')
                            if retval[0] == True:
                                handler.custom_verify = suppressor.make_keyword_before_func_verify(['查询'],handler.custom_verify)
                                bot.debug_log(f"调整了{plugin.plugin_id}的handler:'干员名'")
                        except Exception as e:
                            log.error(e,"ChatGPT Error:")
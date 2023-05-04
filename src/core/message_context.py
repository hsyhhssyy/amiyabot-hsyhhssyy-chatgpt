import time

from amiyabot import Message, Chain

prefix = ['阿米娅', '阿米兔', '兔兔', '兔子', '小兔子', 'Amiya', 'amiya']

def get_quote_id(data):
    message = data.message
    if 'messageChain' in message.keys():
        for msg in message['messageChain']:
            if msg['type']=='Quote':
                sender = msg['senderId']
                if f'{sender}' == f'{data.instance.appid}':
                    return msg['id']

def format_request(text):
    # 首先移除先导关键词
    for prefix_str in prefix:
        # 检查文本是否以prefix开头
        if text.startswith(prefix_str):
            text = text[len(prefix_str):]
            # bot.debug_log(f'[ChatGPT]移除先导词 {prefix_str}')
            break
        # 检查文本是否以prefix + "chat"开头
        elif text.startswith(prefix_str + "chat"):
            text = text[len(prefix_str + "chat"):]
            # bot.debug_log(f'[ChatGPT]移除先导词 {prefix_str + "chat"}')
            break

    return text

class ChatGPTMessageContext:
    def __init__(self, text, nickname):
        self.text = text
        self.nickname = nickname
        self.timestamp = time.time()
        self.user_id = ChatGPTMessageContext.AMIYA_USER_ID
        self.is_quote = False

    AMIYA_USER_ID = 0

    @classmethod
    def from_message(cls, data:Message):
        context = cls(data.text_original, data.nickname)
        # context = cls(format_request(data.text_original), data.nickname)
        context.user_id = data.user_id
        context.is_quote = get_quote_id(data) == 0
        return context
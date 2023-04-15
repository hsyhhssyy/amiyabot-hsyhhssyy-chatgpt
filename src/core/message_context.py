import time

from amiyabot import Message, Chain

def get_quote_id(data):
    message = data.message
    if 'messageChain' in message.keys():
        for msg in message['messageChain']:
            if msg['type']=='Quote':
                sender = msg['senderId']
                if f'{sender}' == f'{data.instance.appid}':
                    return msg['id']

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
        context.user_id = data.user_id
        context.is_quote = get_quote_id(data) == 0
        return context
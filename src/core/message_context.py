import time

from typing import List, Tuple
from amiyabot.adapters.cqhttp import CQHttpBotInstance
from amiyabot import Message, Chain

prefix = ['阿米娅', '阿米兔', '兔兔', '兔子', '小兔子', 'Amiya', 'amiya']

def get_quote_id(data):
    message = data.message
    if type(data.instance) == CQHttpBotInstance and 'message' in message.keys():
        if len(message['message']) >= 2:
            # print(f'{message}')
            if message['message'][0]['type'] == 'reply' and message['message'][1]['type'] == 'at':
                if f"{message['message'][1]['data']['qq']}" == f'{data.instance.appid}':
                    # print(f"is quote {message['message'][0]['data']['id']}")
                    return message['message'][0]['data']['id']
    elif 'messageChain' in message.keys():
        for msg in message['messageChain']:
            if msg['type']=='Quote':
                sender = msg['senderId']
                if f'{sender}' == f'{data.instance.appid}':
                    # print(f"is quote {msg['id']}")
                    return msg['id']
    return 0

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
        self.image_url = []
        self.nickname = nickname
        self.timestamp = time.time()
        self.user_id = ChatGPTMessageContext.AMIYA_USER_ID
        self.is_quote = False
        self.is_prefix = False
        self.type = "text"

    AMIYA_USER_ID = 0
    MESSAGE_CONTENT_IMAGE = "[图片]"

    @classmethod
    def from_message(cls, data:Message):
        context = cls(data.text_original, data.nickname)
        if data.text_original is None or data.text_original == "":
            if data.image:
                context.text = "[图片]"
        # context = cls(format_request(data.text_original), data.nickname)
        context.user_id = data.user_id

        if data.image:
            context.image_url = data.image
            # for imgPath in data.image:
            #     imgBytes = download_sync(imgPath)
            #     pilImage = Image.open(BytesIO(imgBytes))
            #     images_in_prompt.append(pilImage)
        
        context.is_prefix = data.is_at or data.text_original.startswith(tuple(prefix))
        context.is_quote = get_quote_id(data) != 0
        return context

    @classmethod
    def pick_prompt(cls, context_list, max_chars=1000,distinguish_doc:bool= False) -> Tuple[list, str, list]:
        
        request_obj = []
        
        picked_context = []

        result = ""
        for i in range(1, len(context_list) + 1):
            context = context_list[-i]
            if context.user_id != ChatGPTMessageContext.AMIYA_USER_ID:
                if distinguish_doc:
                    text_to_append = f'[{context.nickname}博士]:{context.text}'
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
import os
import shutil
import openai

from amiyabot import PluginInstance, Message, Chain
from core.util import create_dir, read_yaml, run_in_thread_pool
from core import log

curr_dir = os.path.dirname(__file__)
config_file = 'resource/plugins/chatGPT/config.yaml'


class ChatGPTPluginInstance(PluginInstance):
    def install(self):
        if not os.path.exists(config_file):
            create_dir(config_file, is_file=True)
            shutil.copy(f'{curr_dir}/config.yaml', config_file)


bot = ChatGPTPluginInstance(
    name='ChatGPT 智能回复',
    version='1.1',
    plugin_id='amiyabot-hsyhhssyy-chatgpt',
    plugin_type='',
    description='调用 OpenAI ChatGPT 智能回复普通对话（接替兔妈维护）',
    document=f'{curr_dir}/README.md'
)
user_lock = []

context_holder= {}

async def check_talk(data: Message):
    if 'chat' in data.text.lower():
        return True, 10
    return True, 0

def format_request(text):

    # 首先移除先导关键词

    if text.startswith('兔兔'):
        text=text.replace('兔兔','',1)
    
    if text.startswith('阿米娅'):
        text=text.replace('阿米娅','',1)

    if text.startswith('Amiya'):
        text=text.replace('Amiya','',1)

    if text.startswith('amiya'):
        text=text.replace('amiya','',1)

    return text

def get_quote_id(data):
    message = data.message
    if 'messageChain' in message.keys():
        for msg in message['messageChain']:
            # log.info(f'{msg}')
            if msg['type']=='Quote':
                sender = msg['senderId']
                # log.info(f'{sender}')
                if f'{sender}' == f'{data.instance.appid}':
                    # log.info('find quote')
                    return msg['id']
    
    return 0

def get_context(data):
    context_id = f'{data.channel_id}-{data.user_id}'
    if context_id in context_holder.keys():
        log.info(f'context get :\n{context_holder[context_id]}')
        return context_holder[context_id]
    else:
        log.info(f'context get : [Null]')
        return ''

def set_context(data,text):
    context_id = f'{data.channel_id}-{data.user_id}'
    if context_id in context_holder.keys():
        log.info(f'context set :\n{context_holder[context_id] + text}')
        context_holder[context_id] = context_holder[context_id] + text
    else:
        log.info(f'context set :\n{text}')
        context_holder[context_id] = text

def clear_context(data):
    context_id = f'{data.channel_id}-{data.user_id}'
    if context_id in context_holder.keys():
        log.info(f'context clear')
        context_holder[context_id] =''

@bot.on_message(verify=check_talk)
async def _(data: Message):
    if not data.text:
        return

    if data.user_id in user_lock:
        await data.send(Chain(data).text('博士，我还在想上一个问题...>.<'))
        return

    config = read_yaml(config_file, _dict=True)
    openai.api_key = config['api_key']

    user_lock.append(data.user_id)

    request_text = format_request(data.text_original)

    # 尝试确定context
    if get_quote_id(data) >0:
        context = get_context(data)
        request_text = context + '\n' + request_text
    else:
        clear_context(data)
    
    # log.info(f'{request_text}')

    async with log.catch():
        await data.send(Chain(data).text('阿米娅思考中...').face(32))
        response = await run_in_thread_pool(
            openai.Completion.create,
            **{
                'prompt': request_text,
                **config['options']
            }
        )

    user_lock.remove(data.user_id)

    text: str = response['choices'][0]['text']

    set_context(data,request_text+text+'\n\n')


    if len(text) >= config['max_length']:
        return Chain(data, reference=True).markdown(text.strip('\n').replace('\n', '<br>'))
    else:
        return Chain(data, reference=True).text(text.strip('\n'))

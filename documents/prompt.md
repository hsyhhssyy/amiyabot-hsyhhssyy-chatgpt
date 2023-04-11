总的来说，想要完全催眠GPT-4，
需要将你的交互方式也要变得足够复杂，
以下是我尝试了很久才得出的结论：
我将交互内容分成五个模块

第一个模块 交互区
内容是角色的话语和动作以及心理描写

第二个模块 命令区
内容是针对 chatgpt 回答的具体要求

第三个模块 记忆区
里面存着角色设定 角色状态

第四个模块 回顾区
里面存放着 ChatGPT 上一次交互过程中的内容

第五个模块 格式区
里面提供是 ChatGPT 回复时需要遵循的格式

以上五个模块
每次都需要人为手动改变交互区、记忆区以及回顾区的内容
命令区的内容可以随时改变
以上五个模块内容每次交互都要一并提交给GPT4

使用步骤：
1、将五个模块当中的内容填写完毕后，发送给GPT-4，等待他将内容反馈给你
2、将GPT-4反馈的内容放至回顾区，替换掉原本回顾区的内容
3、将GPT-4反馈内容中的角色状态替换掉记忆区当中的角色状态
4、按照情节，你需要修改你所扮演的角色状态
5、修改交互区的内容
6、确认回顾区，记忆区，以及交互区信息无误后再将信息发送给GPT-4，周而复始。

视频操作指南：
https://www.bilibili.com/video/BV1ZX4y1o7Nj/?vd_source=dfe3e504ae1aa87f7
a57f7d0209e4791
贴吧原贴：
https://tieba.baidu.com/p/8313253049



现在有一个聊天机器人框架，每当有人在群里说话时，就会调用回调函数

def on_message(text,user_id,channel_id):

其中text是这个人说的话,user_id是这个用户的id,channel_id是所在的频道。

另有一个函数 def ask_amiya(text,channel_id) -> str: 可以根据一句话生成一个回复。
这个函数ask_amiya是由他人提供的，只需要引入即可。

还有一个函数 def check_conversation(texts: list, channel_id) -> bool: 可以判断一个str的列表是否属于同一个话题。
这个函数check_conversation也是由他人提供的，只需要引入即可。

现在，请你编写on_message函数的实现，实现下列功能：
1. 在某人说了一句超过4个字的话后，超过1分钟没人回复，兔兔会有10%的几率回复这句话。
2. 如果在30秒内，有连续10个人说话，兔兔会通过AI判断一下这10句话是否属于同一个话题，如果是，那么他也会回复这个话题的最后一句话。


我定义了一个class，并将全局变量转为存储在里面
class DeepCosplay:
    def __init__(self) -> None:
        self.recent_messages = []
        self.conversation_timeout = 30
        self.conversation_length = 10
        self.no_reply_timeout = 60
        self.reply_probability = 0.1
请将on_message实现为他的成员


经过修改和调整后，我将Python文件写成下面这个格式：

现在有一个聊天机器人框架，其代码如下所示：
每当有人在群里说话时，就会调用回调函数
def on_message(self, data: Message):
其中data是包含这个人说的话的消息对象，包含text_initial,user_id和message_id几个成员，text_initial是消息的字符串表示,user_id是这个用户的id,message_id是这条消息的唯一Guid

import time
import random
from threading import Timer
from typing import List

from amiyabot import Message, Chain
from .ask_chat_gpt import ChatGPTDelegate

# 用于保存大家聊天内容的数据类
class ChatGPTMessageContext:
    def __init__(self, data: str, timestamp: float, user_id: int):
        self.data = data
        self.timestamp = timestamp
        self.user_id = user_id


class DeepCosplay:
    def __init__(self,channel_id: int) -> None:
        self.channel_id = channel_id

        self.recent_messages : List[ChatGPTMessageContext] = []
        self.conversation_timeout = 30
        self.conversation_length = 10
        self.no_reply_timeout = 60
        self.reply_probability = 0.1

    def on_message(self, data: Message, force:bool=False):
        pass

    # 根据一大堆话生成一个回复
    def ask_amiya(self, context_list: List[ChatGPTMessageContext]) -> str:
        ...

    # 可以判断一个context的列表是否在讨论同一件事
    def check_conversation(self, context_list: List[ChatGPTMessageContext]):
        ...

    # 发送消息到频道
    def send_message(self, text: str):
        ...

    # 判断一条消息是否是回复了兔兔的消息
    def is_quoting(data:ChatGPTMessageContext) -> bool:
        ...

现在，请你编写on_message函数的实现，实现下列功能：
1. 在某人说了一句超过4个字的话后，超过1分钟没人回复，兔兔会有10%的几率回复这句话，并启动一个话题。
2. 如果在30秒内，有连续10个人说话，兔兔会通过AI判断一下这10句话是否在讨论同一件事，如果是，那么他会回复这段对话的最后一句话，并启动一个话题。
3. 如果force=True,则兔兔会回复这条消息并开启一个话题。
3. 话题在同一个频道内只会有一个，当有进行中的话题时，兔兔不会产生新的话题。
4. 在兔兔说话以后的30秒内，在话题内的用户，在群内说话，兔兔就会把他当成是回复，从而继续接话。
5. 兔兔回复的那条消息的发送者，初始就在话题内。
6. 其他用户可以选择在60秒内回复兔兔的消息从而加入话题，可用is_quoting判断。
7. 30秒内，没有话题内的用户说话，则话题结束。



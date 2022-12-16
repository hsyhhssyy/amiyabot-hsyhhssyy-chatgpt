> 调用 OpenAI ChatGPT 智能回复普通对话。

在唤起兔兔但不能触发其他任何功能时，将会进入此功能。可以在对话中附带 `chat` 关键词强制触发。

如果你想和机器人在同一个话题上持续对话，那么请回复兔兔说的那句话。如果你单独说一句话，那么兔兔会视为你开启了一个新的话题。

> 注意事项

仅支持代码部署使用，并需要使用境外手机号注册 [OpenAI](https://beta.openai.com/) 账户以获取ApiKey。

经过修改后的插件，可能不能再用于QQ频道。如果您不是QQ群用户，请继续使用兔妈原版插件。

警告！回复对话功能会指数级消耗你的API余额，可能会很快导致账户余额用尽。（具体原因是，和AI对话，每一次请求都要把历史聊天记录全部传给AI，而AI计费是算你发给他的文本的字数，因此随着对话越来越长，每次附带的记录也越来越长，收费也越来越高。）

兔妈版本的插件，会原封不动的发送用户的输入给API，我这个版本，尝试剔除一句话开头的：“兔兔”，“阿米娅”，“Amiya”。这样，如果用户用“兔兔地球为什么是圆的？”来触发发问，AI不会再去思考什么是“兔兔地球”。

> 安装 OpenAI

```
pip install openai
```

> 配置

打开配置文件：resource/plugins/chatGPT/config.yaml
找到api_key这一行，替换为您的API KEY

```yaml
api_key: {openai 账户的 api key}
```

> 其他

兔妈账户没额度了，不维护原来那个插件了，经过兔妈授权，我拿过来继续更新。

> [项目地址:Github](https://github.com/hsyhhssyy/amiyabot-hsyhhssyy-chatgpt/)

> [遇到问题可以在这里反馈(Github)](https://github.com/hsyhhssyy/amiyabot-hsyhhssyy-chatgpt/issues/new/)

> [如果上面的连接无法打开可以在这里反馈(Gitee)](https://gitee.com/hsyhhssyy/amiyabot-plugin-bug-report/issues/new)

> [Logo作者:Sesern老师](https://space.bilibili.com/305550122)

|  版本   | 变更  |
|  ----  | ----  |
| 1.0  | 兔妈的版本 |
| 1.1  | 加入连续对话功能，剔除前导关键词 |
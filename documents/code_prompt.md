一个Python类TRPGMode有下面几个成员函数

def get_config(self,key:str):

def set_config(self,key:str,value):

当key是pc_name_mapping时,可以读取和写入一个dict
我们希望这个dict用来保存一个玩家qq号和昵称的映射

def check_command(self, data):
函数通过接受一条qq聊天消息(data)更新这个映射
他的可用能力如下
data.at_target[0]可以获取消息中at的人的qq号
data.text可以获取消息文本
期望是消息格式为 "兔兔(@XXXX)设置PC名称巨神兵"可以将at的那个人映射为巨神兵
key是qq号,value是巨神兵
请写出一个check_command的可能实现

请根据下面这个函数实现set_handler_config

def get_handler_config(self, configName, default = None):
        handler_conf = self.bot.get_config(self.handler_conf_key,self.channel_id)

        if configName in handler_conf.keys():
            if handler_conf[configName] != "" and handler_conf[configName] != []:
                self.debug_log(f'[GetConfig]{configName} : {handler_conf[configName]}')
                return handler_conf[configName]
        
        handler_conf = self.bot.get_config(self.handler_conf_key)

        if configName in handler_conf.keys():
            if handler_conf[configName] != "" and handler_conf[configName] != []:
                self.debug_log(f'[GetConfig]{configName} : {handler_conf[configName]}')
                return handler_conf[configName]
            else:
                return default
        
        self.debug_log(f'[GetConfig]{configName} : None')
        return default

请注意,self.bot存在下面这个函数可供使用:
def set_config(self, config_name: str, config_value: JSON_VALUE_TYPE, channel_id: str = None):

下面这两个函数太过简单,没有判断边界条件,比如None之类的,请修改
def get_config(self,conf:str):
    if conf == "pc_name_mapping":
        map_str = self.get_handler_config("pc_name_mapping")
        json_object = json.loads(map_str)
        return json_object

def set_config(self,conf:str,value):
    if conf == "pc_name_mapping":
        json_str = json.dump(value)
        self.set_handler_config("pc_name_mapping",json_str)

Python有一个变量item_info是一个dict的数组，格式如下：
[{
"名称": "电池",
"数量": -1,
"单位": "块",
"情报": ["情报1","情报2"]
}],

现有一个变量json_obj,是从下面这个json转换而来:
{
	"reply": "明白了，今晚就在这里休息。如果有怪物靠近，我们的屏蔽器会警告我们。在这之前，我想我们应该设立一些警戒机制，比如在可能的入口放置一些暗示，以便于在怪物接近时我们可以得到警告。",
	"role": "阿米娅",
	"item_exchange": [{
		"Names": "电池",
		"Amount": -1,
		"Unit": "块"
	}],
	"mp_change": 0,
	"hp_change": 0,
	"env_info_gain": [
		"基站中除门外没有其他出入口",
		"此基站目前处于无电状态",
		"电池更换后屏蔽器的电量为80%"
	],
	"itm_info_gain": {
		"电池": [
			"电池可以为屏蔽器提供电力"
		],
		"屏蔽器": [
			"屏蔽器消耗电池电量"
		]
	}
}
请根据里面的item_exchange和itm_info_gain更新item_info,更新操作包括新增物品,添加数量,增加情报
注意不可以删除item_info里的项,且物品数量不能低于0

有两个字符串数组
        env_info = self.get_config('env_info')  
        env_info_gain = json_obj["env_info_gain"]
请将env_info_gain添加进env_info


if conf == "item_info" or conf == "loc_info":
            map_obj = self.get_handler_config(conf)
            if map_obj is None:
                return []
            try:
                converted_list = [json.loads(item) for item in map_obj]
                return converted_list
            except json.JSONDecodeError:
                return []
这段代码请改为跳过不能正常转换的item,保留可以正常转换的item
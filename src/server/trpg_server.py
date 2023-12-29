import json

from datetime import datetime, timedelta

from pydantic import BaseModel

from peewee import SelectQuery

from core import app
from core import bot as main_bot

from ..core.developer_types import BLMAdapter
from ..core.trpg_storage import AmiyaBotChatGPTParamHistory,AmiyaBotChatGPTTRPGSpeechLog,AmiyaBotChatGPTExecutionLog

# Pydantic Models
class ParamByTeam(BaseModel):
    team_uuid: str
    param_name: str

class SpeechByTeam(BaseModel):
    team_uuid: str

class InsertParamHistory(BaseModel):
    team_uuid: str
    param_name: str
    param_value: str

class InsertSpeechLog(BaseModel):
    team_uuid: str
    channel_id: str
    channel_name: str
    user_id: str
    user_type: str
    irrelevant: bool
    data: str

class InsertExecutionLog(BaseModel):
    team_uuid: str
    channel_id: str
    channel_name: str
    template_name: str
    template_value: str
    model:str
    data: str

@app.controller
class TRPGAPI:
    # 列出指定team_uuid的两个类的两个接口
    @app.route(method='post')
    async def get_param_history_by_name(self, params: ParamByTeam):
        team_uuid = params.team_uuid
        param_name = params.param_name
        query = AmiyaBotChatGPTParamHistory.select().where((AmiyaBotChatGPTParamHistory.team_uuid == team_uuid)&(AmiyaBotChatGPTParamHistory.param_name == param_name))
        result_dicts = [result.__data__ for result in query]
        return app.response({"success": True, "param_history": result_dicts})

    @app.route(method='post')
    async def get_speech_log(self, params: SpeechByTeam):
        team_uuid = params.team_uuid
        query = AmiyaBotChatGPTTRPGSpeechLog.select().where(AmiyaBotChatGPTTRPGSpeechLog.team_uuid == team_uuid)
        result_dicts = [result.__data__ for result in query]
        return app.response({"success": True, "speech_log": result_dicts})

    @app.route(method='post')
    async def get_execution_log(self, params: SpeechByTeam):
        team_uuid = params.team_uuid
        query = AmiyaBotChatGPTExecutionLog.select().where(AmiyaBotChatGPTExecutionLog.team_uuid == team_uuid)
        result_dicts = [result.__data__ for result in query]
        return app.response({"success": True, "execution_log": result_dicts})


    @app.route(method='post')
    async def insert_param_history(self, params: InsertParamHistory):
        team_uuid = params.team_uuid
        param_name = params.param_name
        param_value = params.param_value
        new_entry = AmiyaBotChatGPTParamHistory.create(
            team_uuid=team_uuid,
            param_name=param_name,
            param_value=param_value,
            create_at=datetime.now()
        )
        return app.response({"success": True, "inserted_id": new_entry.id})

    @app.route(method='post')
    async def insert_speech_log(self, params: InsertSpeechLog):
        team_uuid = params.team_uuid
        channel_id = params.channel_id
        channel_name = params.channel_name
        user_id = params.user_id
        user_type = params.user_type
        irrelevant = params.irrelevant
        data = params.data
        new_entry = AmiyaBotChatGPTTRPGSpeechLog.create(
            team_uuid=team_uuid,
            channel_id=channel_id,
            channel_name=channel_name,
            user_id=user_id,
            user_type=user_type,
            irrelevant=irrelevant,
            data=data,
            create_at=datetime.now()
        )
        return app.response({"success": True, "inserted_id": new_entry.id})

    @app.route(method='post')
    async def insert_execution_log(self, params: InsertExecutionLog):

        blm_lib : BLMAdapter = main_bot.plugins['amiyabot-blm-library']

        if params.template_value is None or params.template_value == "":

            param_name = f"TEMPLATE-{params.template_name}"
            # 读取Template
            record = AmiyaBotChatGPTParamHistory.select().where(
                (AmiyaBotChatGPTParamHistory.param_name == param_name) &
                (AmiyaBotChatGPTParamHistory.team_uuid == params.team_uuid)
            ).order_by(AmiyaBotChatGPTParamHistory.create_at.desc()).first()

            if record is None:
                return app.response({"success": False, "reason": "No such template"})
            
            template = record.param_value
        
        else:

            template = params.template_value

        # 从data json获取字典
        data_dict = json.loads(params.data)

        print(f"{data_dict}")

        for key in data_dict:
            value = data_dict[key]
            template = template.replace(f"<<{key}>>",value)

        response = await blm_lib.chat_flow(
            prompt=template,
            model=params.model,
            channel_id=params.channel_id,
            json_mode=True)

        new_entry = AmiyaBotChatGPTExecutionLog.create(
            team_uuid=params.team_uuid,
            channel_id=params.channel_id,
            channel_name=params.channel_name,
            template_name=params.template_name,
            template_value=params.template_value,
            model=params.model,
            data=params.data,
            raw_request=template,
            raw_response=response,
            create_at=datetime.now()
        )
        return app.response({"success": True, "inserted_id": new_entry.id})
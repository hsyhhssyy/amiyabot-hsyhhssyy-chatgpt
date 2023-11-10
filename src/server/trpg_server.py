from datetime import datetime, timedelta
from peewee import SelectQuery
from ..core.trpg_storage import AmiyaBotChatGPTTRPGParamHistory,AmiyaBotChatGPTTRPGSpeechLog
from core import app
from pydantic import BaseModel

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

@app.controller
class TRPGAPI:
    # 列出指定team_uuid的两个类的两个接口
    @app.route(method='post')
    async def get_param_history_by_name(self, params: ParamByTeam):
        team_uuid = params.team_uuid
        param_name = params.param_name
        query = AmiyaBotChatGPTTRPGParamHistory.select().where((AmiyaBotChatGPTTRPGParamHistory.team_uuid == team_uuid)&(AmiyaBotChatGPTTRPGParamHistory.param_name == param_name))
        result_dicts = [result.__data__ for result in query]
        return app.response({"success": True, "param_history": result_dicts})

    @app.route(method='post')
    async def get_speech_log(self, params: SpeechByTeam):
        team_uuid = params.team_uuid
        query = AmiyaBotChatGPTTRPGSpeechLog.select().where(AmiyaBotChatGPTTRPGSpeechLog.team_uuid == team_uuid)
        result_dicts = [result.__data__ for result in query]
        return app.response({"success": True, "speech_log": result_dicts})

    @app.route(method='post')
    async def insert_param_history(self, params: InsertParamHistory):
        team_uuid = params.team_uuid
        param_name = params.param_name
        param_value = params.param_value
        new_entry = AmiyaBotChatGPTTRPGParamHistory.create(
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

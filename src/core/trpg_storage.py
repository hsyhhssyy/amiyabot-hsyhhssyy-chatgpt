from datetime import datetime

from peewee import AutoField,CharField,TextField,DateTimeField,BooleanField

from amiyabot.database import ModelClass

from core.database.plugin import db

class AmiyaBotChatGPTParamHistory(ModelClass):
    id: int = AutoField()
    team_uuid: str = CharField()
    param_name: str = CharField()
    param_value: str = TextField()
    create_at: datetime = DateTimeField(null=True)

    class Meta:
        database = db
        table_name = "amiyabot-hsyhhssyy-chatgpt-param-history"

    def get_param(param_name,team_uuid):
        record = AmiyaBotChatGPTParamHistory.select().where(
            (AmiyaBotChatGPTParamHistory.param_name == param_name) &
            (AmiyaBotChatGPTParamHistory.team_uuid == team_uuid)
        ).order_by(AmiyaBotChatGPTParamHistory.create_at.desc()).first()

        if record:
            return record.param_value
        else:
            return None
    
    def set_param(param_name,param_value,team_uuid):
        new_entry = AmiyaBotChatGPTParamHistory.create(
            team_uuid=team_uuid,
            param_name=param_name,
            param_value=param_value,
            create_at=datetime.now()
        )
        return new_entry.id

class AmiyaBotChatGPTTRPGSpeechLog(ModelClass):
    id: int = AutoField()
    team_uuid: str = CharField()
    channel_id: str = CharField()
    channel_name: str = CharField()
    user_id: str = TextField()
    user_type: str = TextField()
    irrelevant: bool = BooleanField()
    data: str = TextField()
    create_at: datetime = DateTimeField(null=True)

    class Meta:
        database = db
        table_name = "amiyabot-hsyhhssyy-chatgpt-trpg-speech-log"

class AmiyaBotChatGPTExecutionLog(ModelClass):
    id: int = AutoField()
    team_uuid: str = CharField()
    channel_id: str = CharField()
    channel_name: str = CharField()
    template_name: str = CharField()
    template_value: str = TextField()
    model:str = CharField()
    data: str = TextField()
    raw_request: str = TextField()
    raw_response: str = TextField()
    create_at: datetime = DateTimeField(null=True)

    class Meta:
        database = db
        table_name = "amiyabot-hsyhhssyy-chatgpt-exec-log"
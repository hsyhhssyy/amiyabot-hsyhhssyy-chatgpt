from datetime import datetime

from peewee import AutoField,CharField,TextField,DateTimeField,BooleanField

from amiyabot.database import ModelClass

from core.database.plugin import db

class AmiyaBotChatGPTTRPGParamHistory(ModelClass):
    id: int = AutoField()
    team_uuid: str = CharField()
    param_name: str = CharField()
    param_value: str = TextField()
    create_at: datetime = DateTimeField(null=True)

    class Meta:
        database = db
        table_name = "amiyabot-hsyhhssyy-chatgpt-trpg-param-history"

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
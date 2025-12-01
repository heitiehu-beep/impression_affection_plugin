"""
印象消息记录模型 - 用于去重处理
"""

from peewee import Model, TextField, DateTimeField
from datetime import datetime
from .database import db


class ImpressionMessageRecord(Model):
    """印象构建时处理的消息记录（用于去重）"""

    user_id = TextField(index=True)
    message_id = TextField(index=True)
    impression_id = TextField(null=True)  # 对应的印象记录ID
    processed_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        table_name = "impression_message_records"
        indexes = (
            (('user_id', 'message_id'), True),  # 复合唯一索引
        )

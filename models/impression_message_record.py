"""
印象消息记录模型 - 存储已处理消息的记录
"""

from peewee import Model, TextField, DateTimeField
from datetime import datetime
from .database import db


class ImpressionMessageRecord(Model):
    """印象消息记录模型 - 存储已处理消息的记录"""

    user_id = TextField(index=True)
    message_id = TextField(index=True, unique=True)
    content_hash = TextField(index=True, null=True)
    processed_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        table_name = "impression_message_records"
        indexes = (
            (("user_id", "message_id"), False),  # 复合索引
            (("user_id", "processed_at"), False),  # 复合索引
            (("user_id", "content_hash"), False),  # 新增：内容哈希索引
        )

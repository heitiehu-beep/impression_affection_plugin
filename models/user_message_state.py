"""
用户消息状态模型 - 跟踪增量消息处理状态
"""

from peewee import Model, TextField, IntegerField, DateTimeField, BigIntegerField
from datetime import datetime
from .database import db


class UserMessageState(Model):
    """用户消息状态跟踪（增量处理）"""

    user_id = TextField(unique=True, index=True)
    last_message_id = TextField(null=True)
    last_message_time = DateTimeField(null=True)

    # 更新计数
    impression_update_count = IntegerField(default=0)
    affection_update_count = IntegerField(default=0)

    # 消息统计
    total_messages = BigIntegerField(default=0)
    processed_messages = BigIntegerField(default=0)

    class Meta:
        database = db
        table_name = "user_message_state"

    def increment_counters(self, impression_updated: bool = False, affection_updated: bool = False):
        """增加计数器"""
        self.total_messages += 1
        self.processed_messages += 1

        if impression_updated:
            self.impression_update_count += 1

        if affection_updated:
            self.affection_update_count += 1

        self.last_message_time = datetime.now()

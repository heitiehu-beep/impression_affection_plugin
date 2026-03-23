"""
数据库模型模块 - 纯文本多维度版本
"""

from .user_impression import UserImpression
from .user_message_state import UserMessageState
from .impression_message_record import ImpressionMessageRecord
from .database import db

__all__ = [
    'UserImpression',
    'UserMessageState', 
    'ImpressionMessageRecord',
    'db'
]
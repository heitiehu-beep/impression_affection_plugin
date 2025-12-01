"""
消息管理服务 - 管理用户消息状态和记录
"""

from typing import Dict, Any, Optional
from datetime import datetime

from ..models import UserMessageState, ImpressionMessageRecord, UserImpression


class MessageService:
    """消息管理服务"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def update_message_state(self, user_id: str, message_id: str, impression_updated: bool = False, affection_updated: bool = False):
        """
        更新用户消息状态

        Args:
            user_id: 用户ID
            message_id: 消息ID
            impression_updated: 是否更新了印象
            affection_updated: 是否更新了好感度
        """
        try:
            state, created = UserMessageState.get_or_create(user_id=user_id)

            state.last_message_id = message_id
            state.last_message_time = datetime.now()
            state.total_messages += 1
            state.processed_messages += 1

            if impression_updated:
                state.impression_update_count += 1

            if affection_updated:
                state.affection_update_count += 1

            state.save()

        except Exception as e:
            # 记录错误但不抛出，避免影响主流程
            print(f"更新消息状态失败: {str(e)}")

    def record_processed_message(self, user_id: str, message_id: str, impression_id: str = None) -> bool:
        """
        记录已处理的消息（用于去重）

        Args:
            user_id: 用户ID
            message_id: 消息ID
            impression_id: 印象记录ID

        Returns:
            是否成功记录
        """
        try:
            # 检查是否已存在
            existing = ImpressionMessageRecord.select().where(
                (ImpressionMessageRecord.user_id == user_id) &
                (ImpressionMessageRecord.message_id == message_id)
            ).first()

            if existing:
                return False

            # 创建记录
            ImpressionMessageRecord.create(
                user_id=user_id,
                message_id=message_id,
                impression_id=impression_id,
                processed_at=datetime.now()
            )

            return True

        except Exception as e:
            print(f"记录处理消息失败: {str(e)}")
            return False

    def is_message_processed(self, user_id: str, message_id: str) -> bool:
        """
        检查消息是否已处理

        Args:
            user_id: 用户ID
            message_id: 消息ID

        Returns:
            是否已处理
        """
        try:
            existing = ImpressionMessageRecord.select().where(
                (ImpressionMessageRecord.user_id == user_id) &
                (ImpressionMessageRecord.message_id == message_id)
            ).first()

            return existing is not None

        except Exception:
            return False

    def get_message_state(self, user_id: str) -> Optional[UserMessageState]:
        """
        获取用户消息状态

        Args:
            user_id: 用户ID

        Returns:
            消息状态对象或None
        """
        try:
            return UserMessageState.get_or_create(user_id=user_id)[0]
        except Exception:
            return None

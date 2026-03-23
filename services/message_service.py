"""
消息管理服务 - 管理用户消息状态和记录
"""

import os
import hashlib
from typing import Dict, Any, Optional, Set, List
from datetime import datetime, timedelta

from ..models import UserMessageState, ImpressionMessageRecord, UserImpression
from src.common.logger import get_logger

logger = get_logger("impression_affection_message")

class MessageService:
    """消息管理服务"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.processed_content_hashes = {}
        self.message_id_cache = {}

    @staticmethod
    def normalize_user_id(user_id: Any) -> str:
        """
        标准化用户ID格式

        Args:
            user_id: 原始用户ID

        Returns:
            标准化后的用户ID字符串
        """
        if user_id is None:
            return ""

        user_id_str = str(user_id).strip()

        # 移除常见前缀
        if user_id_str.startswith("qq_"):
            user_id_str = user_id_str[3:]
        elif user_id_str.startswith("QQ:"):
            user_id_str = user_id_str[3:]
        elif user_id_str.startswith("U:"):
            user_id_str = user_id_str[2:]

        # 移除花括号等
        user_id_str = user_id_str.strip("{}[]()")

        return user_id_str

    def generate_content_hash(self, content: str) -> str:
        """
        生成消息内容的哈希值（用于去重）

        Args:
            content: 消息内容

        Returns:
            MD5哈希值
        """
        normalized_content = content.strip().lower()
        return hashlib.md5(normalized_content.encode('utf-8')).hexdigest()

    def is_message_processed(self, user_id: str, message_id: str) -> bool:
        """
        检查消息是否已处理过（基于message_id）

        Args:
            user_id: 用户ID
            message_id: 主程序的实际message_id

        Returns:
            是否已处理
        """
        if not message_id:
            logger.debug(f"message_id为空，无法查重")
            return False

        normalized_user_id = self.normalize_user_id(user_id)

        # 检查数据库记录
        try:
            existing = ImpressionMessageRecord.select().where(
                (ImpressionMessageRecord.user_id == normalized_user_id) &
                (ImpressionMessageRecord.message_id == message_id)
            ).first()

            if existing:
                logger.debug(f"消息已处理(数据库): 用户 {normalized_user_id}, message_id {message_id}")
                return True
            else:
                logger.debug(f"消息未处理: 用户 {normalized_user_id}, message_id {message_id}")
                return False

        except Exception as e:
            logger.error(f"检查消息处理状态失败: {str(e)}")
            return False

    def mark_message_processed(self, user_id: str, message_id: str, impression_id: str = None):
        """
        标记消息为已处理（基于message_id）

        Args:
            user_id: 用户ID
            message_id: 主程序的实际message_id
            impression_id: 印象记录ID（可选）
        """
        if not message_id:
            logger.warning(f"无法标记处理：message_id为空")
            return

        normalized_user_id = self.normalize_user_id(user_id)

        # 记录到数据库
        try:
            # 检查是否已存在
            existing = ImpressionMessageRecord.select().where(
                (ImpressionMessageRecord.user_id == normalized_user_id) &
                (ImpressionMessageRecord.message_id == message_id)
            ).first()

            if not existing:
                ImpressionMessageRecord.create(
                    user_id=normalized_user_id,
                    message_id=message_id,
                    processed_at=datetime.now()
                )
                logger.info(f"记录已处理消息: 用户 {normalized_user_id}, message_id {message_id}")
            else:
                logger.debug(f"消息已存在: 用户 {normalized_user_id}, message_id {message_id}")

        except Exception as e:
            logger.error(f"记录处理消息失败: {str(e)}")

    def is_content_processed(self, user_id: str, content: str) -> bool:
        """
        检查消息内容是否已处理过（基于内容哈希）

        Args:
            user_id: 用户ID
            content: 消息内容

        Returns:
            是否已处理
        """
        normalized_user_id = self.normalize_user_id(user_id)
        content_hash = self.generate_content_hash(content)

        # 检查内存缓存
        if normalized_user_id in self.processed_content_hashes:
            if content_hash in self.processed_content_hashes[normalized_user_id]:
                return True

        # 检查数据库
        try:
            existing = ImpressionMessageRecord.select().where(
                (ImpressionMessageRecord.user_id == normalized_user_id) &
                (ImpressionMessageRecord.content_hash == content_hash)
            ).first()

            return existing is not None
        except Exception as e:
            logger.error(f"检查内容处理状态失败: {str(e)}")
            return False

    def get_processed_message_ids(self, user_id: str) -> Set[str]:
        """
        获取用户已处理的消息ID列表

        Args:
            user_id: 用户ID

        Returns:
            已处理的消息ID集合
        """
        normalized_user_id = self.normalize_user_id(user_id)

        # 从数据库获取
        try:
            db_records = ImpressionMessageRecord.select().where(
                ImpressionMessageRecord.user_id == normalized_user_id
            )

            processed_ids = set()
            for record in db_records:
                if record.message_id:
                    processed_ids.add(record.message_id)

            logger.debug(f"用户 {normalized_user_id} 已处理消息ID统计: 数据库 {len(db_records)} 个，总计 {len(processed_ids)} 个")

            return processed_ids
        except Exception as e:
            logger.error(f"获取已处理消息ID失败: {str(e)}")
            return set()

    def cleanup_old_records(self, user_id: str, days_to_keep: int = 30):
        """
        清理旧的处理记录

        Args:
            user_id: 用户ID
            days_to_keep: 保留天数
        """
        normalized_user_id = self.normalize_user_id(user_id)

        try:
            cutoff_date = datetime.now() - timedelta(days=days_to_keep)

            # 删除旧记录
            deleted_count = ImpressionMessageRecord.delete().where(
                (ImpressionMessageRecord.user_id == normalized_user_id) &
                (ImpressionMessageRecord.processed_at < cutoff_date)
            ).execute()

            if deleted_count > 0:
                logger.info(f"清理用户 {normalized_user_id} 的 {deleted_count} 条旧记录")

        except Exception as e:
            logger.error(f"清理旧记录失败: {str(e)}")

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

    def record_processed_message(self, user_id: str, message_id: str, content: str = None, impression_id: str = None) -> bool:
        """
        记录已处理的消息（用于去重）

        Args:
            user_id: 用户ID
            message_id: 消息ID
            content: 消息内容（可选，用于内容哈希）
            impression_id: 印象记录ID

        Returns:
            是否成功记录
        """
        normalized_user_id = self.normalize_user_id(user_id)
        content_hash = None

        # 如果提供了内容，生成内容哈希
        if content:
            content_hash = self.generate_content_hash(content)

            # 检查内容是否已处理
            if self.is_content_processed(normalized_user_id, content):
                logger.debug(f"消息内容已存在，跳过重复记录: 用户 {normalized_user_id}, 消息ID {message_id}")
                return False

        try:
            # 检查消息ID是否已存在
            existing = ImpressionMessageRecord.select().where(
                (ImpressionMessageRecord.user_id == normalized_user_id) &
                (ImpressionMessageRecord.message_id == message_id)
            ).first()

            if existing:
                # 更新内容哈希（如果之前没有）
                if content_hash and not existing.content_hash:
                    existing.content_hash = content_hash
                    existing.save()
                    logger.debug(f"更新消息内容哈希: 用户 {normalized_user_id}, 消息ID {message_id}, 哈希 {content_hash[:8]}...")
                return False

            # 创建记录
            ImpressionMessageRecord.create(
                user_id=normalized_user_id,
                message_id=message_id,
                impression_id=impression_id,
                content_hash=content_hash,
                processed_at=datetime.now()
            )

            # 添加到内存缓存
            if content_hash:
                if normalized_user_id not in self.processed_content_hashes:
                    self.processed_content_hashes[normalized_user_id] = set()
                self.processed_content_hashes[normalized_user_id].add(content_hash)

                if normalized_user_id not in self.message_id_cache:
                    self.message_id_cache[normalized_user_id] = {}
                self.message_id_cache[normalized_user_id][message_id] = content_hash

            logger.debug(f"记录新处理消息: 用户 {normalized_user_id}, 消息ID {message_id}")
            return True

        except Exception as e:
            logger.error(f"记录处理消息失败: {str(e)}")
            return False

    def get_message_state(self, user_id: str) -> Optional[UserMessageState]:
        """
        获取用户消息状态

        Args:
            user_id: 用户ID

        Returns:
            消息状态对象或None
        """
        normalized_user_id = self.normalize_user_id(user_id)

        try:
            return UserMessageState.get_or_create(user_id=normalized_user_id)[0]
        except Exception as e:
            logger.error(f"获取消息状态失败: {str(e)}")
            return None

    def get_user_processing_stats(self, user_id: str) -> Dict[str, Any]:
        """
        获取用户处理统计信息

        Args:
            user_id: 用户ID

        Returns:
            处理统计信息
        """
        normalized_user_id = self.normalize_user_id(user_id)

        try:
            # 获取消息状态
            message_state = self.get_message_state(normalized_user_id)
            if not message_state:
                return {"error": "用户消息状态不存在"}

            # 获取处理记录数量
            processed_count = ImpressionMessageRecord.select().where(
                ImpressionMessageRecord.user_id == normalized_user_id
            ).count()

            # 获取内存缓存统计
            cached_hashes = len(self.processed_content_hashes.get(normalized_user_id, set()))
            cached_ids = len(self.message_id_cache.get(normalized_user_id, {}))

            return {
                "user_id": normalized_user_id,
                "total_messages": message_state.total_messages,
                "processed_messages": message_state.processed_messages,
                "impression_updates": message_state.impression_update_count,
                "affection_updates": message_state.affection_update_count,
                "database_records": processed_count,
                "cached_content_hashes": cached_hashes,
                "cached_message_ids": cached_ids,
                "last_message_time": message_state.last_message_time,
                "last_message_id": message_state.last_message_id
            }

        except Exception as e:
            logger.error(f"获取处理统计失败: {str(e)}")
            return {"error": f"获取统计失败: {str(e)}"}

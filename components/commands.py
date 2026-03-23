"""
命令组件 - 管理命令
"""

from typing import Optional, List
from src.plugin_system import BaseCommand

from ..models import UserImpression, UserMessageState
from ..utils.helpers import get_affection_level

class BaseImpressionCommand(BaseCommand):
    """提供权限检查功能"""

    def _check_permission(self) -> bool:
        """
        检查用户是否有权限使用命令
        如果配置 allowed_users 为空列表，允许所有人使用
        如果配置了指定用户ID，只有这些用户能使用
        """
        # 获取命令配置
        commands_config = self.plugin_config.get("commands", {})
        allowed_users = commands_config.get("allowed_users", [])

        # 如果没有设置允许列表（空列表），允许所有人
        if not allowed_users:
            return True

        # 获取当前用户ID（发送命令的人）
        current_user_id = None

        # 尝试多种可能的属性获取方式
        if hasattr(self, 'user_id'):
            current_user_id = self.user_id
        elif hasattr(self, 'event') and hasattr(self.event, 'user_id'):
            current_user_id = self.event.user_id
        elif hasattr(self, 'message') and hasattr(self.message, 'user_id'):
            current_user_id = self.message.user_id

        if not current_user_id:
            return False

        # 标准化比较（都转为字符串）
        current_user_id_str = str(current_user_id).strip()
        allowed_list = [str(uid).strip() for uid in allowed_users]

        return current_user_id_str in allowed_list


class ViewImpressionCommand(BaseImpressionCommand):
    """查看印象命令"""

    command_name = "view_impression"
    command_description = "查看指定用户的印象和好感度"
    command_pattern = r"^/impression\s+(?:view|v)\s+(?P<user_id>\d+)$"

    async def execute(self) -> tuple:
        """执行查看印象"""
        try:
            # 权限检查 - 静默拒绝（无权限直接返回，不提示）
            if not self._check_permission():
                return False, "权限不足", False

            user_id = self.matched_groups.get("user_id")
            if not user_id:
                await self.send_text("请提供用户ID")
                return False, "请提供用户ID", False

            # 从数据库获取印象
            impression = UserImpression.select().where(
                UserImpression.user_id == user_id
            ).first()

            if not impression:
                await self.send_text(f"暂无用户 {user_id} 的印象数据")
                return False, f"暂无用户 {user_id} 的印象数据", False

            # 获取消息状态
            state = UserMessageState.get_or_create(user_id=user_id)[0]

            # 获取印象摘要
            impression_summary = impression.get_impression_summary()

            message = f"""
用户印象信息 (ID: {user_id})
━━━━━━━━━━━━━━━━━━━━━━
印象: {impression_summary}

好感度: {impression.affection_score:.1f}/100 ({impression.affection_level})
累计消息: {impression.message_count} 条
总消息: {state.total_messages} 条
更新时间: {impression.updated_at.strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
            """.strip()

            await self.send_text(message)
            return True, None, False

        except Exception as e:
            error_msg = f"查看印象失败: {str(e)}"
            await self.send_text(error_msg)
            return False, error_msg, False


class SetAffectionCommand(BaseImpressionCommand):
    """手动设置好感度命令"""

    command_name = "set_affection"
    command_description = "手动调整用户好感度"
    command_pattern = r"^/impression\s+(?:set|s)\s+(?P<user_id>\d+)\s+(?P<score>\d+)$"

    async def execute(self) -> tuple:
        """执行设置好感度"""
        try:
            # 权限检查
            if not self._check_permission():
                return False, "权限不足", False

            user_id = self.matched_groups.get("user_id")
            score_str = self.matched_groups.get("score")

            if not user_id or not score_str:
                await self.send_text("用法: /impression set <user_id> <score>")
                return False, "参数错误", False

            try:
                score = float(score_str)
                if not (0 <= score <= 100):
                    await self.send_text("好感度分数必须在0-100之间")
                    return False, "分数超出范围", False
            except ValueError:
                await self.send_text("好感度分数必须是数字")
                return False, "分数格式错误", False

            # 获取或创建印象记录
            impression, created = UserImpression.get_or_create(user_id=user_id)

            # 更新好感度
            impression.affection_score = score
            impression.affection_level = get_affection_level(score)
            impression.save()

            action = "创建" if created else "更新"
            await self.send_text(f"{action}用户 {user_id} 的好感度为: {score:.1f}/100 ({impression.affection_level})")

            return True, f"{action}好感度成功", False

        except Exception as e:
            error_msg = f"设置好感度失败: {str(e)}"
            await self.send_text(error_msg)
            return False, error_msg, False


class ListImpressionsCommand(BaseImpressionCommand):
    """列出所有印象命令"""

    command_name = "list_impressions"
    command_description = "列出所有用户的印象和好感度"
    command_pattern = r"^/impression\s+(?:list|ls)$"

    async def execute(self) -> tuple:
        """执行列出印象"""
        try:
            # 权限检查 - 静默拒绝
            if not self._check_permission():
                return False, "权限不足", False

            # 获取所有印象
            impressions = UserImpression.select()

            if not impressions:
                await self.send_text("暂无用户印象数据")
                return True, "无数据", False

            # 构建消息
            message = "用户印象列表\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━\n"

            for imp in impressions:
                impression_summary = imp.get_impression_summary()
                message += f"\n用户: {imp.user_id}\n"
                message += f"印象: {impression_summary[:30]}...\n"
                message += f"好感度: {imp.affection_score:.1f}/100 ({imp.affection_level})\n"
                message += f"消息数: {imp.message_count}\n"
                message += f"更新: {imp.updated_at.strftime('%m-%d %H:%M')}\n"

            await self.send_text(message)
            return True, f"列出 {len(impressions)} 个用户印象", False

        except Exception as e:
            error_msg = f"列出印象失败: {str(e)}"
            await self.send_text(error_msg)
            return False, error_msg, False

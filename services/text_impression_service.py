"""
文本印象服务 - 基于LLM的纯文本多维度印象管理
"""

from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime
import re

from ..models import UserImpression
from ..clients import LLMClient
from ..utils.constants import AFFECTION_LEVELS
from .database_service import DatabaseService
from src.common.logger import get_logger

logger = get_logger("impression_affection_text")


class TextImpressionService:
    """文本印象服务 - 基于LLM分析用户消息并更新多维度印象"""

    def __init__(self, llm_client: LLMClient, config: Dict[str, Any]):
        self.llm_client = llm_client
        self.config = config
        self.prompts_config = config.get("prompts", {})
        self.db_service = DatabaseService(config)

    async def build_impression(self, user_id: str, message: str, history_context: str = "") -> Tuple[bool, str]:
        """
        构建用户印象 - 基于LLM分析的多维度印象
        
        Args:
            user_id: 用户ID
            message: 当前消息
            history_context: 历史上下文
            
        Returns:
            (是否成功, 印象描述)
        """
        try:
            # 获取用户现有印象
            existing_impression = self._get_existing_impression(user_id)
            
            # 获取增强的历史上下文
            enhanced_context = await self._get_enhanced_context(user_id, history_context)
            
            # 生成更新提示词
            prompt = self._build_update_prompt(existing_impression, enhanced_context, message)
            
            # 调用LLM生成印象
            success, content = await self.llm_client.generate_impression_analysis(prompt)

            if not success:
                return False, f"LLM调用失败: {content}"

            # 解析响应
            impression_result = self._parse_impression_response(content)
            
            if impression_result:
                # 清理印象结果，确保纯中文输出
                cleaned_impression = self._clean_impression_text(impression_result)
                
                # 保存印象（使用更新方式）
                success = self._save_impression_update(user_id, cleaned_impression)
                if success:
                    logger.debug(f"印象更新成功")
                    return True, cleaned_impression
                else:
                    logger.warning(f"印象保存失败")
                    return False, "印象保存失败"
            else:
                logger.warning(f"印象解析失败: {content}")
                return False, "印象解析失败"

        except Exception as e:
            return False, f"构建印象失败: {str(e)}"

    async def _get_enhanced_context(self, user_id: str, existing_context: str) -> str:
        """
        获取增强的历史上下文（严格验证用户身份）
        
        Args:
            user_id: 用户ID
            existing_context: 现有的上下文
            
        Returns:
            增强后的上下文
        """
        try:
            # 检查是否启用数据库功能
            db_config = self.config.get("database", {})
            if not db_config.get("enabled", True):
                return existing_context
                
            # 如果数据库服务不可用，返回原有上下文
            if not self.db_service or not self.db_service.is_connected():
                return existing_context
            
            # 从配置获取参数
            history_config = self.config.get("history", {})
            hours_back = history_config.get("hours_back", 72)
            recent_hours = history_config.get("recent_hours", 24)
            
            # 获取用户聊天摘要（严格验证用户ID）
            summary = self.db_service.get_user_chat_summary(user_id, days_back=max(1, hours_back // 24))
            
            # 获取最近的互动（严格验证用户ID）
            recent_interactions = self.db_service.get_recent_interactions(user_id, hours_back=recent_hours)
            
            # 构建增强上下文
            enhanced_parts = []
            
            # 添加用户标识
            enhanced_parts.append(f"用户 {user_id} 的印象构建上下文")
            
            # 添加聊天摘要
            if "error" not in summary and summary.get("total_messages", 0) > 0:
                summary_text = f"用户统计: {hours_back}小时内共{summary['total_messages']}条消息"
                if summary.get("active_groups"):
                    groups = [g["name"] for g in summary["active_groups"][:3]]
                    summary_text += f", 主要活跃群组: {', '.join(groups)}"
                enhanced_parts.append(summary_text)
            
            # 添加最近互动
            verified_interactions = []
            # 从配置获取最近互动条数限制
            max_recent_interactions = self.config.get("history", {}).get("max_recent_interactions", 10)
            max_content_length = self.config.get("history", {}).get("max_content_length", 150)
            
            for interaction in recent_interactions[:max_recent_interactions]:
                if interaction.get("content") and len(interaction["content"].strip()) >= 2:
                    content = interaction["content"][:max_content_length]  # 使用配置的长度限制
                    hours_ago = interaction.get("hours_ago", 0)
                    verified_interactions.append(f"[{hours_ago:.1f}小时前] {content}")
            
            if verified_interactions:
                enhanced_parts.append(f"最近{recent_hours}小时内的对话记录:")
                enhanced_parts.extend(verified_interactions)
            
            # 合并原有上下文
            if existing_context:
                enhanced_parts.append("当前会话上下文:")
                enhanced_parts.append(existing_context)
            
            # 限制总长度
            enhanced_context = "\n".join(enhanced_parts)
            max_context_length = self.config.get("history", {}).get("max_context_length", 2000)  # 使用配置的上下文长度限制
            if len(enhanced_context) > max_context_length:
                enhanced_context = enhanced_context[:max_context_length] + "..."
            
            # 添加上下文来源说明
            enhanced_context += f"\n\n基于用户 {user_id} 的历史对话记录生成"
            
            return enhanced_context
            
        except Exception as e:
            # 发生错误时返回原有上下文
            logger.warning(f"获取历史上下文失败: {str(e)}")
            return existing_context

    def _build_prompt(self, history_context: str, message: str) -> str:
        """构建印象分析提示词"""
        template = self.prompts_config.get("impression_template", "").strip()

        # 从配置获取长度限制
        max_history_chars = self.config.get("prompts", {}).get("max_history_chars", 2000)
        max_message_chars = self.config.get("prompts", {}).get("max_message_chars", 500)

        if template:
            return template.format(
                history_context=history_context[:max_history_chars],
                message=message[:max_message_chars],
                context=""
            )

        # 默认提示词 - 使用配置的长度限制
        limited_history = history_context[:max_history_chars] if len(history_context) > max_history_chars else history_context
        limited_message = message[:max_message_chars] if len(message) > max_message_chars else message
        
        return f"请基于用户的聊天记录生成印象描述，用自然语言描述这个人的性格特点、兴趣爱好、交流方式等，长度50-100字。要求语言自然流畅，像朋友介绍这个人一样。如果信息不足，可以适当推测并用'似乎'、'看起来'等词。历史对话: {limited_history} 当前消息: {limited_message}"

    def _parse_impression_response(self, content: str) -> Optional[str]:
        """解析印象构建响应"""
        # 移除可能的JSON格式标记
        content = content.strip()
        
        # 如果是JSON格式，提取内容
        if content.startswith('{') and content.endswith('}'):
            try:
                import json
                data = json.loads(content)
                if 'impression' in data:
                    content = data['impression']
                elif 'description' in data:
                    content = data['description']
            except:
                pass
        
        # 移除可能的标记
        content = re.sub(r'^(印象描述|印象|描述)[:：]\s*', '', content, flags=re.IGNORECASE)
        content = re.sub(r'["""]', '', content)
        
        # 清理多余空白
        content = re.sub(r'\s+', ' ', content).strip()
        
        # 验证内容质量
        if len(content) < 10:
            return None
        
        if len(content) > 200:
            content = content[:200] + "..."
        
        return content

    def _clean_impression_text(self, impression: str) -> str:
        """
        清理印象文本，确保纯中文输出
        
        Args:
            impression: 原始印象文本
            
        Returns:
            清理后的印象文本
        """
        if not impression:
            return impression
        
        # 移除英文单词和缩写
        # 匹配英文单词（包括likely、maybe等）
        cleaned = re.sub(r'\b[a-zA-Z]+\b', '', impression)
        
        # 移除多余的标点符号
        cleaned = re.sub(r'[，,]{2,}', '，', cleaned)
        cleaned = re.sub(r'[。.]{2,}', '。', cleaned)
        cleaned = re.sub(r'\s+', '', cleaned)  # 移除所有空白
        
        # 移除开头和结尾的标点
        cleaned = cleaned.strip('，。、；;！!？?')
        
        # 确保句子通顺
        if cleaned and not cleaned.endswith(('。', '！', '？')):
            cleaned += '。'
        
        # 如果清理后内容太短，返回默认值
        if len(cleaned) < 15:
            return "该用户性格温和，交流友好，给人良好印象。"
        
        return cleaned

    def _save_impression(self, user_id: str, impression_text: str) -> bool:
        """
        保存用户印象到数据库（直接覆盖方式）
        
        Args:
            user_id: 用户ID
            impression_text: 印象文本
            
        Returns:
            是否保存成功
        """
        try:
            # 获取或创建用户印象记录
            impression, created = UserImpression.get_or_create(
                user_id=user_id,
                defaults={
                    'personality_traits': impression_text,
                    'updated_at': datetime.now()
                }
            )
            
            if not created:
                # 更新现有记录
                impression.personality_traits = impression_text
                impression.update_timestamps()
                impression.save()
            
            logger.debug(f"印象已保存: 用户 {user_id}, 印象: {impression_text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"保存印象失败: {str(e)}")
            return False
    
    def _get_existing_impression(self, user_id: str) -> Optional[str]:
        """
        获取用户现有印象
        
        Args:
            user_id: 用户ID
            
        Returns:
            现有印象文本，如果不存在则返回None
        """
        try:
            impression = UserImpression.select().where(
                UserImpression.user_id == user_id
            ).first()
            
            if impression and impression.personality_traits:
                return impression.personality_traits
            return None
            
        except Exception as e:
            logger.error(f"获取现有印象失败: {str(e)}")
            return None
    
    def _build_update_prompt(self, existing_impression: Optional[str], history_context: str, message: str) -> str:
        """
        构建增量更新印象的提示词
        
        Args:
            existing_impression: 现有印象
            history_context: 历史上下文
            message: 当前消息
            
        Returns:
            增量更新提示词
        """
        template = self.prompts_config.get("impression_template", "").strip()

        # 从配置获取长度限制
        max_history_chars = self.config.get("prompts", {}).get("max_history_chars", 2000)
        max_message_chars = self.config.get("prompts", {}).get("max_message_chars", 500)

        if template:
            return template.format(
                existing_impression=existing_impression or "暂无印象",
                history_context=history_context[:max_history_chars],
                message=message[:max_message_chars]
            )

        # 默认增量更新提示词
        if existing_impression:
            return f"""你是一个擅长人物印象分析的心理学家。现在需要基于新的对话信息，更新对用户的印象。

当前用户印象：{existing_impression}

历史对话上下文：{history_context[:max_history_chars] if len(history_context) > max_history_chars else history_context}

当前新消息：{message[:max_message_chars] if len(message) > max_message_chars else message}

请基于新信息更新用户印象，要求：
1. 保持原有印象中依然准确的部分
2. 根据新信息补充或修正印象
3. 语言要自然流畅，50-100字
4. 如果新信息与原有印象冲突，以新信息为准但保持表达委婉
5. 如果信息不足，可以用'似乎'、'看起来'等词

只返回更新后的印象描述，不要其他解释。"""
        else:
            # 如果没有现有印象，使用原始的印象构建提示词
            return self._build_prompt(history_context, message)
    
    def _save_impression_update(self, user_id: str, impression_text: str) -> bool:
        """
        保存用户印象到数据库（更新方式）
        
        Args:
            user_id: 用户ID
            impression_text: 印象文本
            
        Returns:
            是否保存成功
        """
        try:
            # 获取或创建用户印象记录
            impression, created = UserImpression.get_or_create(
                user_id=user_id,
                defaults={
                    'personality_traits': impression_text,
                    'updated_at': datetime.now()
                }
            )
            
            if not created:
                # 使用更新方式
                impression.set_impression_with_version(impression_text)
                impression.save()
                
                # 记录版本变化
                change_summary = impression.get_impression_change_summary()
                logger.debug(f"印象更新: 用户 {user_id}, {change_summary}")
            
            logger.debug(f"印象已保存: 用户 {user_id}, 印象: {impression_text[:50]}...")
            return True
            
        except Exception as e:
            logger.error(f"保存印象失败: {str(e)}")
            return False

    def get_impression(self, user_id: str) -> Optional[UserImpression]:
        """获取用户印象"""
        try:
            return UserImpression.get_or_create(user_id=user_id)[0]
        except Exception as e:
            logger.error(f"获取印象失败: {str(e)}")
            return None

    def search_impressions(self, keyword: str, limit: int = 10) -> List[UserImpression]:
        """搜索印象"""
        try:
            impressions = UserImpression.select().where(
                UserImpression.personality_traits.contains(keyword) |
                UserImpression.interests_hobbies.contains(keyword) |
                UserImpression.communication_style.contains(keyword)
            ).limit(limit)
            
            return list(impressions)
        except Exception as e:
            logger.error(f"搜索印象失败: {str(e)}")
            return []

    def get_all_impressions(self) -> List[UserImpression]:
        """获取所有印象"""
        try:
            return list(UserImpression.select())
        except Exception as e:
            logger.error(f"获取所有印象失败: {str(e)}")
            return []

    def get_impression(self, user_id: str) -> Optional[UserImpression]:
        """获取用户印象"""
        try:
            return UserImpression.select().where(
                UserImpression.user_id == user_id
            ).first()
        except Exception as e:
            print(f"获取印象失败: {str(e)}")
            return None

    async def update_dimension(self, user_id: str, dimension: str, content: str) -> Tuple[bool, str]:
        """更新特定维度的内容"""
        try:
            impression = self.get_impression(user_id)
            if not impression:
                return False, "用户不存在"

            impression.set_dimension(dimension, content)
            return True, f"{dimension}已更新: {content}"
        except Exception as e:
            return False, f"更新维度失败: {str(e)}"

    async def get_dimension(self, user_id: str, dimension: str) -> str:
        """获取特定维度的内容"""
        try:
            impression = self.get_impression(user_id)
            if not impression:
                return "用户不存在"
            
            return impression.get_dimension(dimension)
        except Exception as e:
            return f"获取维度失败: {str(e)}"

    def get_impression_summary(self, user_id: str) -> str:
        """获取印象摘要"""
        try:
            impression = self.get_impression(user_id)
            if not impression:
                return "暂无用户印象数据"
            
            # 返回自然语言印象
            natural_impression = impression.interests_hobbies  # 从复用的字段获取
            if natural_impression:
                return natural_impression
            else:
                return "用户印象正在构建中..."
                
        except Exception as e:
            return f"获取摘要失败: {str(e)}"
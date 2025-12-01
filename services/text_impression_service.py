"""
文本印象服务 - 基于LLM的纯文本多维度印象管理
"""

from typing import Dict, Any, Tuple, Optional, List
from datetime import datetime

from ..models import UserImpression
from ..clients import LLMClient
from ..utils.constants import AFFECTION_LEVELS


class TextImpressionService:
    """文本印象服务 - 基于LLM分析用户消息并更新多维度印象"""

    def __init__(self, llm_client: LLMClient, config: Dict[str, Any]):
        self.llm_client = llm_client
        self.config = config
        self.prompts_config = config.get("prompts", {})

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
            # 生成提示词
            prompt = self._build_prompt(history_context, message)
            
            # 调用LLM生成印象
            success, content = await self.llm_client.generate_impression_analysis(prompt)

            if not success:
                return False, f"LLM调用失败: {content}"

            # 解析结果
            impression_data = self._parse_impression_response(content)

            if not impression_data:
                return False, f"解析失败: {content}"

            # 保存到数据库
            await self._save_impression(user_id, impression_data, message, history_context)

            return True, impression_data.get("impression", "印象构建成功")

        except Exception as e:
            return False, f"构建印象失败: {str(e)}"

    def _build_prompt(self, history_context: str, message: str) -> str:
        """构建印象分析提示词"""
        template = self.prompts_config.get("impression_template", "").strip()

        if template:
            return template.format(
                history_context=history_context[:500],  # 限制历史上下文长度
                message=message[:200],  # 限制消息长度
                context=""
            )

        # 默认提示词 - 优化token使用
        # 限制历史上下文和消息长度以节省token
        limited_history = history_context[:300] if len(history_context) > 300 else history_context
        limited_message = message[:200] if len(message) > 200 else message
        
        return f"分析用户消息按8个维度生成印象，每项10字内，信息不足用待观察。只返回键值对格式：personality_traits:性格特征;interests_hobbies:兴趣爱好;communication_style:交流风格;emotional_tendencies:情感倾向;behavioral_patterns:行为模式;values_attitudes:价值观态度;relationship_preferences:关系偏好;growth_development:成长发展。历史: {limited_history};消息: {limited_message}"

    def _parse_impression_response(self, content: str) -> Dict[str, str]:
        """解析LLM响应"""
        import re
        import logging
        
        logger = logging.getLogger("impression_affection_system")
        
        try:
            # 清理内容
            content = content.strip()
            
            # 主要方法：解析键值对格式
            result = {}
            
            # 定义8个维度的解析模式
            patterns = {
                'personality_traits': r'personality_traits:\s*([^;]+)',
                'interests_hobbies': r'interests_hobbies:\s*([^;]+)',
                'communication_style': r'communication_style:\s*([^;]+)',
                'emotional_tendencies': r'emotional_tendencies:\s*([^;]+)',
                'behavioral_patterns': r'behavioral_patterns:\s*([^;]+)',
                'values_attitudes': r'values_attitudes:\s*([^;]+)',
                'relationship_preferences': r'relationship_preferences:\s*([^;]+)',
                'growth_development': r'growth_development:\s*([^;]+)'
            }
            
            # 提取各个维度
            for key, pattern in patterns.items():
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    if value and value != '待观察':
                        result[key] = value
                        logger.debug(f"提取到{key}: {value}")
            
            # 如果成功提取到至少一个维度，返回结果
            if result:
                logger.debug(f"解析结果: {result}")
                return result
            
            # 备用方法：处理IMPRESSION/REASON格式
            impression_match = re.search(r'IMPRESSION:\s*([^;]+)', content, re.IGNORECASE)
            if impression_match:
                impression_text = impression_match.group(1).strip()
                result['interests_hobbies'] = impression_text
                logger.debug(f"备用方法提取到IMPRESSION: {impression_text}")
                return result
            
            logger.warning(f"无法解析印象响应: {repr(content)}")
            return {}
            
        except Exception as e:
            logger.error(f"解析印象响应异常: {str(e)}")
            return {}

    async def _save_impression(self, user_id: str, impression_data: Dict[str, str], message: str, context: str):
        """保存印象数据到数据库"""
        try:
            # 获取或创建用户记录
            impression, created = UserImpression.get_or_create(
                user_id=user_id,
                defaults={
                    "affection_score": 50.0,
                    "affection_level": "一般",
                    "message_count": 0
                }
            )

            # 更新各个维度
            impression.personality_traits = impression_data.get("personality_traits", "")
            impression.interests_hobbies = impression_data.get("interests_hobbies", "")
            impression.communication_style = impression_data.get("communication_style", "")
            impression.emotional_tendencies = impression_data.get("emotional_tendencies", "")
            impression.behavioral_patterns = impression_data.get("behavioral_patterns", "")
            impression.values_attitudes = impression_data.get("values_attitudes", "")
            impression.relationship_preferences = impression_data.get("relationship_preferences", "")
            impression.growth_development = impression_data.get("growth_development", "")

            # 更新统计信息
            if created:
                impression.message_count = 1
            else:
                impression.message_count += 1

            impression.last_interaction = datetime.now()
            impression.update_timestamps()
            impression.save()

        except Exception as e:
            print(f"保存印象失败: {str(e)}")

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
            
            return impression.get_impression_summary()
        except Exception as e:
            return f"获取摘要失败: {str(e)}"
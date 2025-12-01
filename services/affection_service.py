"""
好感度更新服务 - 评估和更新用户好感度
"""

from typing import Dict, Any, Tuple
from datetime import datetime

from ..models import UserImpression
from ..clients import LLMClient
from ..utils.constants import AFFECTION_LEVELS


class AffectionService:
    """好感度更新服务"""

    def __init__(self, llm_client: LLMClient, config: Dict[str, Any]):
        self.llm_client = llm_client
        self.config = config
        self.prompts_config = config.get("prompts", {})
        self.increment_config = config.get("affection_increment", {})

        # 默认增幅配置
        self.friendly_increment = self.increment_config.get("friendly_increment", 2.0)
        self.neutral_increment = self.increment_config.get("neutral_increment", 0.5)
        self.negative_increment = self.increment_config.get("negative_increment", -3.0)

    async def update_affection(self, user_id: str, message: str) -> Tuple[bool, str]:
        """
        更新用户好感度

        Args:
            user_id: 用户ID
            message: 消息内容

        Returns:
            (是否成功, 结果描述)
        """
        try:
            # 评估评论类型
            comment_type, reason = await self._evaluate_comment_type(message)

            # 计算增幅
            increment = self._calculate_increment(comment_type)

            # 更新数据库
            new_score = await self._update_affection_score(user_id, increment)

            # 获取等级
            level = self._get_affection_level(new_score)

            result = f"好感度更新: {comment_type} (+{increment:.1f}) -> {new_score:.1f}/100 ({level})"
            return True, result

        except Exception as e:
            return False, f"更新好感度失败: {str(e)}"

    async def _evaluate_comment_type(self, message: str) -> Tuple[str, str]:
        """评估评论类型"""
        prompt = self._build_affection_prompt(message)

        success, content = await self.llm_client.generate_affection_analysis(prompt)

        if not success:
            raise Exception(f"LLM调用失败: {content}")

        result = self._parse_affection_response(content)

        if not result:
            return "neutral", "解析失败，默认为中性"

        return result.get("type", "neutral"), result.get("reason", "")

    def _build_affection_prompt(self, message: str) -> str:
        """构建好感度评估提示词"""
        template = self.prompts_config.get("affection_template", "").strip()

        if template:
            return template.format(message=message, context="")

        # 默认提示词 - 使用键值对格式
        return f"""你是一个情感分析师。请评估用户消息的情感倾向。

评估标准：
- friendly: 友善的评论（赞美、鼓励、感谢等）
- neutral: 中性的评论（客观陈述、信息性消息等）
- negative: 差劲的评论（批评、讽刺、攻击等）

回复要求：只返回键值对格式，不要包含其他内容

格式：
TYPE: friendly/neutral/negative;REASON: 评估原因;消息: {message}"""

    def _parse_affection_response(self, content: str) -> Dict[str, str]:
        """解析好感度响应 - 键值对格式"""
        import logging
        import re
        
        logger = logging.getLogger("impression_affection_system")
        
        # 清理内容
        content = content.strip()
        
        # 如果内容太短
        if len(content) < 10:
            logger.error(f"LLM响应太短: {repr(content)}")
            return {}
        
        # 使用正则表达式提取 TYPE 和 REASON
        type_match = re.search(r'TYPE:\s*(\w+)', content, re.IGNORECASE)
        reason_match = re.search(r'REASON:\s*(.+?)(?:\n|;消息:|$)', content, re.IGNORECASE)
        
        result = {}
        if type_match:
            result["type"] = type_match.group(1).strip().lower()
        if reason_match:
            result["reason"] = reason_match.group(1).strip()
        
        if result:
            logger.debug(f"提取到好感度数据: {result}")
            return result
        
        logger.error(f"无法提取好感度数据: {repr(content)}")
        return {}

    def _calculate_increment(self, comment_type: str) -> float:
        """计算好感度增幅"""
        increments = {
            "friendly": self.friendly_increment,
            "negative": self.negative_increment,
            "neutral": self.neutral_increment
        }
        return increments.get(comment_type, self.neutral_increment)

    async def _update_affection_score(self, user_id: str, increment: float) -> float:
        """更新好感度分数"""
        impression, created = UserImpression.get_or_create(
            user_id=user_id,
            defaults={
                "affection_score": 50.0,
                "affection_level": "一般",
                "message_count": 0
            }
        )

        if created:
            current_score = 50.0
        else:
            current_score = impression.affection_score or 50.0

        # 计算新分数
        new_score = current_score + increment
        new_score = max(0, min(100, new_score))

        # 更新记录
        impression.affection_score = new_score
        impression.affection_level = self._get_affection_level(new_score)
        impression.message_count += 1
        impression.update_timestamps()
        impression.save()

        return new_score

    def _get_affection_level(self, score: float) -> str:
        """根据分数获取好感度等级"""
        for (min_score, max_score), level in AFFECTION_LEVELS.items():
            if min_score <= score <= max_score:
                return level
        return "一般"

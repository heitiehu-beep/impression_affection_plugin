"""
好感度更新服务 v3.0.0
"""

import json
import re
from typing import Dict, Any, Tuple
from datetime import datetime

from ..models import UserImpression
from ..clients import LLMClient
from src.common.logger import get_logger
from ..utils.constants import AFFECTION_LEVELS, DIFFICULTY_LEVELS, AFFECTION_INCREMENTS


class AffectionService:
    """好感度更新服务 - 支持难度系统和固定好感度"""

    def __init__(self, llm_client: LLMClient, config: Dict[str, Any]):
        self.llm_client = llm_client
        self.config = config
        self.logger = get_logger(__name__)

        # 从配置文件加载各模块配置
        self.prompts_config = config.get("prompts", {})
        self.increment_config = config.get("affection_increment", {})
        self.affection_config = config.get("affection", {})
        self.difficulty_config = config.get("difficulty", {})

        # 加载初始好感度分数（默认50.0）
        self.initial_score = self.affection_config.get("initial_score", 50.0)

        # 加载固定好感度列表（JSON格式）
        fixed_list_str = self.affection_config.get("fixed_affection_list", "{}")
        try:
            self.fixed_affection = json.loads(fixed_list_str)
            if not isinstance(self.fixed_affection, dict):
                self.fixed_affection = {}
                self.logger.warning("固定好感度列表格式错误，应为字典格式")
        except Exception as e:
            self.fixed_affection = {}
            self.logger.warning(f"固定好感度列表解析失败: {fixed_list_str}, 错误: {e}")

        # 加载全局难度设置
        self.default_difficulty = self.difficulty_config.get("level", "normal")
        self.allow_difficulty_change = self.difficulty_config.get("allow_user_change", True)

    async def update_affection(self, user_id: str, message: str) -> Tuple[bool, str]:
        """
        更新用户好感度 - 增强版本，支持难度系统和固定好感度
        修复：Nightmare 模式增加双重验证，防止负面消息被误判为加分

        Args:
            user_id: 用户ID
            message: 消息内容

        Returns:
            (是否成功, 结果描述)
        """
        try:
            # 检查是否是固定好感度用户（固定好感度不会被聊天改变）
            if user_id in self.fixed_affection:
                fixed_score = float(self.fixed_affection[user_id])

                # 获取或创建记录
                impression, created = UserImpression.get_or_create(
                    user_id=user_id,
                    defaults={
                        "affection_score": fixed_score,
                        "affection_level": self._get_affection_level(fixed_score),
                        "difficulty_level": self.default_difficulty
                    }
                )

                # 如果不是新建的，强制更新为固定值（防止被修改）
                if not created:
                    impression.affection_score = fixed_score
                    impression.affection_level = self._get_affection_level(fixed_score)
                    impression.save()

                return True, f"固定好感度用户 {user_id}: {fixed_score}分（不会被聊天改变）"

            # 普通用户：使用配置的初始值创建
            impression, created = UserImpression.get_or_create(
                user_id=user_id,
                defaults={
                    "affection_score": self.initial_score,
                    "affection_level": self._get_affection_level(self.initial_score),
                    "difficulty_level": self.default_difficulty
                }
            )

            # 获取用户的难度等级
            difficulty = impression.difficulty_level

            # 获取难度配置（从常量加载，但增幅使用配置文件中的覆盖值）
            difficulty_config = DIFFICULTY_LEVELS.get(difficulty, DIFFICULTY_LEVELS["normal"])
            # 加载难度对应的增幅配置（如果配置文件中存在则覆盖默认值）
            difficulty_increments = AFFECTION_INCREMENTS.get(difficulty, AFFECTION_INCREMENTS["normal"]).copy()

            # 允许通过配置文件覆盖特定难度的增幅值
            if difficulty in self.increment_config:
                difficulty_increments.update(self.increment_config[difficulty])

            multiplier = difficulty_config.get("multiplier", 1.0)

            # 步骤 1: 基础情感评估（友好/中性/负面）
            comment_type, base_reason = await self._evaluate_comment_type(message)
            old_score = impression.affection_score

            # 步骤 2: 根据难度计算最终增量
            if difficulty == "nightmare":
                # Nightmare 模式：双重评估机制（关键修复）
                nightmare_verdict, nightmare_reason = await self._evaluate_nightmare_mode(message)

                # 修复 1: 如果基础评估为 negative，强制扣分（无视 Nightmare 评估结果）
                if comment_type == "negative":
                    increment = difficulty_increments.get("strong_disagreement", -5.0)
                    reason = f"Nightmare模式[强制惩罚]: 基础评估为负面({base_reason})"

                # 修复 2: 如果基础是 friendly，但 Nightmare 识破伪装（识别出虚伪/空洞）
                elif comment_type == "friendly" and nightmare_verdict in ["disagreement", "minor_disagreement"]:
                    increment = difficulty_increments.get("minor_disagreement", -2.0)
                    reason = f"Nightmare模式[识破伪装]: 表面友好但实质空洞 | {nightmare_reason}"

                # 修复 3: Nightmare 评估为 disagreement（内容空洞/敷衍）
                elif nightmare_verdict == "disagreement":
                    increment = difficulty_increments.get("strong_disagreement", -5.0)
                    reason = f"Nightmare模式[内容低质]: {nightmare_reason}"

                elif nightmare_verdict == "minor_disagreement":
                    increment = difficulty_increments.get("minor_disagreement", -2.0)
                    reason = f"Nightmare模式[略有欠缺]: {nightmare_reason}"

                elif nightmare_verdict == "strong_agreement":
                    # 只有双重验证通过才给奖励：基础友好 + Nightmare 认可
                    if comment_type == "friendly":
                        increment = difficulty_increments.get("strong_agreement", 2.0)
                        reason = f"Nightmare模式[深度认可]: {nightmare_reason}"
                    else:
                        # 基础不友好，即使 Nightmare 认可有深度，也不给分（轻微惩罚）
                        increment = -0.5
                        reason = f"Nightmare模式[态度不佳]: 虽有见地但态度不友善 | {nightmare_reason}"
                else:
                    # normal 或其他，Nightmare 模式下平庸即罪
                    increment = -0.5
                    reason = f"Nightmare模式[平庸即罪]: 缺乏亮点 | {nightmare_reason}"

            else:
                # 普通难度：使用基础评估结果
                increment = self._calculate_increment(comment_type, difficulty, difficulty_increments)
                reason = base_reason

            # 应用难度倍数
            increment = increment * multiplier

            # 确保分数在 0-100 范围内
            new_score = old_score + increment
            new_score = max(0, min(100, new_score))

            # 保存更新
            impression.affection_score = new_score
            impression.affection_level = self._get_affection_level(new_score)
            impression.message_count += 1
            impression.update_timestamps()
            impression.save()

            # 构建结果消息
            result = f"{reason}\n({old_score:.1f} -> {new_score:.1f})\n"
            result += f"当前好感度: {impression.affection_level} ({new_score:.1f}/100)\n"
            result += f"难度: {difficulty_config['name']}"

            return True, result

        except Exception as e:
            self.logger.error(f"更新好感度失败: {str(e)}")
            return False, f"更新好感度失败: {str(e)}"

    async def _evaluate_comment_type(self, message: str) -> Tuple[str, str]:
        """评估评论类型（基础情感分析）"""
        prompt = self._build_affection_prompt(message)

        success, content = await self.llm_client.generate_affection_analysis(prompt)

        if not success:
            self.logger.warning(f"LLM调用失败: {content}")
            return "neutral", "评估失败，默认为中性"

        result = self._parse_affection_response(content)

        if not result:
            return "neutral", "解析失败，默认为中性"

        return result.get("type", "neutral"), result.get("reason", "")

    async def _evaluate_nightmare_mode(self, message: str) -> Tuple[str, str]:
        """
        Nightmare 模式特殊评估 - 严格扣分机制
        修复：增加负面关键词预检查和内容质量校验
        """
        # 预检查 1: 负面关键词检测（快速路径）
        negative_keywords = ['缺乏', '没有', '空洞', '敷衍', '无效', '差劲', '讨厌',
                             '恶心', '垃圾', '废话', '无聊', '愚蠢', '错误', '反对']
        if any(keyword in message for keyword in negative_keywords):
            return "disagreement", "检测到负面关键词或批评语气，判定为无效沟通"

        # 预检查 2: 消息长度检查（太短的内容直接判为敷衍）
        if len(message.strip()) < 5:
            return "disagreement", "消息过短，缺乏实质内容"

        # 使用配置文件中的提示词模板（如果存在）
        custom_prompt = self.prompts_config.get("nightmare_evaluation_prompt", "")

        if custom_prompt:
            prompt = custom_prompt.format(message=message)
        else:
            # 默认严格提示词
            prompt = f"""你是一个极其严厉的评论家。请严格评估用户消息的质量和价值。

消息内容: "{message}"

评估标准（极其严格，几乎不会给高分）：
- strong_agreement: ONLY 当用户表达了极其深刻、真挚、有建设性的观点，展现出极高的情商和独特见解。普通赞美或简单回应绝对不算。
- normal: 日常寒暄、普通对话、中性陈述、简单分享。
- minor_disagreement: 略显敷衍、缺乏深度、轻微的负面情绪、流于表面的回应。
- disagreement: 明显敷衍、虚伪、发泄情绪、无意义抱怨、批评指责、完全缺乏实质内容、逻辑混乱。

重要规则（必须遵守）：
1. 如果消息包含批评、抱怨、指责、负面词汇 → 必须判定为 disagreement
2. 如果消息内容空洞、没有营养、纯粹发泄 → 必须判定为 disagreement  
3. 如果消息是在评价"某事物缺乏XX"（如"这句话没有内容"）→ 这是批评，必须判定为 disagreement
4. 只有真正深刻、有见地、有建设性的观点才能给 strong_agreement（这种情况极少）

只返回键值对格式：
VERDICT: strong_agreement/normal/minor_disagreement/disagreement;REASON: 简要原因（必须具体指出问题）;"""

        success, content = await self.llm_client.generate_affection_analysis(prompt)

        if not success:
            # LLM 失败时保守处理：扣分
            return "disagreement", f"评估失败，保守处理: {content}"

        result = self._parse_affection_response(content)

        if result:
            verdict_type = result.get("type", "normal")
            reason = result.get("reason", "未提供原因")

            # 映射到标准值
            verdict_map = {
                "strong_agreement": "strong_agreement",
                "normal": "normal",
                "minor_disagreement": "minor_disagreement",
                "disagreement": "disagreement",
                "negative": "disagreement",  # 兼容基础评估的 negative
            }
            verdict = verdict_map.get(verdict_type, "normal")

            # 二次校验：如果原因中包含负面描述，但 verdict 是 strong_agreement，强制降级
            negative_indicators = ['缺乏', '没有', '空洞', '敷衍', '无效', '批评', '负面',
                                   '差劲', '不好', '错误', '反对', '不同意']
            if verdict == "strong_agreement" and any(word in reason for word in negative_indicators):
                verdict = "disagreement"
                reason = f"内容质量检测失败，强制降级 | 原因为: {reason}"

            return verdict, reason

        # 解析失败时保守处理
        return "disagreement", "解析失败，保守处理"

    def _build_affection_prompt(self, message: str) -> str:
        """构建好感度评估提示词"""
        template = self.prompts_config.get("affection_template", "").strip()

        if template:
            return template.format(message=message, context="")

        # 默认提示词
        return f"""你是一个情感分析师。请评估用户消息的情感倾向。

评估标准：
- friendly: 友善的评论（赞美、鼓励、感谢、积极分享等）
- neutral: 中性的评论（客观陈述、信息性消息等）
- negative: 差劲的评论（批评、讽刺、攻击、抱怨等）

回复要求：只返回键值对格式，不要包含其他内容

格式：
TYPE: friendly/neutral/negative;REASON: 评估原因;消息: {message}"""

    def _parse_affection_response(self, content: str) -> Dict[str, str]:
        """解析好感度响应 - 支持 TYPE 和 VERDICT 两种键名"""
        content = content.strip()

        if len(content) < 5:
            return {}

        # 使用正则表达式提取 TYPE/VERDICT 和 REASON
        type_match = re.search(r'(?:TYPE|VERDICT):\s*(\w+)', content, re.IGNORECASE)
        reason_match = re.search(r'REASON:\s*(.+?)(?:\n|;消息:|$)', content, re.IGNORECASE)

        result = {}
        if type_match:
            result["type"] = type_match.group(1).strip().lower()
        if reason_match:
            result["reason"] = reason_match.group(1).strip()

        return result if result else {}

    def _calculate_increment(self, comment_type: str, difficulty: str, increments: Dict[str, float]) -> float:
        """
        计算好感度增幅

        Args:
            comment_type: 评论类型 (friendly/neutral/negative)
            difficulty: 难度等级
            increments: 难度对应的增幅配置（从配置文件加载）
        """
        # 使用传入的 increments（已合并配置文件覆盖值）
        increment = increments.get(comment_type, increments.get("neutral", 0))
        return increment

    def _get_affection_level(self, score: float) -> str:
        """根据分数获取好感度等级"""
        for (min_score, max_score), level in AFFECTION_LEVELS.items():
            if min_score <= score <= max_score:
                return level
        return "一般"

    def set_difficulty(self, user_id: str, difficulty_level: str) -> Tuple[bool, str]:
        """设置用户难度等级"""
        if not self.allow_difficulty_change:
            return False, "配置不允许改变难度等级"

        valid_levels = list(DIFFICULTY_LEVELS.keys())
        if difficulty_level not in valid_levels:
            return False, f"无效的难度等级: {difficulty_level}，可选: {valid_levels}"

        try:
            impression, _ = UserImpression.get_or_create(user_id=user_id)
            impression.set_difficulty(difficulty_level)
            impression.save()

            config = DIFFICULTY_LEVELS[difficulty_level]
            return True, f"难度已设置为: {config['name']} - {config['description']}"
        except Exception as e:
            return False, f"设置难度失败: {str(e)}"

    def get_affection_summary(self, user_id: str) -> str:
        """获取用户好感度摘要"""
        try:
            impression = UserImpression.get_or_none(UserImpression.user_id == user_id)
            if not impression:
                return "该用户还没有好感度记录"

            difficulty_config = DIFFICULTY_LEVELS.get(impression.difficulty_level, DIFFICULTY_LEVELS["normal"])

            summary = f"当前好感度: {impression.affection_score:.1f}/100 ({impression.affection_level})\n"
            summary += f"难度等级: {difficulty_config['name']}\n"
            summary += f"消息统计: {impression.message_count} 条\n"
            summary += f"印象版本: {impression.impression_version}"

            return summary
        except Exception as e:
            return f"获取失败: {str(e)}"

    def get_difficulty_info(self, user_id: str) -> Dict[str, Any]:
        """获取用户的难度信息"""
        try:
            impression = UserImpression.get_or_none(UserImpression.user_id == user_id)
            if impression:
                difficulty = impression.difficulty_level
                config = DIFFICULTY_LEVELS.get(difficulty, DIFFICULTY_LEVELS["normal"])
                return {
                    "level": difficulty,
                    "name": config["name"],
                    "description": config["description"],
                    "multiplier": config.get("multiplier", 1.0)
                }
            else:
                return {
                    "level": self.default_difficulty,
                    "name": DIFFICULTY_LEVELS[self.default_difficulty]["name"],
                    "description": DIFFICULTY_LEVELS[self.default_difficulty]["description"],
                    "multiplier": DIFFICULTY_LEVELS[self.default_difficulty].get("multiplier", 1.0)
                }
        except Exception as e:
            self.logger.error(f"获取难度信息失败: {str(e)}")
            return {
                "level": self.default_difficulty,
                "name": DIFFICULTY_LEVELS[self.default_difficulty]["name"],
                "description": DIFFICULTY_LEVELS[self.default_difficulty]["description"],
                "multiplier": DIFFICULTY_LEVELS[self.default_difficulty].get("multiplier", 1.0)
            }

    def list_all_difficulties(self) -> Dict[str, Dict[str, str]]:
        """列出所有难度等级"""
        return {
            key: {
                "name": value["name"],
                "description": value["description"]
            }
            for key, value in DIFFICULTY_LEVELS.items()
        }

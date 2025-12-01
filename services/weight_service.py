"""
权重评估服务 - 评估消息权重，筛选高价值消息
"""

from typing import Dict, Any, Tuple, Optional
from datetime import datetime
from collections import defaultdict

from ..clients import LLMClient


class WeightService:
    """权重评估服务"""

    def __init__(self, llm_client: LLMClient, config: Dict[str, Any]):
        self.llm_client = llm_client
        self.config = config
        self.weight_config = config.get("weight_filter", {})
        self.prompts_config = config.get("prompts", {})

        # 阈值配置
        self.high_threshold = self.weight_config.get("high_weight_threshold", 70.0)
        self.medium_threshold = self.weight_config.get("medium_weight_threshold", 40.0)
        self.filter_mode = self.weight_config.get("filter_mode", "selective")
        
        # 内存存储 - 按用户存储消息权重记录
        self.message_weights = defaultdict(list)  # {user_id: [(message_id, score, level, timestamp), ...]}

    async def evaluate_message(self, user_id: str, message_id: str, message: str, context: str = "") -> Tuple[bool, float, str]:
        """
        评估消息权重

        Args:
            user_id: 用户ID
            message_id: 消息ID
            message: 消息内容
            context: 上下文

        Returns:
            (是否成功, 权重分数, 权重等级)
        """
        try:
            # 检查消息是否已存在
            user_messages = self.message_weights.get(user_id, [])
            for msg_record in user_messages:
                if msg_record[0] == message_id:  # message_id matches
                    return True, msg_record[1], msg_record[2]  # score, level

            # 生成提示词
            prompt = self._build_weight_prompt(message, context)

            # 调用LLM评估
            success, content = await self.llm_client.generate_weight_evaluation(prompt)

            if not success:
                # 评估失败，使用默认权重
                return self._save_default_weight(user_id, message_id, message, context)

            # 解析结果
            result = self._parse_weight_response(content)

            if not result:
                # 解析失败，使用默认权重
                return self._save_default_weight(user_id, message_id, message, context)

            weight_score = float(result.get("weight_score", 0.0))
            weight_level = result.get("weight_level", "low")

            # 保存到内存
            self._save_weight(user_id, message_id, message, context, weight_score, weight_level)

            return True, weight_score, weight_level

        except Exception as e:
            return False, 0.0, f"评估权重失败: {str(e)}"

    def _build_weight_prompt(self, message: str, context: str) -> str:
        """构建权重评估提示词"""
        template = self.prompts_config.get("weight_evaluation_prompt", "").strip()

        if template:
            return template.format(message=message, context=context)

        # 默认提示词 - 使用键值对格式
        return f"""评估消息权重（0-100），用于判断是否用于构建用户印象。权重评估标准：高权重(70-100): 包含重要个人信息、兴趣爱好、价值观、情感表达、深度思考、独特观点、生活经历分享；中权重(40-69): 一般日常对话、简单提问、客观陈述、基础信息交流；低权重(0-39): 简单问候、客套话、无实质内容的互动、表情符号。特别注意：分享个人喜好（如书籍、音乐、电影等）、询问对方偏好、表达个人观点都应该给予较高权重。只返回键值对格式：WEIGHT_SCORE: 分数;WEIGHT_LEVEL: high/medium/low;REASON: 评估原因;消息: {message};上下文: {context}"""

    def _parse_weight_response(self, content: str) -> Optional[Dict[str, Any]]:
        """解析权重评估响应 - 支持键值对和JSON两种格式"""
        import logging
        import re
        import json
        
        logger = logging.getLogger("impression_affection_system")
        
        # 清理内容
        content = content.strip()
        
        # 如果内容太短
        if len(content) < 10:
            logger.error(f"LLM响应太短: {repr(content)}")
            return None
        
        # 方法1: 尝试提取键值对格式
        score_match = re.search(r'WEIGHT_SCORE:\s*([\d.]+)', content, re.IGNORECASE)
        level_match = re.search(r'WEIGHT_LEVEL:\s*(\w+)', content, re.IGNORECASE)
        reason_match = re.search(r'REASON:\s*(.+?)(?:\n|;消息:|$)', content, re.IGNORECASE)
        
        result = {}
        if score_match:
            try:
                result["weight_score"] = float(score_match.group(1))
            except:
                result["weight_score"] = 0.0
        if level_match:
            result["weight_level"] = level_match.group(1).strip().lower()
        if reason_match:
            result["reason"] = reason_match.group(1).strip()
        
        if result and "weight_score" in result:
            logger.debug(f"提取到键值对格式权重数据: {result}")
            return result
        
        # 方法2: 尝试解析JSON格式（作为后备）
        try:
            # 查找JSON部分（从第一个{到最后一个}）
            start = content.find('{')
            end = content.rfind('}')
            
            if start >= 0 and end >= 0 and end > start:
                json_str = content[start:end+1]
                json_result = json.loads(json_str)
                
                if isinstance(json_result, dict) and "weight_score" in json_result:
                    logger.debug(f"提取到JSON格式权重数据: {json_result}")
                    return json_result
        except json.JSONDecodeError as e:
            logger.debug(f"JSON解析失败: {e}")
        
        logger.error(f"无法提取权重数据: {repr(content)}")
        return None

    def _save_weight(self, user_id: str, message_id: str, message: str, context: str, weight_score: float, weight_level: str):
        """保存权重评估结果到内存"""
        self.message_weights[user_id].append((
            message_id, 
            weight_score, 
            weight_level, 
            datetime.now(),
            message[:100],  # 保存消息内容的前100字符
            context[:100]   # 保存上下文的前100字符
        ))
        
        # 限制每个用户最多保存100条记录
        if len(self.message_weights[user_id]) > 100:
            self.message_weights[user_id] = self.message_weights[user_id][-100:]

    def _save_default_weight(self, user_id: str, message_id: str, message: str, context: str) -> Tuple[bool, float, str]:
        """保存默认权重"""
        # 简单规则：消息长度大于20字认为是中权重
        if len(message) > 20:
            weight_score = 50.0
            weight_level = "medium"
        else:
            weight_score = 20.0
            weight_level = "low"

        self._save_weight(user_id, message_id, message, context, weight_score, weight_level)
        return True, weight_score, weight_level

    def get_filtered_messages(self, user_id: str, limit: int = 10) -> Tuple[str, list]:
        """
        获取筛选后的消息用于印象构建

        Args:
            user_id: 用户ID
            limit: 最大消息数

        Returns:
            (上下文字符串, 消息ID列表)
        """
        if self.filter_mode == "disabled":
            return "", []

        # 获取用户的消息记录
        user_messages = self.message_weights.get(user_id, [])
        
        # 根据筛选模式过滤消息
        filtered_messages = []
        for msg_record in user_messages:
            message_id, weight_score, weight_level, timestamp, message_content, context = msg_record
            
            if self.filter_mode == "selective":
                if weight_score >= self.high_threshold:
                    filtered_messages.append(msg_record)
            elif self.filter_mode == "balanced":
                if weight_score >= self.medium_threshold:
                    filtered_messages.append(msg_record)
            else:  # 默认包含所有消息
                filtered_messages.append(msg_record)

        # 按时间倒序排列，取前limit条
        filtered_messages.sort(key=lambda x: x[3], reverse=True)  # 按timestamp排序
        filtered_messages = filtered_messages[:limit]

        if not filtered_messages:
            return "", []

        # 构建上下文
        contexts = []
        message_ids = []

        for msg_record in filtered_messages:
            message_id, weight_score, weight_level, timestamp, message_content, context = msg_record
            
            context_str = f"[{timestamp.strftime('%m-%d %H:%M')}] {message_content}"
            if weight_score > 0:
                context_str += f" (权重: {weight_score:.1f}, 等级: {weight_level})"
            contexts.append(context_str)
            message_ids.append(message_id)

        result = f"\n\n最近对话记录 (共 {len(contexts)} 条):\n" + "\n".join(contexts)

        return result, message_ids
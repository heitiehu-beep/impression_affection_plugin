import time
import json
import asyncio
import os
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
import uuid

from src.plugin_system import (
    BasePlugin,
    register_plugin,
    BaseTool,
    BaseAction,
    BaseCommand,
    ComponentInfo,
    ConfigField,
    ToolParamType,
    ActionActivationType,
)
from src.common.logger import get_logger
from peewee import (
    Model,
    TextField,
    FloatField,
    IntegerField,
    DateTimeField,
    BigIntegerField,
    BooleanField,
    fn,
    SqliteDatabase,
)


logger = get_logger("impression_affection_system")


# 独立数据库连接
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(PLUGIN_DIR, "impression_affection_data.db")
plugin_db = SqliteDatabase(DB_PATH)


# 数据库模型
class UserImpression(Model):
    """用户印象模型"""
    user_id = TextField(index=True)
    impression_text = TextField()  # 自然语言描述
    affection_score = FloatField()  # 好感度分数(0-100)
    affection_level = TextField()  # 等级名称

    # 向量存储
    impression_vector = TextField()  # JSON序列化
    context_vector = TextField(null=True)

    # 上下文信息
    context = TextField()
    message_count = IntegerField(default=1)

    # 时间戳
    created_time = DateTimeField(default=datetime.now)
    updated_time = DateTimeField(default=datetime.now)
    last_update_time = DateTimeField(default=datetime.now)

    class Meta:
        database = plugin_db
        table_name = "user_impressions"


class UserMessageState(Model):
    """用户消息状态跟踪（增量处理）"""
    user_id = TextField(unique=True, index=True)
    last_message_id = TextField(null=True)
    last_message_time = DateTimeField(null=True)
    impression_update_count = IntegerField(default=0)
    affection_update_count = IntegerField(default=0)
    total_messages = BigIntegerField(default=0)
    processed_messages = BigIntegerField(default=0)

    class Meta:
        database = plugin_db
        table_name = "user_message_state"


class ImpressionMessageRecord(Model):
    """印象构建时处理的消息记录（用于去重）"""
    user_id = TextField(index=True)
    message_id = TextField(index=True)
    impression_id = TextField(null=True)  # 对应的印象记录ID
    processed_time = DateTimeField(default=datetime.now)

    class Meta:
        database = plugin_db
        table_name = "impression_message_records"
        indexes = (
            (('user_id', 'message_id'), True),  # 复合唯一索引
        )


class UserMessage(Model):
    """用户消息记录（用于权重筛选）"""
    user_id = TextField(index=True)
    message_id = TextField(index=True)
    message_content = TextField()
    context = TextField()
    weight_score = FloatField(default=0.0)  # 权重分数
    weight_level = TextField(default="low")  # 权重等级: high, medium, low
    is_filtered = BooleanField(default=False)  # 是否被过滤
    timestamp = DateTimeField(default=datetime.now)

    class Meta:
        database = plugin_db
        table_name = "user_messages"
        indexes = (
            (('user_id', 'message_id'), True),  # 复合唯一索引
        )


# 好感度等级映射
AFFECTION_LEVELS = {
    (90, 100): "非常好",
    (80, 89): "很好",
    (70, 79): "较好",
    (50, 69): "一般",
    (30, 49): "较差",
    (10, 29): "很差",
    (0, 9): "非常差",
}


def get_affection_level(score: float) -> str:
    """根据分数获取好感度等级"""
    for (min_score, max_score), level in AFFECTION_LEVELS.items():
        if min_score <= score <= max_score:
            return level
    return "一般"


# 独立模型客户端
class IndependentModelClient:
    """插件独立模型客户端，不依赖主程序配置"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.llm_config = config.get("llm_provider", {})
        self.embedding_config = config.get("embedding_provider", {})

    async def generate_impression_analysis(self, prompt: str) -> Tuple[bool, str]:
        """使用LLM分析印象"""
        try:
            provider_type = self.llm_config.get("provider_type", "openai")

            if provider_type == "openai":
                return await self._openai_generate(prompt)
            elif provider_type == "custom":
                return await self._custom_generate(prompt)
            else:
                return False, f"不支持的提供商类型: {provider_type}"

        except Exception as e:
            logger.error(f"LLM调用失败: {str(e)}")
            return False, f"LLM调用失败: {str(e)}"

    async def _openai_generate(self, prompt: str) -> Tuple[bool, str]:
        """使用OpenAI格式API"""
        try:
            import openai

            client = openai.AsyncOpenAI(
                api_key=self.llm_config.get("api_key"),
                base_url=self.llm_config.get("base_url") or "https://api.openai.com/v1"
            )

            logger.info(f"LLM模型: {self.llm_config.get('model_id')}")
            
            response = await client.chat.completions.create(
                model=self.llm_config.get("model_id"),
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=200
            )

            content = response.choices[0].message.content
            logger.info(f"LLM分析完成，内容长度: {len(content)}")
            return True, content

        except Exception as e:
            logger.error(f"ERROR OpenAI API调用失败: {str(e)}")
            return False, f"OpenAI API调用失败: {str(e)}"

    async def _custom_generate(self, prompt: str) -> Tuple[bool, str]:
        """使用自定义API"""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                logger.info(f"自定义LLM模型: {self.llm_config.get('model_id')}")
                
                response = await client.post(
                    self.llm_config.get("api_endpoint"),
                    headers={
                        "Authorization": f"Bearer {self.llm_config.get('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.llm_config.get("model_id"),
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.3,
                        "max_tokens": 200
                    }
                )

                response.raise_for_status()
                result = response.json()

                # 根据不同API格式解析
                if "choices" in result:
                    content = result["choices"][0]["message"]["content"]
                elif "content" in result:
                    content = result["content"]
                else:
                    return False, "API返回格式未知"

                logger.info(f"自定义LLM分析完成，内容长度: {len(content)}")
                return True, content

        except Exception as e:
            logger.error(f"ERROR 自定义API调用失败: {str(e)}")
            return False, f"自定义API调用失败: {str(e)}"

    async def generate_embedding(self, text: str) -> Tuple[bool, List[float], str]:
        """使用嵌入模型生成向量"""
        try:
            logger.info(f"正在生成嵌入向量，文本长度: {len(text)}")
            
            provider_type = self.embedding_config.get("provider_type", "openai")

            if provider_type == "openai":
                return await self._openai_embedding(text)
            elif provider_type == "custom":
                return await self._custom_embedding(text)
            else:
                return False, [], f"不支持的嵌入提供商类型: {provider_type}"

        except Exception as e:
            logger.error(f"ERROR 嵌入生成失败: {str(e)}")
            return False, [], f"嵌入生成失败: {str(e)}"

    async def _openai_embedding(self, text: str) -> Tuple[bool, List[float], str]:
        """使用OpenAI嵌入模型"""
        try:
            import openai

            client = openai.AsyncOpenAI(
                api_key=self.embedding_config.get("api_key"),
                base_url=self.embedding_config.get("base_url") or "https://api.openai.com/v1"
            )

            model_id = self.embedding_config.get("model_id")
            logger.info(f"嵌入模型: {model_id}")

            response = await client.embeddings.create(
                model=model_id,
                input=text
            )

            embedding = response.data[0].embedding
            dimensions = len(embedding)
            
            logger.info(f"嵌入生成成功，向量维度: {dimensions}")
            return True, embedding, f"成功生成{dimensions}维向量"

        except Exception as e:
            logger.error(f"ERROR OpenAI嵌入API调用失败: {str(e)}")
            return False, [], f"OpenAI嵌入API调用失败: {str(e)}"

    async def _custom_embedding(self, text: str) -> Tuple[bool, List[float], str]:
        """使用自定义嵌入API"""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30) as client:
                model_id = self.embedding_config.get("model_id")
                logger.info(f"自定义嵌入模型: {model_id}")
                
                response = await client.post(
                    self.embedding_config.get("api_endpoint"),
                    headers={
                        "Authorization": f"Bearer {self.embedding_config.get('api_key')}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model_id,
                        "input": text
                    }
                )

                response.raise_for_status()
                result = response.json()

                # 根据不同API格式解析
                if "data" in result and len(result["data"]) > 0:
                    embedding = result["data"][0]["embedding"]
                elif "embedding" in result:
                    embedding = result["embedding"]
                else:
                    return False, [], "API返回格式未知"

                dimensions = len(embedding)
                logger.info(f"自定义嵌入生成成功，向量维度: {dimensions}")
                return True, embedding, f"成功生成{dimensions}维向量"

        except Exception as e:
            logger.error(f"ERROR 自定义嵌入API调用失败: {str(e)}")
            return False, [], f"自定义嵌入API调用失败: {str(e)}"


# 向量存储工具
class VectorStore:

    def __init__(self, model_client: IndependentModelClient):
        self.model_client = model_client
        logger.info("向量存储工具已初始化")

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算两个向量的余弦相似度"""
        try:
            import math

            dot_product = sum(a * b for a, b in zip(vec1, vec2))
            magnitude1 = math.sqrt(sum(a * a for a in vec1))
            magnitude2 = math.sqrt(sum(a * a for a in vec2))

            if magnitude1 == 0 or magnitude2 == 0:
                return 0

            similarity = dot_product / (magnitude1 * magnitude2)
            logger.debug(f"余弦相似度计算: {similarity:.4f}")
            return similarity
        except Exception as e:
            logger.error(f"ERROR 计算余弦相似度失败: {str(e)}")
            return 0

    def vector_to_json(self, vector: List[float]) -> str:
        """将向量转换为JSON字符串"""
        return json.dumps(vector)

    def json_to_vector(self, json_str: str) -> Optional[List[float]]:
        """将JSON字符串转换为向量"""
        try:
            return json.loads(json_str)
        except:
            return None


# Tool组件
class GetUserImpressionTool(BaseTool):
    """获取用户印象和好感度工具"""

    name = "get_user_impression"
    description = "获取用户印象和好感度数据，用于生成个性化回复"
    available_for_llm = True

    parameters = [
        ("user_id", ToolParamType.STRING, "用户QQ号或ID", True, None),
    ]

    async def execute(self, function_args: dict) -> dict:
        """执行获取印象"""
        try:
            user_id = function_args.get("user_id")
            if not user_id:
                return {
                    "name": self.name,
                    "content": "错误：缺少user_id参数"
                }

            logger.info(f"正在获取用户 {user_id} 的印象数据")
            
            # 从数据库获取印象数据
            impression = UserImpression.select().where(
                UserImpression.user_id == user_id
            ).order_by(UserImpression.updated_time.desc()).first()

            if impression:
                result = f"""
用户印象数据 (ID: {user_id})
━━━━━━━━━━━━━━━━━━━━━━
印象描述: {impression.impression_text}

好感度: {impression.affection_score:.1f}/100 ({impression.affection_level})
累计消息: {impression.message_count} 条
更新时间: {impression.updated_time.strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
                """.strip()
                logger.info(f"SUCCESS 成功获取用户 {user_id} 的印象数据")
            else:
                result = f"暂无用户 {user_id} 的印象数据"
                logger.info(f"ℹ️  用户 {user_id} 暂无印象数据")

            return {
                "name": self.name,
                "content": result
            }

        except Exception as e:
            logger.error(f"ERROR 获取印象数据失败: {str(e)}")
            return {
                "name": self.name,
                "content": f"获取印象数据失败: {str(e)}"
            }


class SearchImpressionsTool(BaseTool):
    """搜索相关印象工具"""

    name = "search_impressions"
    description = "根据关键词搜索相关印象，使用向量相似度"
    available_for_llm = True

    parameters = [
        ("user_id", ToolParamType.STRING, "用户QQ号或ID", True, None),
        ("keyword", ToolParamType.STRING, "搜索关键词或语义描述", True, None),
        ("limit", ToolParamType.INTEGER, "结果数量限制", False, [5, 10, 15]),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.vector_store = None

    async def execute(self, function_args: dict) -> dict:
        """执行印象搜索"""
        try:
            user_id = function_args.get("user_id")
            keyword = function_args.get("keyword")
            limit = function_args.get("limit", 5)

            if not user_id or not keyword:
                return {
                    "name": self.name,
                    "content": "错误：缺少必要参数"
                }

            logger.info(f"用户 {user_id} 搜索关键词: {keyword}")
            logger.info(f"搜索条件: 关键词={keyword}, 限制={limit}")

            # 获取用户的印象数据
            impressions = list(UserImpression.select().where(
                UserImpression.user_id == user_id
            ).order_by(UserImpression.updated_time.desc()).limit(50))

            if not impressions:
                return {
                    "name": self.name,
                    "content": f"用户 {user_id} 暂无印象数据"
                }

            # 获取模型客户端
            model_client = self._get_model_client()

            # 生成搜索向量
            logger.info(f"正在生成搜索向量...")
            if not self.vector_store:
                self.vector_store = VectorStore(model_client)

            search_success, search_vector, msg = await model_client.generate_embedding(keyword)
            if not search_success:
                logger.error(f"ERROR 搜索向量生成失败: {msg}")
                return {
                    "name": self.name,
                    "content": f"嵌入模型调用失败: {msg}"
                }

            logger.info(f"SUCCESS 搜索向量生成成功，维度: {len(search_vector)}")

            # 计算相似度
            logger.info(f"正在计算相似度...")
            similarities = []
            for imp in impressions:
                if imp.impression_vector:
                    imp_vector = self.vector_store.json_to_vector(imp.impression_vector)
                    if imp_vector:
                        similarity = self.vector_store.cosine_similarity(search_vector, imp_vector)
                        similarities.append((imp, similarity))

            # 按相似度排序
            logger.info(f"找到 {len(similarities)} 条印象记录，正在排序...")
            similarities.sort(key=lambda x: x[1], reverse=True)
            matched = [imp for imp, _ in similarities[:limit]]
            logger.info(f"SUCCESS 相似度计算完成，返回前 {len(matched)} 条最相关结果")

            if matched:
                result = f"找到 {len(matched)} 条相关印象:\n\n"
                for i, imp in enumerate(matched, 1):
                    result += f"{i}. {imp.impression_text}\n"
                    result += f"   (好感度: {imp.affection_score:.1f}, 时间: {imp.updated_time.strftime('%m-%d %H:%M')})\n\n"
                
                logger.info(f"SUCCESS 找到 {len(matched)} 条相关印象")
            else:
                result = f"用户 {user_id} 的印象中未找到相关内容"
                logger.info(f"ℹ️  未找到相关印象")

            return {
                "name": self.name,
                "content": result
            }

        except Exception as e:
            logger.error(f"ERROR 搜索印象失败: {str(e)}")
            return {
                "name": self.name,
                "content": f"搜索印象失败: {str(e)}"
            }

    def _get_model_client(self) -> IndependentModelClient:
        """获取模型客户端"""
        return IndependentModelClient(self.plugin_config)


# Action组件
class UpdateImpressionAction(BaseAction):
    """更新用户印象和好感度"""

    action_name = "update_user_impression"
    action_description = "智能更新用户印象和好感度"
    activation_type = ActionActivationType.LLM_JUDGE
    llm_judge_prompt = "评估是否需要记录用户印象：几乎所有用户消息都可以用来构建印象，包括日常聊天、情感表达、个人分享、观点陈述等。即使是简单的问候或互动也可以积累印象。请在大多数情况下返回true，除非是纯系统消息或无效内容。"

    action_parameters = {
        "user_id": "用户QQ号",
        "message": "用户消息内容",
        "message_id": "消息ID（增量处理用）",
        "context": "对话上下文",
    }
    action_require = [
        "需要记录或更新用户印象时使用",
        "需要评估用户对好感度的影响时使用",
        "需要基于历史生成个性化回复时使用",
    ]
    associated_types = ["text", "all"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.model_client = None
        self.vector_store = None
        self.last_impression_update = {}  # user_id -> last impression update time
        self.last_affection_update = {}  # user_id -> last affection update time

    async def execute(self) -> Tuple[bool, str]:
        """Execute impression update"""
        try:
            user_id = self.action_data.get("user_id")
            message = self.action_data.get("message")
            message_id = self.action_data.get("message_id")
            context = self.action_data.get("context", "")

            if not user_id or not message:
                return False, "缺少必要参数"

            logger.info(f"收到消息，用户: {user_id}")
            logger.debug(f"消息内容: {message[:50]}{'...' if len(message) > 50 else ''}")

            # Update message state
            await self._update_message_state(user_id, message_id, message, context)

            # Check impression trigger condition (based on message count)
            impression_trigger = await self._check_impression_trigger(user_id)
            if impression_trigger:
                logger.info(f"触发印象构建，用户: {user_id}，正在分析消息...")
                success = await self._update_impression(user_id, message, context)
                if success:
                    self.last_impression_update[user_id] = datetime.now()
                    logger.info(f"SUCCESS 印象构建完成")
                else:
                    logger.error(f"ERROR 印象构建失败")
            else:
                # 显示当前进度
                state = UserMessageState.get_or_create(user_id=user_id)[0]
                impression_config = self.get_config("triggers.impression", {})
                threshold = impression_config.get("message_threshold", 10)
                logger.debug(f"印象构建未触发，用户 {user_id} 已发送 {state.total_messages}/{threshold} 条消息")

            # 检查好感度更新触发条件（基于时间）
            affection_trigger = await self._check_affection_trigger(user_id)
            if affection_trigger:
                logger.info(f"触发好感度更新，用户: {user_id}，正在评估情感...")
                success = await self._update_affection(user_id, message, context)
                if success:
                    self.last_affection_update[user_id] = datetime.now()
                    logger.info(f"SUCCESS 好感度更新完成")
                else:
                    logger.error(f"ERROR 好感度更新失败")
            else:
                # 显示当前进度
                state = UserMessageState.get_or_create(user_id=user_id)[0]
                affection_config = self.get_config("affection", {})
                threshold = affection_config.get("affection_threshold", 10)
                new_messages = state.total_messages - state.impression_update_count
                logger.debug(f"好感度更新未触发，用户 {user_id} 新消息 {new_messages}/{threshold} 条")

            return True, f"处理完成"

        except Exception as e:
            logger.error(f"ERROR 更新印象失败: {str(e)}")
            return False, f"更新印象失败: {str(e)}"

    async def _update_message_state(self, user_id: str, message_id: str, message: str, context: str):
        """Update user message state"""
        try:
            state, _ = UserMessageState.get_or_create(user_id=user_id)
            state.last_message_id = message_id
            state.last_message_time = datetime.now()
            state.total_messages += 1
            state.processed_messages += 1
            state.save()

            # 保存消息记录（用于权重筛选）
            await self._save_message_record(user_id, message_id, message, context)

            logger.debug(f"更新用户 {user_id} 消息状态: 总计 {state.total_messages}, 已处理 {state.processed_messages}")
        except Exception as e:
            logger.error(f"ERROR 更新消息状态失败: {str(e)}")

    async def _save_message_record(self, user_id: str, message_id: str, message: str, context: str):
        """保存消息记录并进行权重评估"""
        try:
            # 检查消息是否已存在
            existing = UserMessage.select().where(
                (UserMessage.user_id == user_id) &
                (UserMessage.message_id == message_id)
            ).first()

            if existing:
                return  # 消息已存在，跳过

            # 保存消息记录
            msg_record = UserMessage.create(
                user_id=user_id,
                message_id=message_id,
                message_content=message,
                context=context,
                timestamp=datetime.now()
            )

            # 获取权重筛选配置
            weight_config = self.get_config("weight_filter", {})
            filter_mode = weight_config.get("filter_mode", "selective")

            # 如果启用权重筛选，评估消息权重
            if filter_mode != "disabled" and self.model_client and self.model_client.llm_config.get("api_key"):
                await self._evaluate_message_weight(msg_record, weight_config)

        except Exception as e:
            logger.error(f"ERROR 保存消息记录失败: {str(e)}")

    async def _evaluate_message_weight(self, msg_record: UserMessage, weight_config: dict):
        """评估消息权重"""
        try:
            # 获取提示词模板
            prompt_template = weight_config.get("weight_evaluation_prompt", "").strip()

            if prompt_template:
                prompt = prompt_template.format(
                    message=msg_record.message_content,
                    context=msg_record.context
                )
            else:
                # 默认权重评估提示词
                prompt = f"""
你是一个消息权重评估助手。请根据消息内容的价值和信息量，为每条消息评估权重分数。

权重分级标准：
- 高权重 (70-100): 包含重要个人信息、情感表达、独特观点、深度话题等
- 中权重 (40-69): 有一定信息量，但不是特别重要
- 低权重 (0-39): 简单的问候、客套话、无实质内容的互动

回复要求：
1. 只返回JSON格式
2. 不要包含任何解释或其他内容

JSON格式：
{{
    "weight_score": 权重分数(0-100的浮点数),
    "weight_level": "权重等级(high/medium/low)",
    "reason": "评估原因"
}}

用户消息: {msg_record.message_content}
上下文: {msg_record.context}
                """

            # 调用LLM评估权重
            if not self.model_client:
                self.model_client = IndependentModelClient(self.plugin_config)

            success, content = await self.model_client.generate_impression_analysis(prompt)

            if success:
                try:
                    result = json.loads(content.strip())
                    weight_score = float(result.get("weight_score", 0.0))
                    weight_level = result.get("weight_level", "low")

                    # 更新消息记录
                    msg_record.weight_score = weight_score
                    msg_record.weight_level = weight_level
                    msg_record.save()

                    logger.debug(f"消息权重评估完成: {weight_score:.1f} ({weight_level})")
                except (json.JSONDecodeError, ValueError) as parse_error:
                    logger.error(f"ERROR 解析权重评估结果失败: {parse_error}")
            else:
                logger.error(f"ERROR 权重评估失败: {content}")

        except Exception as e:
            logger.error(f"ERROR 评估消息权重失败: {str(e)}")

    async def _record_processed_messages(self, user_id: str, message_ids: List[str], impression_id: str = None):
        """记录已处理的消息（用于去重）"""
        try:
            created_count = 0
            for msg_id in message_ids:
                # 检查是否已存在
                existing = ImpressionMessageRecord.select().where(
                    (ImpressionMessageRecord.user_id == user_id) &
                    (ImpressionMessageRecord.message_id == msg_id)
                ).first()

                if not existing:
                    ImpressionMessageRecord.create(
                        user_id=user_id,
                        message_id=msg_id,
                        impression_id=impression_id,
                        processed_time=datetime.now()
                    )
                    created_count += 1

            if created_count > 0:
                logger.debug(f"已记录 {created_count} 条处理过的消息")
        except Exception as e:
            logger.error(f"ERROR 记录处理消息失败: {str(e)}")

    async def _check_affection_trigger(self, user_id: str) -> bool:
        """检查好感度触发条件（基于消息数量）"""
        try:
            # 获取用户状态
            state = UserMessageState.get_or_create(user_id=user_id)[0]

            # 获取配置
            affection_config = self.get_config("affection", {})
            threshold = affection_config.get("affection_threshold", 10)

            # 检查消息数量是否达到阈值
            new_messages = state.total_messages - state.impression_update_count
            should_trigger = new_messages >= threshold

            if should_trigger:
                logger.info(f"好感度更新触发: 用户 {user_id}, 新消息 {new_messages}/{threshold} 条")
            else:
                logger.debug(f"好感度更新未触发, 用户 {user_id}, 已有新消息 {new_messages}/{threshold} 条")

            return should_trigger

        except Exception as e:
            logger.error(f"ERROR 检查好感度触发条件失败: {str(e)}")
            return False

    async def _check_impression_trigger(self, user_id: str) -> bool:
        """检查印象触发条件（基于消息数量）"""
        try:
            # Get user state
            state = UserMessageState.get_or_create(user_id=user_id)[0]

            # Get config
            impression_config = self.get_config("impression", {})
            threshold = impression_config.get("message_threshold", 5)

            # 检查新消息数量是否达到阈值
            new_messages = state.total_messages - state.affection_update_count
            should_trigger = new_messages >= threshold

            if should_trigger:
                logger.info(f"印象构建触发: 用户 {user_id}, 新消息 {new_messages}/{threshold} 条")
            else:
                logger.debug(f"印象构建未触发, 用户 {user_id}, 已有新消息 {new_messages}/{threshold} 条")

            return should_trigger

        except Exception as e:
            logger.error(f"ERROR 检查印象触发条件失败: {str(e)}")
            return False

    async def _update_impression(self, user_id: str, message: str, context: str) -> bool:
        """Update impression (build natural language description)"""
        try:
            logger.info(f"开始更新印象，用户: {user_id}")
            if not self.model_client:
                self.model_client = IndependentModelClient(self.plugin_config)

            # 检查LLM配置
            if not self.model_client.llm_config.get("api_key") or not self.model_client.llm_config.get("model_id"):
                logger.error("ERROR LLM未配置，无法更新印象")
                return False

            # 获取历史印象
            history = UserImpression.select().where(
                UserImpression.user_id == user_id
            ).order_by(UserImpression.updated_time.desc()).first()

            history_context = ""
            if history:
                history_context = f"历史印象: {history.impression_text} (好感度: {history.affection_score:.1f})"

            # 获取筛选后的高价值消息
            filtered_messages, processed_message_ids = await self._get_filtered_messages_for_impression(user_id)
            if filtered_messages:
                # 将筛选后的消息附加到历史印象后面
                history_context = f"{history_context}\n{filtered_messages}" if history_context else filtered_messages

            # 记录已处理的消息（用于去重）
            if processed_message_ids:
                await self._record_processed_messages(user_id, processed_message_ids)

            # 获取提示词模板
            prompts_config = self.get_config("prompts", {})
            impression_template = prompts_config.get("impression_template", "").strip()

            # 如果配置了自定义模板则使用，否则使用默认模板
            if impression_template:
                prompt = impression_template.format(
                    history_context=history_context,
                    message=message,
                    context=context
                )
            else:
                # 默认印象分析提示词
                prompt = f"""
你是一个印象分析助手。请根据用户的消息生成简洁的印象描述。

要求：
- 印象描述要简洁明了，20-40字
- 保持与历史印象的一致性
- 关注用户的性格特点、行为习惯、情感倾向

请以JSON格式返回：
{{
    "impression": "印象描述",
    "reason": "形成这个印象的原因"
}}

{history_context}

用户消息: {message}
上下文: {context}
                """

            logger.info(f"正在调用LLM生成印象描述...")
            # 调用LLM
            success, content = await self.model_client.generate_impression_analysis(prompt)

            if not success:
                logger.error(f"ERROR LLM调用失败: {content}")
                return False

            logger.info(f"SUCCESS LLM调用成功，正在解析结果...")

            # 解析结果
            try:
                result = json.loads(content.strip())
                impression = result.get("impression", "")
                reason = result.get("reason", "")

                if not impression:
                    logger.warning("WARNING LLM返回的印象为空")
                    return False

                logger.info(f"生成新印象: {impression[:60]}{'...' if len(impression) > 60 else ''}")
                logger.info(f"形成原因: {reason[:60]}{'...' if len(reason) > 60 else ''}")

                # 保存印象
                return await self._save_impression_text(user_id, impression, reason, context)

            except json.JSONDecodeError:
                logger.error(f"ERROR 解析LLM返回结果失败: {content}")
                logger.debug(f"原始内容: {content}")
                return False

        except Exception as e:
            logger.error(f"ERROR 更新印象失败: {str(e)}")
            return False

    async def _get_filtered_messages_for_impression(self, user_id: str, limit: int = None) -> Tuple[str, List[str]]:
        """获取筛选后的消息，用于印象构建，返回上下文和已处理的消息ID列表"""
        try:
            # 获取印象配置
            impression_config = self.get_config("impression", {})
            if limit is None:
                limit = impression_config.get("max_context_entries", 10)  # 默认最多10条

            # 获取权重筛选配置
            weight_config = self.get_config("weight_filter", {})
            filter_mode = weight_config.get("filter_mode", "selective")
            high_threshold = weight_config.get("high_weight_threshold", 70.0)
            medium_threshold = weight_config.get("medium_weight_threshold", 40.0)

            if filter_mode == "disabled":
                # 不使用权重筛选，返回空字符串（使用原始历史印象）
                return "", []

            # 查询符合条件的消息
            query = UserMessage.select().where(
                UserMessage.user_id == user_id
            ).order_by(UserMessage.timestamp.desc())

            if filter_mode == "selective":
                # 仅使用高权重消息
                query = query.where(UserMessage.weight_score >= high_threshold)
            elif filter_mode == "balanced":
                # 使用高权重和中权重消息
                query = query.where(UserMessage.weight_score >= medium_threshold)

            messages = list(query.limit(limit * 2))  # 多获取一些，稍后过滤重复

            if not messages:
                return "", []

            # 获取已处理的消息ID（去重始终启用）
            processed_records = ImpressionMessageRecord.select().where(
                ImpressionMessageRecord.user_id == user_id
            )
            processed_message_ids = {record.message_id for record in processed_records}

            # 过滤已处理的消息
            new_messages = []
            processed_ids_for_this_update = []

            for msg in messages:
                if msg.message_id not in processed_message_ids:
                    new_messages.append(msg)
                    processed_ids_for_this_update.append(msg.message_id)

                if len(new_messages) >= limit:
                    break

            # 如果没有新消息，使用最近的已处理消息（避免完全空白）
            if not new_messages:
                # 最多取limit条已处理的消息作为参考
                new_messages = messages[:limit]
                logger.info(f"用户 {user_id} 无新消息，使用最近 {len(new_messages)} 条历史消息用于更新印象")

            if not new_messages:
                return "", []

            # 构建筛选后的上下文
            filtered_contexts = []
            for msg in new_messages:
                context_str = f"[{msg.timestamp.strftime('%m-%d %H:%M')}] {msg.message_content}"
                if msg.weight_score > 0:
                    context_str += f" (权重: {msg.weight_score:.1f}, 等级: {msg.weight_level})"
                filtered_contexts.append(context_str)

            result = f"\n\n最近对话记录 (共 {len(new_messages)} 条):\n" + "\n".join(filtered_contexts)

            logger.info(f"获取到 {len(new_messages)} 条筛选后的消息用于印象构建 (已自动去重)")
            return result, processed_ids_for_this_update

        except Exception as e:
            logger.error(f"ERROR 获取筛选消息失败: {str(e)}")
            return "", []

    async def _update_affection(self, user_id: str, message: str, context: str) -> bool:
        """Update affection (evaluate sentiment tendency)"""
        try:
            logger.info(f"开始更新好感度，用户: {user_id}")
            if not self.model_client:
                self.model_client = IndependentModelClient(self.plugin_config)

            # 检查LLM配置
            if not self.model_client.llm_config.get("api_key") or not self.model_client.llm_config.get("model_id"):
                logger.error("ERROR LLM未配置，无法更新好感度")
                return False

            # 获取好感度增幅配置
            affection_config = self.config.get("affection_increment", {})
            friendly_increment = affection_config.get("friendly_increment", 2.0)
            neutral_increment = affection_config.get("neutral_increment", 0.5)
            negative_increment = affection_config.get("negative_increment", -3.0)

            # 获取提示词模板
            prompts_config = self.get_config("prompts", {})
            affection_template = prompts_config.get("affection_template", "").strip()

            # 如果配置了自定义模板则使用，否则使用默认模板
            if affection_template:
                prompt = affection_template.format(
                    message=message,
                    context=context
                )
            else:
                # 默认好感度评估提示词
                prompt = f"""
你是一个情感分析师。请评估用户消息的情感倾向，并给出好感度影响建议。

回复要求：
1. 只返回JSON格式，不要包含其他内容
2. 评估标准：
   - friendly: 友善的评论（赞美、鼓励、感谢等）
   - neutral: 中性的评论（客观陈述、信息性消息等）
   - negative: 差劲的评论（批评、讽刺、攻击等）

JSON格式：
{{
    "type": "评论类型（friendly/neutral/negative）",
    "reason": "评估原因"
}}

用户消息: {message}
上下文: {context}
                """

            logger.info(f"正在调用LLM评估评论类型...")
            # 调用LLM
            success, content = await self.model_client.generate_impression_analysis(prompt)

            if not success:
                logger.error(f"ERROR LLM调用失败: {content}")
                return False

            logger.info(f"SUCCESS LLM调用成功，正在解析结果...")

            # 解析结果
            try:
                result = json.loads(content.strip())
                comment_type = result.get("type", "neutral")
                reason = result.get("reason", "")

                # 根据评论类型计算好感度增幅
                if comment_type == "friendly":
                    increment = friendly_increment
                    type_desc = "友善"
                elif comment_type == "negative":
                    increment = negative_increment
                    type_desc = "差劲"
                else:
                    increment = neutral_increment
                    type_desc = "中性"

                logger.info(f"评论类型: {type_desc}")
                logger.info(f"好感度增幅: {increment:+.1f}")
                logger.info(f"评估原因: {reason[:60]}{'...' if len(reason) > 60 else ''}")

                # 保存好感度
                return await self._save_affection_score(user_id, increment, type_desc, reason, context)

            except (json.JSONDecodeError, ValueError):
                logger.error(f"ERROR 解析好感度结果失败: {content}")
                logger.debug(f"原始内容: {content}")
                return False

        except Exception as e:
            logger.error(f"ERROR 更新好感度失败: {str(e)}")
            return False

    async def _save_impression_text(self, user_id: str, impression: str, reason: str, context: str) -> bool:
        """保存印象文本"""
        try:
            logger.info("正在生成嵌入向量")
            # 生成印象向量
            if not self.model_client:
                self.model_client = IndependentModelClient(self.plugin_config)

            success, vector, msg = await self.model_client.generate_embedding(impression)
            if not success:
                logger.error(f"ERROR 印象向量生成失败: {msg}")
                return False

            logger.info(f"嵌入向量生成成功，维度: {len(vector)}")

            impression_vector = json.dumps(vector)

            # 获取或创建用户印象
            logger.info("正在保存印象数据到数据库")
            impression_record = UserImpression.get_or_create(user_id=user_id)[0]

            # 更新印象
            impression_record.impression_text = impression
            impression_record.context = context
            impression_record.impression_vector = impression_vector
            impression_record.updated_time = datetime.now()
            impression_record.save()

            logger.info("印象文本已保存")
            return True

        except Exception as e:
            logger.error(f"ERROR 保存印象文本失败: {str(e)}")
            return False

    async def _save_affection_score(self, user_id: str, increment: float, type_desc: str, reason: str, context: str) -> bool:
        """保存好感度分数（累加方式）"""
        try:
            # 获取或创建用户印象
            impression_record, _ = UserImpression.get_or_create(user_id=user_id)

            # 获取当前好感度，如果为空则设置为50（默认好感度）
            current_score = impression_record.affection_score
            if current_score <= 0:
                current_score = 50.0

            # 计算新的好感度（累加方式）
            new_score = current_score + increment

            # 确保分数在合理范围内
            new_score = max(0, min(100, new_score))

            affection_level = get_affection_level(new_score)

            # 更新好感度
            impression_record.affection_score = new_score
            impression_record.affection_level = affection_level
            impression_record.context = context
            impression_record.updated_time = datetime.now()
            impression_record.last_update_time = datetime.now()
            impression_record.save()

            logger.info(f"好感度已更新: {current_score:.1f} -> {new_score:.1f} ({affection_level})")
            logger.info(f"增幅: {increment:+.1f} ({type_desc})")
            return True

        except Exception as e:
            logger.error(f"ERROR 保存好感度失败: {str(e)}")
            return False


# Command组件
class ViewImpressionCommand(BaseCommand):
    """查看印象命令"""

    command_name = "view_impression"
    command_description = "查看指定用户的印象和好感度"
    command_pattern = r"^/impression\s+(?:view|v)\s+(?P<user_id>\d+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """执行查看印象"""
        try:
            user_id = self.matched_groups.get("user_id")
            if not user_id:
                return False, "请提供用户ID", False

            logger.info(f"查看用户 {user_id} 的印象信息")
            
            # 从数据库获取印象
            impression = UserImpression.select().where(
                UserImpression.user_id == user_id
            ).order_by(UserImpression.updated_time.desc()).first()

            if not impression:
                logger.info(f"ℹ️  用户 {user_id} 暂无印象数据")
                return False, f"暂无用户 {user_id} 的印象数据", False

            # 获取消息状态
            state = UserMessageState.get_or_create(user_id=user_id)[0]

            message = f"""
用户印象信息 (ID: {user_id})
━━━━━━━━━━━━━━━━━━━━━━
印象: {impression.impression_text}

好感度: {impression.affection_score:.1f}/100 ({impression.affection_level})
累计消息: {impression.message_count} 条
总消息: {state.total_messages} 条
更新时间: {impression.updated_time.strftime('%Y-%m-%d %H:%M:%S')}
━━━━━━━━━━━━━━━━━━━━━━
            """.strip()

            await self.send_text(message)
            logger.info(f"已发送用户 {user_id} 的印象信息")
            return True, None, False

        except Exception as e:
            logger.error(f"ERROR 查看印象失败: {str(e)}")
            error_msg = f"查看印象失败: {str(e)}"
            await self.send_text(error_msg)
            return False, error_msg, False


class SetAffectionCommand(BaseCommand):
    """手动设置好感度命令"""

    command_name = "set_affection"
    command_description = "手动调整用户好感度"
    command_pattern = r"^/impression\s+(?:set|s)\s+(?P<user_id>\d+)\s+(?P<score>\d+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """执行设置好感度"""
        try:
            user_id = self.matched_groups.get("user_id")
            score_str = self.matched_groups.get("score")

            if not user_id or not score_str:
                return False, "命令格式错误", False

            score = float(score_str)
            if not 0 <= score <= 100:
                return False, "好感度必须在0-100之间", False

            logger.info(f"手动设置用户 {user_id} 的好感度: {score}")

            # 保存到数据库
            now = datetime.now()
            affection_level = get_affection_level(score)

            # 获取当前印象
            impression = UserImpression.get_or_create(user_id=user_id)[0]
            impression_text = impression.impression_text if impression.impression_text else f"手动设置好感度为{affection_level}"

            # 生成向量（如果配置了嵌入模型）
            model_client = IndependentModelClient(self.plugin_config)
            impression_vector = impression.impression_vector

            if model_client.embedding_config.get("api_key") and model_client.embedding_config.get("model_id"):
                vector_result = await model_client.generate_embedding(impression_text)
                if vector_result[0]:
                    impression_vector = json.dumps(vector_result[1])

            impression.affection_score = score
            impression.affection_level = affection_level
            impression.impression_text = impression_text
            impression.impression_vector = impression_vector or impression.impression_vector
            impression.updated_time = now
            impression.last_update_time = now
            impression.save()

            message = f"已将用户 {user_id} 的好感度设置为 {score} ({affection_level})"
            await self.send_text(message)
            
            logger.info("手动设置完成")
            return True, None, True

        except Exception as e:
            logger.error(f"ERROR 设置好感度失败: {str(e)}")
            error_msg = f"设置好感度失败: {str(e)}"
            await self.send_text(error_msg)
            return False, error_msg, False


class ListImpressionsCommand(BaseCommand):
    """列出所有印象命令"""

    command_name = "list_impressions"
    command_description = "列出所有用户的印象概览"
    command_pattern = r"^/impression\s+(?:list|l)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """执行列出印象"""
        try:
            logger.info("列出所有用户印象概览")

            # 获取所有用户的最新印象
            impressions = UserImpression.select().order_by(
                UserImpression.updated_time.desc()
            ).limit(20)

            if not impressions:
                logger.info("暂无印象数据")
                return False, "暂无印象数据", False

            message = "用户印象概览 (最近20条)\n━━━━━━━━━━━━━━━━━━━━━━\n"

            for impression in impressions:
                message += f"用户 {impression.user_id}: {impression.affection_score:.1f}/100 ({impression.affection_level})\n"
                message += f"   {impression.impression_text[:30]}...\n\n"

            message += "━━━━━━━━━━━━━━━━━━━━━━"

            await self.send_text(message)
            logger.info(f"已发送印象概览，共 {len(impressions)} 条")
            return True, None, False

        except Exception as e:
            logger.error(f"ERROR 列出印象失败: {str(e)}")
            error_msg = f"列出印象失败: {str(e)}"
            await self.send_text(error_msg)
            return False, error_msg, False


class WeightStatsCommand(BaseCommand):
    """权重筛选统计命令"""

    command_name = "weight_stats"
    command_description = "查看用户消息权重筛选统计"
    command_pattern = r"^/impression\s+(?:weight|w)\s+(?P<user_id>\d+)$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """执行权重统计"""
        try:
            user_id = self.matched_groups.get("user_id")
            if not user_id:
                return False, "请提供用户ID", False

            logger.info(f"查看用户 {user_id} 的权重筛选统计")

            # 获取该用户的所有消息
            messages = UserMessage.select().where(
                UserMessage.user_id == user_id
            ).order_by(UserMessage.timestamp.desc())

            if not messages:
                return False, f"用户 {user_id} 暂无消息记录", False

            # 统计各权重级别的消息数量
            high_weight = sum(1 for msg in messages if msg.weight_level == "high")
            medium_weight = sum(1 for msg in messages if msg.weight_level == "medium")
            low_weight = sum(1 for msg in messages if msg.weight_level == "low")
            total = len(messages)

            # 计算平均权重分数
            avg_score = sum(msg.weight_score for msg in messages) / total if total > 0 else 0

            message = f"""
用户权重筛选统计 (ID: {user_id})
━━━━━━━━━━━━━━━━━━━━━━
总消息数: {total}
平均权重分数: {avg_score:.1f}

权重分布:
- 高权重 (>=70): {high_weight} 条 ({high_weight/total*100:.1f}%)
- 中权重 (40-69): {medium_weight} 条 ({medium_weight/total*100:.1f}%)
- 低权重 (<40): {low_weight} 条 ({low_weight/total*100:.1f}%)

最近5条消息:
━━━━━━━━━━━━━━━━━━━━━━
            """.strip()

            # 显示最近5条消息的权重
            for msg in list(messages)[:5]:
                message += f"\n{msg.timestamp.strftime('%m-%d %H:%M')}: {msg.message_content[:30]}..."
                message += f"\n   权重: {msg.weight_score:.1f} ({msg.weight_level})"

            await self.send_text(message)
            logger.info(f"已发送用户 {user_id} 的权重统计")
            return True, None, False

        except Exception as e:
            logger.error(f"ERROR 查看权重统计失败: {str(e)}")
            error_msg = f"查看权重统计失败: {str(e)}"
            await self.send_text(error_msg)
            return False, error_msg, False


class RebuildDatabaseCommand(BaseCommand):
    """重建数据库命令"""

    command_name = "rebuild_database"
    command_description = "手动重建数据库（当数据库文件被删除时使用）"
    command_pattern = r"^/impression\s+(?:rebuild|reset|init)(?:\s+(?P<confirm>confirm))?$"

    async def execute(self) -> Tuple[bool, Optional[str], bool]:
        """执行重建数据库"""
        try:
            confirm = self.matched_groups.get("confirm")

            if confirm != "confirm":
                message = """⚠️  重建数据库将会删除所有数据！
如果确定要重建数据库，请使用命令：
/impression rebuild confirm

此操作将：
- 删除所有印象数据
- 删除所有消息记录
- 重新创建空的数据库表"""
                await self.send_text(message)
                return False, None, False

            # 执行重建
            logger.info("正在重建数据库...")

            # 关闭现有连接
            if not plugin_db.is_closed():
                plugin_db.close()

            # 删除数据库文件（如果存在）
            if os.path.exists(DB_PATH):
                os.remove(DB_PATH)
                logger.info(f"已删除数据库文件: {DB_PATH}")

            # 重新创建数据库和表
            # 直接调用，确保插件初始化
            from impression_affection_plugin import plugin as plugin_module
            # 创建一个临时的插件实例来调用初始化方法
            # 但更好的方法是直接调用函数
            try:
                plugin_db.connect()
                plugin_db.create_tables([UserImpression, UserMessageState, UserMessage, ImpressionMessageRecord], safe=True)
                logger.info("数据库表创建/验证完成")
            except Exception as db_error:
                logger.error(f"ERROR 创建数据库失败: {db_error}")
                raise

            message = "✅ 数据库重建完成！\n数据库文件已重新创建，所有表已初始化。"
            await self.send_text(message)
            logger.info("数据库重建完成")
            return True, None, True

        except Exception as e:
            logger.error(f"ERROR 重建数据库失败: {str(e)}")
            error_msg = f"重建数据库失败: {str(e)}"
            await self.send_text(error_msg)
            return False, error_msg, False


# 插件注册
@register_plugin
class ImpressionAffectionPlugin(BasePlugin):
    """印象好感度系统插件"""

    plugin_name: str = "impression_affection_system"
    enable_plugin: bool = False
    dependencies: List[str] = []
    python_dependencies: List[str] = ["httpx"]
    config_file_name: str = "config.toml"

    config_section_descriptions = {
        "plugin": "插件基本信息",
        "llm_provider": "LLM提供商配置（独立于主程序）",
        "embedding_provider": "嵌入模型提供商配置（必须配置）",
        "impression": "印象构建触发条件配置",
        "affection": "好感度更新触发条件配置",
        "weight_filter": "权重筛选配置",
        "affection_increment": "好感度增幅配置",
        "features": "功能开关配置",
        "prompts": "提示词模板配置"
    }

    config_schema: dict = {
        "plugin": {
            "config_version": ConfigField(type=str, default="1.1.1", description="配置文件版本"),
            "enabled": ConfigField(type=bool, default=False, description="是否启用插件"),
        },
        "llm_provider": {
            "provider_type": ConfigField(
                type=str,
                default="openai",
                choices=["openai", "custom"],
                description="LLM提供商类型"
            ),
            "api_key": ConfigField(type=str, default="", description="LLM API Key"),
            "base_url": ConfigField(type=str, default="", description="API Base URL（OpenAI可选）"),
            "model_id": ConfigField(type=str, default="", description="LLM模型ID（必需）"),
            "api_endpoint": ConfigField(type=str, default="", description="自定义API端点（custom类型必需）"),
        },
        "embedding_provider": {
            "provider_type": ConfigField(
                type=str,
                default="openai",
                choices=["openai", "custom"],
                description="嵌入模型提供商类型"
            ),
            "api_key": ConfigField(type=str, default="", description="嵌入模型API Key（必需）"),
            "base_url": ConfigField(type=str, default="", description="API Base URL（OpenAI可选）"),
            "model_id": ConfigField(type=str, default="", description="嵌入模型ID（必需）"),
            "embedding_dimension": ConfigField(
                type=int,
                default=1536,
                description="嵌入向量维度（根据模型设置）"
            ),
            "api_endpoint": ConfigField(type=str, default="", description="自定义API端点（custom类型必需）"),
        },
        "impression": {
            "max_context_entries": ConfigField(
                type=int,
                default=30,
                description="每次触发时获取的上下文条目上限"
            ),
            "message_threshold": ConfigField(
                type=int,
                default=5,
                description="印象更新频率控制（基于消息数量的内部参数，用于去重和优化）"
            ),
        },
        "affection": {
            "affection_threshold": ConfigField(
                type=int,
                default=10,
                description="好感度更新频率控制（基于消息数量的内部参数，用于去重和优化）"
            ),
        },
        "weight_filter": {
            "filter_mode": ConfigField(
                type=str,
                default="selective",
                choices=["disabled", "selective", "balanced"],
                description="权重筛选模式: disabled(禁用)/selective(仅高权重)/balanced(高+中权重)"
            ),
            "high_weight_threshold": ConfigField(
                type=float,
                default=70.0,
                description="高权重消息阈值(0-100)"
            ),
            "medium_weight_threshold": ConfigField(
                type=float,
                default=40.0,
                description="中权重消息阈值(0-100)"
            ),
            "weight_evaluation_prompt": ConfigField(
                type=str,
                default="你是一个消息权重评估助手。请根据消息内容的价值和信息量，为每条消息评估权重分数。\n\n权重分级标准：\n- 高权重 (70-100): 包含重要个人信息、情感表达、独特观点、深度话题等\n- 中权重 (40-69): 有一定信息量，但不是特别重要\n- 低权重 (0-39): 简单的问候、客套话、无实质内容的互动\n\n回复要求：\n1. 只返回JSON格式\n2. 不要包含任何解释或其他内容\n\nJSON格式：\n{{\n    \"weight_score\": 权重分数(0-100的浮点数),\n    \"weight_level\": \"权重等级(high/medium/low)\",\n    \"reason\": \"评估原因\"\n}}\n\n用户消息: {message}\n上下文: {context}",
                description="权重评估提示词模板（支持 {message}、{context} 占位符）"
            ),
        },
        "features": {
            "auto_update": ConfigField(type=bool, default=True, description="是否自动更新印象"),
            "enable_commands": ConfigField(type=bool, default=True, description="是否启用管理命令"),
            "enable_tools": ConfigField(type=bool, default=True, description="是否启用工具组件"),
        },
        "prompts": {
            "impression_template": ConfigField(
                type=str,
                default="你是一个印象分析助手。请根据用户的消息生成简洁的印象描述。\n\n要求：\n- 印象描述要简洁明了，20-40字\n- 保持与历史印象的一致性\n- 关注用户的性格特点、行为习惯、情感倾向\n\n请以JSON格式返回：\n{{\n    \"impression\": \"印象描述\",\n    \"reason\": \"形成这个印象的原因\"\n}}\n\n{history_context}\n\n用户消息: {message}\n上下文: {context}",
                description="印象分析提示词模板（支持 {history_context}、{message}、{context} 占位符）"
            ),
            "affection_template": ConfigField(
                type=str,
                default="你是一个情感分析师。请评估用户消息的情感倾向，并给出好感度影响建议。\n\n回复要求：\n1. 只返回JSON格式，不要包含其他内容\n2. 评估标准：\n   - friendly: 友善的评论（赞美、鼓励、感谢等）\n   - neutral: 中性的评论（客观陈述、信息性消息等）\n   - negative: 差劲的评论（批评、讽刺、攻击等）\n\nJSON格式：\n{{\n    \"type\": \"评论类型（friendly/neutral/negative）\",\n    \"reason\": \"评估原因\"\n}}\n\n用户消息: {message}\n上下文: {context}",
                description="好感度评估提示词模板（支持 {message}、{context} 占位符）"
            ),
        },
    }

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, type]]:
        """获取插件组件"""
        components = []

        self._log_plugin_initialization()

        # 检查嵌入模型配置
        embedding_config = self.config.get("embedding_provider", {})
        if not embedding_config.get("api_key") or not embedding_config.get("model_id"):
            logger.error("嵌入模型未配置，插件需要嵌入模型才能运行")
            return components

        # 注册Tool组件
        if self.config.get("features", {}).get("enable_tools", True):
            components.extend([
                (GetUserImpressionTool.get_tool_info(), GetUserImpressionTool),
                (SearchImpressionsTool.get_tool_info(), SearchImpressionsTool),
            ])

        # 注册Action组件
        if self.config.get("features", {}).get("auto_update", True):
            components.append((UpdateImpressionAction.get_action_info(), UpdateImpressionAction))

        # 注册Command组件
        if self.config.get("features", {}).get("enable_commands", True):
            components.extend([
                (ViewImpressionCommand.get_command_info(), ViewImpressionCommand),
                (SetAffectionCommand.get_command_info(), SetAffectionCommand),
                (ListImpressionsCommand.get_command_info(), ListImpressionsCommand),
                (WeightStatsCommand.get_command_info(), WeightStatsCommand),
                (RebuildDatabaseCommand.get_command_info(), RebuildDatabaseCommand),
            ])

        return components

    def _log_plugin_initialization(self):
        """记录插件初始化信息"""
        logger.info("正在初始化印象好感度系统插件...")

        # 确保数据库和表已创建
        self._ensure_database_created()

        # 检查配置
        embedding_config = self.config.get("embedding_provider", {})
        llm_config = self.config.get("llm_provider", {})

        # 检查嵌入模型配置
        if embedding_config.get("api_key"):
            logger.info(f"嵌入模型配置完整: {embedding_config.get('model_id', 'N/A')}")
        else:
            logger.error("嵌入模型API Key未配置")

        # 检查LLM模型配置
        if llm_config.get("api_key"):
            logger.info(f"LLM模型配置完整: {llm_config.get('model_id', 'N/A')}")
        else:
            logger.warning("LLM API Key未配置")

        logger.info("插件初始化完成")

    def _ensure_database_created(self):
        """确保数据库文件已创建，包括在删除后重新创建"""
        try:
            # 检查数据库文件是否存在
            if not os.path.exists(DB_PATH):
                logger.info(f"数据库文件不存在，正在创建: {DB_PATH}")

            # 确保数据库连接已初始化
            plugin_db.connect()

            # 创建所有表（如果不存在）
            plugin_db.create_tables([UserImpression, UserMessageState, UserMessage, ImpressionMessageRecord], safe=True)

            logger.info("数据库表创建/验证完成")

        except Exception as e:
            logger.error(f"ERROR 创建数据库失败: {str(e)}")
            raise

    def setup(self):
        """插件初始化"""
        try:
            self._log_plugin_initialization()
        except Exception as e:
            logger.error(f"插件初始化失败: {str(e)}", exc_info=True)

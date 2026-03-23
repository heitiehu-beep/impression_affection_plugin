"""
印象和好感度系统插件 v3.0.0

基于LLM分析用户行为和消息，构建用户画像并管理好感度
支持多维度印象和难度等级系统
"""

from typing import List, Tuple, Type, Dict, Any, Optional
import os
import asyncio

from src.plugin_system import (
    BasePlugin,
    register_plugin,
    ComponentInfo,
    ConfigField,
    BaseEventHandler,
    EventType,
    CustomEventHandlerResult
)
from src.common.logger import get_logger

# 导入模型
from .models import db, UserImpression, UserMessageState, ImpressionMessageRecord
from .models.database import DB_PATH

# 导入客户端
from .clients import LLMClient

# 导入服务
from .services import (
    AffectionService,
    WeightService,
    TextImpressionService,
    MessageService,
)

# 导入组件
from .components import (
    GetUserImpressionTool,
    SearchImpressionsTool,
    ViewImpressionCommand,
    SetAffectionCommand,
    ListImpressionsCommand
)

logger = get_logger("impression_affection_system")


class ImpressionUpdateHandler(BaseEventHandler):
    """自动更新用户印象和好感度的事件处理器"""

    event_type = EventType.AFTER_LLM
    handler_name = "update_impression_handler"
    handler_description = "每次LLM回复后更新用户印象和好感度"
    intercept_message = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.affection_service = None
        self.weight_service = None
        self.message_service = None
        self.llm_client = None
        self.text_impression_service = None
        self._services_initialized = False

    async def execute(self, message) -> tuple:
        """执行事件处理器"""
        try:
            self._ensure_services_initialized()
            asyncio.create_task(self._async_update_impression(message))
            return True, True, "印象和好感度更新任务已启动", None, None
        except Exception as e:
            logger.error(f"印象更新执行失败: {str(e)}")
            return True, True, f"执行失败: {str(e)}", None, None

    async def _async_update_impression(self, event_data):
        """异步更新印象和好感度"""
        try:
            self._ensure_services_initialized()
            result = await self.handle(event_data)
        except Exception as e:
            logger.error(f"印象更新失败: {str(e)}")

    def _ensure_services_initialized(self):
        """确保服务已初始化"""
        if self._services_initialized:
            return
        self._init_services()
        self._services_initialized = True

    def _init_services(self):
        """初始化服务"""
        if not self.llm_client:
            llm_config = self.plugin_config.get("llm_provider", {})
            self.llm_client = LLMClient(llm_config)

        if not self.affection_service:
            self.affection_service = AffectionService(self.llm_client, self.plugin_config)

        if not self.weight_service:
            self.weight_service = WeightService(self.llm_client, self.plugin_config)

        if not self.text_impression_service:
            self.text_impression_service = TextImpressionService(self.llm_client, self.plugin_config)

        if not self.message_service:
            self.message_service = MessageService(self.plugin_config)

    async def handle(self, event_data) -> CustomEventHandlerResult:
        """处理事件：更新印象和好感度"""
        try:
            self._ensure_services_initialized()

            user_id = ""
            message = None

            from .services.message_service import MessageService

            # 优先从 ChatStream 获取用户ID
            if hasattr(event_data, 'stream_id') and event_data.stream_id:
                try:
                    from src.chat.message_receive.chat_stream import get_chat_manager
                    chat_manager = get_chat_manager()
                    target_stream = chat_manager.get_stream(event_data.stream_id)

                    if target_stream and target_stream.context:
                        last_message = target_stream.context.get_last_message()
                        if last_message:
                            if hasattr(last_message, 'reply') and last_message.reply:
                                raw_user_id = last_message.reply.message_info.user_info.user_id
                                user_id = MessageService.normalize_user_id(raw_user_id)
                                message = event_data
                                logger.debug(f"从 ChatStream reply 获取用户ID: {user_id}")
                            else:
                                raw_user_id = last_message.message_info.user_info.user_id
                                user_id = MessageService.normalize_user_id(raw_user_id)
                                message = event_data
                                logger.debug(f"从 ChatStream 获取用户ID: {user_id}")
                except Exception as e:
                    logger.warning(f"从 ChatStream 获取用户ID失败: {str(e)}")

            # 从 reply 对象获取（群聊回复场景）
            if not user_id:
                if hasattr(event_data, 'reply') and event_data.reply and hasattr(event_data.reply, 'user_id'):
                    raw_user_id = event_data.reply.user_id
                    user_id = MessageService.normalize_user_id(raw_user_id)
                    message = event_data
                    logger.debug(f"从 reply 对象提取用户ID: {user_id}")
                # 从 message_base_info 获取
                elif hasattr(event_data, 'message_base_info') and event_data.message_base_info:
                    raw_user_id = event_data.message_base_info.get('user_id', '')
                    if raw_user_id:
                        user_id = MessageService.normalize_user_id(raw_user_id)
                        message = event_data
                        logger.debug(f"从 message_base_info 提取用户ID: {user_id}")
                # 直接从 user_id 属性获取
                elif hasattr(event_data, 'user_id'):
                    raw_user_id = event_data.user_id
                    user_id = MessageService.normalize_user_id(raw_user_id)
                    message = event_data
                    logger.debug(f"从 user_id 属性提取用户ID: {user_id}")
                else:
                    logger.error(f"无法从事件数据中提取用户ID: {type(event_data)}")
                    return CustomEventHandlerResult(message="无法获取用户ID")

            if not user_id:
                return CustomEventHandlerResult(message="用户ID为空")

            message_content = self._extract_message_content(message)
            if not message_content:
                return CustomEventHandlerResult(message="消息内容为空")

            # 获取消息ID和时间戳
            message_id = None
            message_timestamp = None

            if hasattr(message, 'message_base_info') and message.message_base_info:
                if 'time' in message.message_base_info:
                    message_timestamp = float(message.message_base_info['time'])
                elif 'timestamp' in message.message_base_info:
                    message_timestamp = float(message.message_base_info['timestamp'])

            if not message_timestamp:
                import time
                message_timestamp = time.time()

            # 尝试从主程序数据库获取真实 message_id
            if self.weight_service.db_service and self.weight_service.db_service.is_connected():
                message_id = self.weight_service.db_service.get_main_message_id(user_id, message_timestamp)

            # 如果获取失败，生成临时ID
            if not message_id:
                import time
                message_id = f"temp_{user_id}_{int(message_timestamp)}"

            # 检查消息是否已处理
            is_processed = self.message_service.is_message_processed(user_id, message_id)
            if is_processed:
                logger.debug(f"消息已处理，跳过: {message_id}")
                return CustomEventHandlerResult(message="消息已处理，跳过")

            logger.debug(f"开始处理用户 {user_id} 的消息: {message_id}")

            # 获取历史上下文用于权重评估
            history_config = self.plugin_config.get("history", {})
            max_messages = history_config.get("max_messages", 20)
            history_context, message_ids_in_context = self.weight_service.get_filtered_messages(user_id, limit=max_messages)

            # 记录上下文中的消息为已处理（避免重复处理历史消息）
            for msg_id in message_ids_in_context:
                self.message_service.record_processed_message(user_id, msg_id)

            # 权重评估
            weight_success = False
            weight_score = 0.0
            weight_level = "low"

            if len(history_context.strip()) > 0:
                weight_success, weight_score, weight_level = await self.weight_service.evaluate_message(
                    user_id, message_id, message_content, history_context
                )

            # 根据权重决定是否更新印象
            impression_updated = False
            should_update_impression = False

            if weight_success:
                filter_mode = self.weight_service.filter_mode
                high_threshold = self.weight_service.high_threshold
                medium_threshold = self.weight_service.medium_threshold

                if filter_mode == "disabled":
                    should_update_impression = True
                elif filter_mode == "selective":
                    should_update_impression = weight_score >= high_threshold
                elif filter_mode == "balanced":
                    should_update_impression = weight_score >= medium_threshold

            # 更新印象
            if should_update_impression:
                try:
                    latest_context, latest_message_ids = self.weight_service.get_filtered_messages(user_id, limit=max_messages)
                    success, impression_result = await self.text_impression_service.build_impression(
                        user_id, message_content, latest_context
                    )
                    if success:
                        impression_updated = True
                        logger.info(f"印象更新成功: 用户 {user_id}")
                except Exception as e:
                    logger.error(f"印象更新异常: {str(e)}")

            # 更新好感度
            affection_updated = False
            try:
                success, affection_result = await self.affection_service.update_affection(
                    user_id, message_content
                )
                if success:
                    affection_updated = True
                    logger.info(f"好感度更新成功: {affection_result}")
            except Exception as e:
                logger.error(f"好感度更新异常: {str(e)}")

            # 标记当前消息为已处理
            try:
                self.message_service.record_processed_message(
                    user_id=user_id,
                    message_id=message_id,
                    content=message_content,
                    impression_id=None
                )
                logger.debug(f"已记录消息处理状态: 用户 {user_id}, message_id {message_id}, content_hash 已生成")
            except Exception as e:
                logger.error(f"记录消息处理状态失败: {str(e)}")

            # 更新消息状态统计
            self.message_service.update_message_state(
                user_id, message_id, impression_updated, affection_updated
            )

            logger.debug(f"用户 {user_id} 消息处理完成: 印象更新={impression_updated}, 好感度更新={affection_updated}")
            return CustomEventHandlerResult(message="印象和好感度更新完成")

        except Exception as e:
            logger.error(f"处理事件失败: {str(e)}")
            return CustomEventHandlerResult(message=f"异常: {str(e)}")

    def _extract_message_content(self, message) -> str:
        """提取消息内容"""
        message_content = ""

        if hasattr(message, 'plain_text') and message.plain_text:
            message_content = str(message.plain_text)
        elif hasattr(message, 'message_segments') and message.message_segments:
            message_content = " ".join([
                str(seg.data) for seg in message.message_segments
                if hasattr(seg, 'data')
            ])
        elif hasattr(message, 'content') and message.content:
            message_content = str(message.content)

        return message_content.strip()


@register_plugin
class ImpressionAffectionPlugin(BasePlugin):
    """印象和好感度系统插件 v3.0.0"""
    plugin_name = "impression_affection_plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = ["peewee", "openai", "httpx"]
    config_file_name = "config.toml"

    # 配置模式定义
    config_schema = {
        "plugin": {
            "enabled": ConfigField(
                type=bool,
                default=False,
                description="是否启用插件"
            ),
            "config_version": ConfigField(
                type=str,
                default="3.0.0",
                description="配置文件版本"
            )
        },

        "llm_provider": {
            "provider_type": ConfigField(
                type=str,
                default="openai",
                description="印象构建/好感度更新LLM提供商"
            ),
            "api_key": ConfigField(
                type=str,
                default="",
                description="API密钥"
            ),
            "base_url": ConfigField(
                type=str,
                default="https://api.openai.com/v1",
                description="API基础URL"
            ),
            "model_id": ConfigField(
                type=str,
                default="gpt-3.5-turbo",
                description="模型名称"
            )
        },

        "difficulty": {
            "level": ConfigField(
                type=str,
                default="normal",
                description="全局难度等级: easy(简单)/normal(标准)/hard(困难)/very_hard(非常困难)/nightmare(噩梦)"
            ),
            "allow_user_change": ConfigField(
                type=bool,
                default=True,
                description="是否允许用户改变难度"
            ),
            "description": ConfigField(
                type=str,
                default="难度等级越高，好感度越难增加。Galgame级别需要特殊策略。",
                description="难度说明"
            )
        },

        "impression": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否启用印象系统"
            ),
            "max_context_entries": ConfigField(
                type=int,
                default=30,
                description="最大历史消息数"
            ),
            "auto_update": ConfigField(
                type=bool,
                default=True,
                description="是否自动更新印象"
            )
        },

        "affection": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否启用好感度系统"
            ),
            "initial_score": ConfigField(
                type=float,
                default=50.0,
                description="初始好感度分数"
            ),
            "max_score": ConfigField(
                type=float,
                default=100.0,
                description="最高好感度分数"
            ),
            "min_score": ConfigField(
                type=float,
                default=0.0,
                description="最低好感度分数"
            ),
            "difficulty_level": ConfigField(
                type=str,
                default="",
                description="单独配置好感度难度(留空使用全局设置)"
            ),
            "allow_negative": ConfigField(
                type=bool,
                default=True,
                description="负面消息是否能降低好感度"
            ),
            "fixed_affection_list": ConfigField(
                type=str,
                default="{}",
                description="固定好感度列表 (JSON格式, 如: {\"user1\": 80, \"user2\": 60})"
            )
        },

        "database": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="启用数据库连接"
            ),
            "main_db_path": ConfigField(
                type=str,
                default="",
                description="数据库路径 (留空使用默认)"
            )
        },

        "history": {
            "max_messages": ConfigField(
                type=int,
                default=20,
                description="最大历史消息数"
            ),
            "hours_back": ConfigField(
                type=int,
                default=72,
                description="回溯小时数"
            ),
            "min_message_length": ConfigField(
                type=int,
                default=5,
                description="最小消息长度"
            ),
            "recent_hours": ConfigField(
                type=int,
                default=24,
                description="最近互动回溯小时数"
            ),
            "max_recent_interactions": ConfigField(
                type=int,
                default=10,
                description="最大最近互动条数"
            ),
            "max_content_length": ConfigField(
                type=int,
                default=150,
                description="单条消息内容最大长度"
            ),
            "max_context_length": ConfigField(
                type=int,
                default=2000,
                description="上下文总长度限制"
            )
        },

        "weight_filter": {
            "filter_mode": ConfigField(
                type=str,
                default="selective",
                description="筛选模式: disabled(不筛选)/selective(仅高权重)/balanced(仅高/中权重)"
            ),
            "high_weight_threshold": ConfigField(
                type=float,
                default=70.0,
                description="高权重阈值"
            ),
            "medium_weight_threshold": ConfigField(
                type=float,
                default=40.0,
                description="中权重阈值"
            ),
            "use_custom_weight_model": ConfigField(
                type=bool,
                default=False,
                description="是否使用独立的权重评估模型"
            ),
            "weight_model_provider": ConfigField(
                type=str,
                default="openai",
                description="权重评估模型提供商"
            ),
            "weight_model_api_key": ConfigField(
                type=str,
                default="",
                description="权重评估模型API密钥"
            ),
            "weight_model_base_url": ConfigField(
                type=str,
                default="https://api.openai.com/v1",
                description="权重评估模型基础URL"
            ),
            "weight_model_id": ConfigField(
                type=str,
                default="gpt-3.5-turbo",
                description="权重评估模型ID"
            ),
            "max_weight_records": ConfigField(
                type=int,
                default=100,
                description="每个用户最大权重记录数"
            )
        },

        # 提示词模板
        "prompts": {
            "impression_template": ConfigField(
                type=str,
                default="基于对话记录生成用户画像。现有印象：{existing_impression} 历史对话：{history_context} 当前消息：{message}",
                description="印象分析提示词模板"
            ),
            "affection_template": ConfigField(
                type=str,
                default="请评估消息的情感倾向(friendly/neutral/negative)。返回格式：TYPE: type; REASON: reason; 消息: {message}",
                description="好感度评估提示词模板"
            ),
            "weight_evaluation_prompt": ConfigField(
                type=str,
                default="",
                description="权重评估提示词模板（留空使用默认）"
            ),
            "max_history_chars": ConfigField(
                type=int,
                default=2000,
                description="历史上下文最大字符数"
            ),
            "max_message_chars": ConfigField(
                type=int,
                default=500,
                description="单条消息最大字符数"
            )
        },

        "commands": {
            "allowed_users": ConfigField(
                type=list,
                default=[],
                description="允许使用命令的用户ID列表，为空则允许所有人使用"
            ),
            "enable_commands": ConfigField(
                type=bool,
                default=True,
                description="启用管理命令"
            )
        },

        "features": {
            "auto_update": ConfigField(
                type=bool,
                default=True,
                description="自动更新印象和好感度"
            ),
            "enable_tools": ConfigField(
                type=bool,
                default=True,
                description="启用工具组件"
            ),
            "enable_commands": ConfigField(
                type=bool,
                default=True,
                description="启用命令组件"
            ),
            "enable_difficulty_system": ConfigField(
                type=bool,
                default=True,
                description="启用难度系统"
            )
        }
    }

    def __init__(self, plugin_dir: str = None):
        super().__init__(plugin_dir)
        self.db_initialized = False

    def init_db(self):
        """初始化数据库"""
        if not self.db_initialized:
            try:
                db.connect()

                from .models import (
                    UserImpression,
                    UserMessageState,
                    ImpressionMessageRecord,
                )

                db.create_tables([
                    UserImpression,
                    UserMessageState,
                    ImpressionMessageRecord,
                ], safe=True)

                # 执行数据库迁移
                self._migrate_database()

                self.db_initialized = True
                logger.info(f"数据库初始化成功: {DB_PATH}")

                tables = db.get_tables()
                logger.info(f"已创建的表: {tables}")

            except Exception as e:
                logger.error(f"数据库初始化失败: {str(e)}")
                raise e

    def _migrate_database(self):
        """数据库迁移 - 添加新字段"""
        try:
            # 为 ImpressionMessageRecord 添加 content_hash 字段
            cursor = db.execute_sql("PRAGMA table_info(impression_message_records)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'content_hash' not in columns:
                logger.info("检测到缺少 content_hash 字段，开始数据库迁移...")
                db.execute_sql("ALTER TABLE impression_message_records ADD COLUMN content_hash TEXT")
                db.execute_sql("CREATE INDEX IF NOT EXISTS impression_message_records_user_content_hash ON impression_message_records(user_id, content_hash)")
                logger.info("数据库迁移完成：已添加 content_hash 字段和索引")
            else:
                logger.debug("content_hash 字段已存在，跳过迁移")

            # 为 UserImpression 添加 difficulty_level 字段
            cursor = db.execute_sql("PRAGMA table_info(user_impressions)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'difficulty_level' not in columns:
                logger.info("检测到缺少 difficulty_level 字段，开始数据库迁移...")
                db.execute_sql("ALTER TABLE user_impressions ADD COLUMN difficulty_level TEXT DEFAULT 'normal'")
                logger.info("数据库迁移完成：已添加 difficulty_level 字段")
            else:
                logger.debug("difficulty_level 字段已存在，跳过迁移")

        except Exception as e:
            logger.error(f"数据库迁移失败: {str(e)}")
            # 不抛出异常，允许插件继续运行，但记录错误

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件组件列表"""
        self.init_db()
        components = []

        # 注册事件处理器
        components.append((ImpressionUpdateHandler.get_handler_info(), ImpressionUpdateHandler))

        features_config = self.get_config("features", {})

        # 注册工具组件
        if features_config.get("enable_tools", True):
            components.extend([
                (GetUserImpressionTool.get_tool_info(), GetUserImpressionTool),
                (SearchImpressionsTool.get_tool_info(), SearchImpressionsTool)
            ])

        # 注册命令组件
        if features_config.get("enable_commands", True):
            components.extend([
                (ViewImpressionCommand.get_command_info(), ViewImpressionCommand),
                (SetAffectionCommand.get_command_info(), SetAffectionCommand),
                (ListImpressionsCommand.get_command_info(), ListImpressionsCommand)
            ])

        return components

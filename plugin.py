"""
印象和好感度系统插件
"""

from typing import List, Tuple, Type, Dict, Any, Optional
import os

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
    MessageService
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
    handler_description = "每次LLM回复后自动更新用户印象和好感度"
    intercept_message = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.affection_service = None
        self.weight_service = None
        self.message_service = None
        self.llm_client = None
        self.text_impression_service = None

    async def execute(self, message) -> tuple:
        """执行事件处理器"""
        result = await self.handle(message)
        return True, True, None, result, None

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
        """处理事件：每次LLM回复后自动更新印象和好感度"""
        try:
            # 初始化服务
            self._init_services()
            
            logger.debug(f"收到AFTER_LLM事件，事件数据类型: {type(event_data)}")

            # 获取消息对象 - 兼容不同的事件数据格式
            message = None
            user_id = ""
            
            # 尝试不同的消息获取方式
            if hasattr(event_data, 'message_base_info'):
                message = event_data
                user_id = str(message.message_base_info.get('user_id', ''))
            elif hasattr(event_data, 'user_id'):
                user_id = str(event_data.user_id)
                message = event_data
            elif hasattr(event_data, 'plain_text'):
                user_id = str(getattr(event_data, 'user_id', ''))
                message = event_data
            else:
                # 尝试从事件数据中提取消息
                if hasattr(event_data, '__dict__'):
                    for attr_name in ['message', 'msg', 'data']:
                        if hasattr(event_data, attr_name):
                            potential_msg = getattr(event_data, attr_name)
                            if hasattr(potential_msg, 'user_id'):
                                user_id = str(potential_msg.user_id)
                                message = potential_msg
                                break
                
                if not user_id:
                    logger.error(f"无法从事件数据中提取用户ID: {event_data}")
                    return CustomEventHandlerResult(message="无法从事件数据中提取用户ID")

            if not user_id:
                logger.error(f"用户ID为空")
                return CustomEventHandlerResult(message="无法获取用户ID")

            # 获取消息内容
            message_content = self._extract_message_content(message)
            if not message_content:
                logger.warning(f"用户 {user_id} 的消息内容为空")
                return CustomEventHandlerResult(message="消息内容为空")

            # 生成消息ID
            import time
            message_id = str(int(time.time() * 1000))

            # 检查消息是否已处理
            if self.message_service.is_message_processed(user_id, message_id):
                logger.debug(f"用户 {user_id} 的消息 {message_id} 已处理，跳过")
                return CustomEventHandlerResult(message="消息已处理，跳过")

            logger.info(f"开始处理用户 {user_id} 的消息: {message_content[:50]}...")

            # 评估消息权重
            logger.debug(f"开始评估消息权重 - 用户: {user_id}, 消息: {message_content[:50]}...")
            weight_success, weight_score, weight_level = await self.weight_service.evaluate_message(
                user_id, message_id, message_content, ""
            )

            if not weight_success:
                logger.warning(f"权重评估失败: {weight_level}")
            else:
                logger.info(f"权重评估成功 - 分数: {weight_score}, 等级: {weight_level}")

            # 获取筛选后的历史消息
            history_context, processed_ids = self.weight_service.get_filtered_messages(user_id)
            logger.debug(f"获取到历史上下文，长度: {len(history_context)}")

            # 根据权重等级决定是否更新印象
            impression_updated = False
            should_update_impression = False
            
            if weight_success:
                # 检查权重等级是否满足更新条件
                filter_mode = self.weight_service.filter_mode
                high_threshold = self.weight_service.high_threshold
                medium_threshold = self.weight_service.medium_threshold
                
                if filter_mode == "disabled":
                    should_update_impression = True
                elif filter_mode == "selective":
                    should_update_impression = weight_score >= high_threshold
                elif filter_mode == "balanced":
                    should_update_impression = weight_score >= medium_threshold
                
                logger.info(f"权重筛选检查 - 模式: {filter_mode}, 分数: {weight_score}, 阈值: {high_threshold}/{medium_threshold}, 是否更新印象: {should_update_impression}")
            else:
                logger.warning(f"权重评估失败，跳过印象更新")
                should_update_impression = False

            # 更新印象
            if should_update_impression:
                try:
                    logger.debug(f"开始构建印象 - 用户: {user_id}, 消息: {message_content[:50]}...")
                    success, impression_result = await self.text_impression_service.build_impression(
                        user_id, message_content, history_context
                    )
                    if success:
                        impression_updated = True
                        logger.info(f"印象更新成功: {impression_result[:50]}...")
                    else:
                        logger.warning(f"印象更新失败: {impression_result}")
                except Exception as e:
                    logger.error(f"印象更新异常: {str(e)}")
            else:
                logger.info(f"权重等级不满足印象更新条件 (分数: {weight_score}, 等级: {weight_level})，跳过印象更新")

            # 更新好感度
            affection_updated = False
            try:
                success, affection_result = await self.affection_service.update_affection(
                    user_id, message_content
                )
                if success:
                    affection_updated = True
                    logger.info(f"好感度更新成功: {affection_result}")
                else:
                    logger.warning(f"好感度更新失败: {affection_result}")
            except Exception as e:
                logger.error(f"好感度更新异常: {str(e)}")

            # 更新消息状态
            self.message_service.update_message_state(
                user_id, message_id, impression_updated, affection_updated
            )

            # 记录已处理的消息
            for msg_id in processed_ids:
                self.message_service.record_processed_message(user_id, msg_id)

            self.message_service.record_processed_message(user_id, message_id)

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

        return message_content.strip()


@register_plugin
class ImpressionAffectionPlugin(BasePlugin):
    """印象和好感度系统插件"""

    # 插件基本信息
    plugin_name = "impression_affection_plugin"
    enable_plugin = True
    dependencies = []
    python_dependencies = ["peewee", "openai", "httpx"]
    config_file_name = "config.toml"

    # 配置模式 - 详细的配置定义
    config_schema = {
        "plugin": {
            "enabled": ConfigField(
                type=bool,
                default=True,
                description="是否启用插件。设置为false可以临时禁用插件功能"
            ),
            "config_version": ConfigField(
                type=str,
                default="2.0.0",
                description="配置文件版本，用于版本管理和兼容性检查"
            )
        },
        "llm_provider": {
            "provider_type": ConfigField(
                type=str,
                default="openai",
                description="LLM提供商类型。可选值: 'openai'(OpenAI格式API)或'custom'(自定义API)"
            ),
            "api_key": ConfigField(
                type=str,
                default="sk-your-api-key-here",
                description="LLM API密钥。必需，用于认证API调用"
            ),
            "base_url": ConfigField(
                type=str,
                default="https://api.openai.com/v1",
                description="API基础URL。OpenAI格式API的端点地址，如使用官方API可保持默认"
            ),
            "model_id": ConfigField(
                type=str,
                default="gpt-3.5-turbo",
                description="LLM模型ID。例如: gpt-3.5-turbo, deepseek-chat等"
            ),
            "api_endpoint": ConfigField(
                type=str,
                default="",
                description="自定义API端点。仅在使用custom提供商时需要，完整的API调用地址"
            )
        },
        
        "impression": {
            "max_context_entries": ConfigField(
                type=int,
                default=30,
                description="每次触发时获取的上下文条目上限。用于限制构建印象时参考的历史消息数量，避免token消耗过大"
            )
        },
        "weight_filter": {
            "filter_mode": ConfigField(
                type=str,
                default="selective",
                description="权重筛选模式。可选值: 'disabled'(禁用筛选，所有消息都更新印象), 'selective'(仅高权重消息更新印象), 'balanced'(高权重+中权重消息更新印象)"
            ),
            "high_weight_threshold": ConfigField(
                type=float,
                default=70.0,
                description="高权重消息阈值(0-100)。高于此阈值的消息被认为包含重要信息，用于印象构建。建议范围: 60.0-80.0"
            ),
            "medium_weight_threshold": ConfigField(
                type=float,
                default=40.0,
                description="中权重消息阈值(0-100)。用于balanced模式，包含一定信息量但不是特别重要的消息。建议范围: 30.0-50.0"
            ),
            "weight_evaluation_prompt": ConfigField(
                type=str,
                default="评估消息权重（0-100），用于判断是否用于构建用户印象。权重评估标准：高权重(70-100): 包含重要个人信息、兴趣爱好、价值观、情感表达、深度思考、独特观点、生活经历分享；中权重(40-69): 一般日常对话、简单提问、客观陈述、基础信息交流；低权重(0-39): 简单问候、客套话、无实质内容的互动、表情符号。特别注意：分享个人喜好（如书籍、音乐、电影等）、询问对方偏好、表达个人观点都应该给予较高权重。只返回键值对格式：WEIGHT_SCORE: 分数;WEIGHT_LEVEL: high/medium/low;REASON: 评估原因;消息: {message};上下文: {context}",
                description="权重评估提示词模板。自定义LLM评估消息权重的提示词，支持{message}和{context}占位符。修改此提示词可能影响权重评估准确性，建议谨慎修改"
            )
        },
        "affection_increment": {
            "friendly_increment": ConfigField(
                type=float,
                default=2.0,
                description="友善评论好感度增幅。用户发送友善、赞美、鼓励类消息时的分数变化。建议范围: 1.0-5.0，过高可能导致好感度增长过快"
            ),
            "neutral_increment": ConfigField(
                type=float,
                default=0.5,
                description="中性评论好感度增幅。用户发送客观、信息性消息时的分数变化。建议范围: 0.1-1.0，用于维持基础好感度增长"
            ),
            "negative_increment": ConfigField(
                type=float,
                default=-3.0,
                description="负面评论好感度增幅。用户发送批评、讽刺、攻击类消息时的分数变化。建议范围: -5.0到-1.0，过低可能导致好感度下降过快"
            )
        },
        "prompts": {
            "impression_template": ConfigField(
                type=str,
                default="根据用户消息按8个维度生成印象，每项10字内，信息不足用待观察。只返回键值对格式：personality_traits:性格特征;interests_hobbies:兴趣爱好;communication_style:交流风格;emotional_tendencies:情感倾向;behavioral_patterns:行为模式;values_attitudes:价值观态度;relationship_preferences:关系偏好;growth_development:成长发展。历史: {history_context};消息: {message}",
                description="印象分析提示词模板。自定义LLM生成印象描述的提示词，支持{history_context}, {message}, {context}占位符。修改此提示词可能影响印象描述质量"
            ),
            "affection_template": ConfigField(
                type=str,
                default="评估用户消息情感倾向（friendly/neutral/negative）。只返回键值对格式：TYPE: friendly/neutral/negative;REASON: 评估原因;消息: {message}",
                description="好感度评估提示词模板。自定义LLM评估情感倾向的提示词，支持{message}, {context}占位符。修改此提示词可能影响情感判断准确性"
            )
        },
        "features": {
            "auto_update": ConfigField(
                type=bool,
                default=True,
                description="是否自动更新印象和好感度。禁用后插件不会自动处理消息，需要手动调用工具。生产环境建议保持启用"
            ),
            "enable_commands": ConfigField(
                type=bool,
                default=True,
                description="是否启用管理命令。启用后可以使用/impression view等命令查看和管理用户印象。调试时可启用"
            ),
            "enable_tools": ConfigField(
                type=bool,
                default=True,
                description="是否启用工具组件。启用后LLM可以调用get_user_impression等工具获取用户印象数据。核心功能，建议保持启用"
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
                
                # 确保导入所有模型
                from .models import (
                    UserImpression,
                    UserMessageState, 
                    ImpressionMessageRecord
                )
                
                # 创建所有表
                db.create_tables([
                    UserImpression,
                    UserMessageState,
                    ImpressionMessageRecord
                ], safe=True)
                
                self.db_initialized = True
                logger.info(f"数据库初始化成功: {DB_PATH}")
                
                # 验证表是否创建成功
                tables = db.get_tables()
                logger.info(f"已创建的表: {tables}")
                
            except Exception as e:
                logger.error(f"数据库初始化失败: {str(e)}")
                raise e

    def get_plugin_components(self) -> List[Tuple[ComponentInfo, Type]]:
        """返回插件组件列表"""
        self.init_db()

        components = []

        # 添加事件处理器
        components.append((ImpressionUpdateHandler.get_handler_info(), ImpressionUpdateHandler))

        # 根据配置添加组件
        features_config = self.get_config("features", {})

        if features_config.get("enable_tools", True):
            # 添加工具组件
            components.extend([
                (GetUserImpressionTool.get_tool_info(), GetUserImpressionTool),
                (SearchImpressionsTool.get_tool_info(), SearchImpressionsTool)
            ])

        if features_config.get("enable_commands", True):
            # 添加命令组件
            components.extend([
                (ViewImpressionCommand.get_command_info(), ViewImpressionCommand),
                (SetAffectionCommand.get_command_info(), SetAffectionCommand),
                (ListImpressionsCommand.get_command_info(), ListImpressionsCommand)
            ])

        return components
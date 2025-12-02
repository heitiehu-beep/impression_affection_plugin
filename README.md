# 印象和好感度系统插件 v2.2.0

基于LLM分析用户行为和消息，构建用户画像并维护好感度关系

## 系统概述

本插件实现基于LLM的用户印象和好感度管理系统，通过智能分析用户消息内容，在独立数据库构建多维度用户画像，并动态维护好感度关系。

## 注意

本插件需使用大量的上下文，会消耗更多的Tokens，请酌情使用

## 核心功能

### 印象构建系统
- 自动分析用户消息内容，提取性格特征和兴趣偏好
- 采用自然语言印象表示，更符合真实印象描述
- 智能权重筛选机制，仅对高价值消息更新印象
- 完善的查重机制，基于主程序message_id避免重复处理
- 增量式印象更新，支持历史上下文分析

### 好感度管理
- 三级情感分类：友善、中性、负面
- 动态分数调整：0-100分制，支持自定义权重配置
- 等级自动划分：非常差、很差、较差、一般、较好、很好、非常好
- 基于消息内容的智能情感判断

### 智能筛选机制
- 基于主程序数据库message_id的精确查重
- 消息权重评估：高权重(70-100)、中权重(40-69)、低权重(0-39)
- 三种筛选模式：禁用筛选、选择性筛选、平衡筛选
- 上下文管理：智能选取高质量历史消息用于印象构建
- 渐进式历史消息获取，避免重复处理

## 技术架构

### 服务层架构
- TextImpressionService：印象构建和文本分析
- AffectionService：好感度评估和动态调整
- WeightService：消息权重评估和筛选
- MessageService：消息状态跟踪和查重管理
- DatabaseService：主程序数据库连接和查询

### 组件系统
- 工具组件：GetUserImpressionTool、SearchImpressionsTool
- 命令组件：ViewImpressionCommand、SetAffectionCommand、ListImpressionsCommand
- 事件处理：ImpressionUpdateHandler

### 数据模型
- UserImpression：用户印象和好感度数据
- UserMessageState：用户消息状态统计
- ImpressionMessageRecord：消息处理记录

### 查重机制
- 基于主程序数据库message_id的精确查重
- 历史消息自动标记已处理，避免重复获取
- 智能时序控制，确保查重准确性

### 插件数据库
- 自动生成的impression_affection_data.db文件
- 可随时删除重新生成
- 使用SQLite

## 配置说明

### LLM提供商配置
```toml
[llm_provider]
provider_type = "openai"  # 或 "custom"
api_key = "your-api-key"
base_url = "https://api.openai.com/v1"
model_id = "gpt-3.5-turbo"
```

### 权重筛选配置
```toml
[weight_filter]
filter_mode = "selective"  # disabled/selective/balanced
high_weight_threshold = 70.0
medium_weight_threshold = 40.0
```

### 好感度增量配置
```toml
[affection_increment]
friendly_increment = 2.0
neutral_increment = 0.5
negative_increment = -3.0
```

## 安装和部署

### 环境要求
- Python 3.11+
- MaiBot 0.11.0+

### 依赖安装
```bash
cd ~/MaiBot/plugins/impression_affection_plugin-main
pip install -r requirements.txt
```

### 配置文件
插件首次启动时会自动生成 `config.toml` 配置文件，请根据需要修改LLM API配置。

## 使用指南

### 自动功能
- 插件启动后自动监听LLM回复事件
- 智能分析用户消息并更新印象和好感度
- 支持权重筛选，仅处理有价值的信息

### 手动命令（暂时没用）
- `/impression view <user_id>` - 查看用户印象信息
- `/impression set <user_id> <score>` - 设置好感度分数
- `/impression list` - 列出所有用户印象

### LLM工具
- `get_user_impression` - 获取用户印象数据
- `search_impressions` - 搜索印象中的关键词

## 数据库结构

### user_impressions 表
| 字段名 | 类型 | 说明 |
|--------|------|------|
| user_id | TEXT | 用户ID（唯一） |
| personality_traits | TEXT | 性格特征描述 |
| interests_hobbies | TEXT | 兴趣爱好描述 |
| communication_style | TEXT | 交流风格描述 |
| emotional_tendencies | TEXT | 情感倾向描述 |
| behavioral_patterns | TEXT | 行为模式描述 |
| values_attitudes | TEXT | 价值观态度描述 |
| relationship_preferences | TEXT | 关系偏好描述 |
| growth_development | TEXT | 成长发展描述 |
| affection_score | REAL | 好感度分数(0-100) |
| affection_level | TEXT | 好感度等级 |
| message_count | INTEGER | 累计消息数 |
| last_interaction | DATETIME | 最后交互时间 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

### user_message_state 表
| 字段名 | 类型 | 说明 |
|--------|------|------|
| user_id | TEXT | 用户ID（唯一） |
| last_message_id | TEXT | 最后消息ID |
| last_message_time | DATETIME | 最后消息时间 |
| impression_update_count | INTEGER | 印象更新次数 |
| affection_update_count | INTEGER | 好感度更新次数 |
| total_messages | BIGINT | 总消息数 |
| processed_messages | BIGINT | 已处理消息数 |

### impression_message_records 表
| 字段名 | 类型 | 说明 |
|--------|------|------|
| user_id | TEXT | 用户ID |
| message_id | TEXT | 消息ID |
| impression_id | TEXT | 印象记录ID |
| processed_at | DATETIME | 处理时间 |

## 开发说明

### 插件结构
```
impression_affection_plugin-main/
├── plugin.py              # 主插件文件
├── config.toml           # 配置文件
├── requirements.txt      # 依赖列表
├── models/               # 数据模型
├── services/             # 服务层
├── components/           # 组件
├── clients/              # 客户端
└── utils/               # 工具函数
```

### 扩展开发
- 添加新的印象维度：修改 `UserImpression` 模型
- 自定义权重算法：扩展 `WeightService`
- 新增命令组件：继承 `BaseCommand`
- 添加工具组件：继承 `BaseTool`


## 故障排除

### 常见问题
1. **插件加载失败**：检查配置文件格式和API密钥
2. **印象不更新**：确认LLM API连接正常
3. **权重评估异常**：检查提示词配置和模型响应
4. **数据库错误**：确认文件权限和磁盘空间

### 调试模式
在配置文件中设置 `plugin.enabled = false` 可临时禁用插件，用于调试。

## 版本历史
PS:这里只更新大版本日志

### v2.2.0
- 增加查重机制，基于主程序message_id进行精确查重
- 优化权重评估流程，避免重复评估
- 改进历史消息获取，支持渐进式查重
- 完善异步处理机制，提升响应速度
- 优化日志输出，减少冗余信息

### v2.1.0
- 移除8维印象系统，改为自然语言（更符合“印象”的设计思路）
- 可以获取获取MaiBot数据库的聊天记录，以更好构建印象
- 修改了一些提示词
- 修改了插件的触发机制，不会影响replyer的回复速度

### v2.0.0
- 重构为纯LLM文本存储版本
- 移除向量化功能，简化架构
- 优化8维度印象系统
- 改进权重筛选机制
- 完善配置管理系统

## 许可证

MIT License

## 作者

HEITIEHU

# 印象和好感度系统插件 v3.0.0

基于LLM分析用户行为和消息，构建用户画像并维护好感度关系

## 系统概述

本插件实现基于LLM的用户印象和好感度管理系统，通过智能分析用户消息内容，在独立数据库构建多维度用户画像，并动态维护好感度关系。**v3.0.0 增强版新增了难度等级系统和 Nightmare 模式，支持多层次难度调整。**

## 注意

本插件需使用大量的上下文，会消耗更多的Tokens，请酌情使用

---

## ✨ v3.0.0 新增功能

### 难度等级系统（新增）

本版本引入了完整的难度等级系统，允许为不同用户设置不同的难度等级，影响好感度的增减速度和规则。

#### 5 个难度等级

| 难度等级 | 名称 | 聊天增幅 | 倍数 | 特点 |
|---------|------|---------|------|------|
| **easy** | 简单 | +2.0 | 1.0 | 聊天直接增加好感度，最容易获得好感 |
| **normal** | 标准 | +1.5 | 1.0 | **【推荐】** 平衡难度，聊天+互动 |
| **hard** | 困难 | +0.5 | 0.8 | 聊天贡献很小，需要特殊互动 |
| **very_hard** | 非常困难 | +0.2 | 0.6 | Galgame 级难度，需要策略 |
| **nightmare** | 噩梦 | ±1.0 | 0.4 | **【新】** 最高难度，聊天可增可减 |

#### Nightmare 模式详解（重点新功能）

在 **Nightmare 模式**（最高难度）下，好感度不再是单纯的增加，而是**双向变化**：

**核心特点：**
- ✅ 普通聊天会**扣分** (-0.4/消息)
- ✅ 虚伪夸奖会**大幅扣分** (-2.0)
- ✅ 完全不同意会**严重扣分** (-2.0)
- ✅ 强烈同意才能**加分** (+0.8)
- ✅ AI 会判断用户观点的**真实性和说服力**

**评估规则：**

```

Nightmare 模式评估流程：

1. 标准评估 (friendly/neutral/negative)
    ↓
2. 深度评估 (真实性和说服力评估)
    ↓
3. 综合判决：
   
   ├─ 强烈同意、深刻观点  → +2.0 × 0.4 = +0.8
   ├─ 友善、友好消息      → +1.0 × 0.4 = +0.4
   ├─ 普通聊天、敷衍      → -1.0 × 0.4 = -0.4 ⚠️
   ├─ 轻微不同意、肤浅    → -2.0 × 0.4 = -0.8
   └─ 完全不同意、虚伪    → -5.0 × 0.4 = -2.0

```

**推荐策略：**
1. 观点要深刻 - 避免表面话
2. 要真挚 - 不要虚伪夸奖
3. 要有说服力 - 肤浅观点会被视为不同意
4. 要有耐心 - 在这个难度下，好感度增长非常缓慢
5. 要研究对方 - 理解对方的价值观才能有效沟通

---

## 核心功能

### 印象构建系统
- 自动分析用户消息内容，提取性格特征和兴趣偏好
- 采用自然语言印象表示，更符合真实印象描述
- 智能权重筛选机制，仅对高价值消息更新印象
- 完善的查重机制，基于主程序message_id避免重复处理
- 增量式印象更新，支持历史上下文分析

### 好感度管理（增强版）
- **【原有】** 三级情感分类：友善、中性、负面
- **【原有】** 动态分数调整：0-100分制，支持自定义权重配置
- **【原有】** 等级自动划分：非常差、很差、较差、一般、较好、很好、非常好
- **【原有】** 基于消息内容的智能情感判断
- **【新增】** 难度等级系统，支持 5 个难度级别
- **【新增】** Nightmare 模式，支持双向好感度变化
- **【新增】** 深度评估机制，评判观点真实性和说服力
- **【新增】** 固定好感度列表，特定用户不受聊天影响

### 智能筛选机制
- 基于主程序数据库message_id的精确查重
- 消息权重评估：高权重(70-100)、中权重(40-69)、低权重(0-39)
- 三种筛选模式：禁用筛选、选择性筛选、平衡筛选
- 上下文管理：智能选取高质量历史消息用于印象构建
- 渐进式历史消息获取，避免重复处理

## 技术架构

### 服务层架构
- TextImpressionService：印象构建和文本分析
- **AffectionService（增强版）** ⭐：支持难度系统、Nightmare 模式、双向好感度
- WeightService：消息权重评估和筛选
- MessageService：消息状态跟踪和查重管理
- DatabaseService：主程序数据库连接和查询

### 组件系统
- 工具组件：GetUserImpressionTool、SearchImpressionsTool
- 命令组件：ViewImpressionCommand、SetAffectionCommand、ListImpressionsCommand
- 事件处理：ImpressionUpdateHandler

### 数据模型
- **UserImpression（增强版）**：新增 `difficulty_level` 字段（难度等级）
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

难度等级配置（新增）

```toml
[difficulty]
# 全局难度等级: easy/normal/hard/very_hard/nightmare
level = "normal"  # 推荐使用 normal（标准难度）

# 是否允许用户改变自己的难度
allow_user_change = true
```

难度等级说明：
- `easy` - 最容易，聊天直接增加好感度
- `normal` - 标准难度 【推荐】
- `hard` - 困难模式
- `very_hard` - Galgame级难度
- `nightmare` - 最高难度，聊天可增可减

权重筛选配置

```toml
[weight_filter]
filter_mode = "selective"  # disabled/selective/balanced
high_weight_threshold = 70.0
medium_weight_threshold = 40.0
```

好感度增量配置（增强版）

```toml
[affection_increment]
# Easy/Normal 模式的基础增幅
friendly_increment = 2.0      # 友善消息增幅
neutral_increment = 0.5        # 中性消息增幅
negative_increment = -3.0      # 负面消息增幅

# 注意：Hard/Very Hard/Nightmare 模式会使用不同的增幅配置
# 倍数乘数会自动根据难度应用
```

好感度基础配置（新增）

```toml
[affection]
enabled = true
initial_score = 30.0           # 初始好感度（不再是固定50）
max_score = 100.0
min_score = 0.0
allow_negative = true
# 固定好感度列表（JSON格式），这些用户的好感度不会被聊天改变
fixed_affection_list = '{"123456789": 80, "987654321": 60}'
```

命令权限配置（新增）

```toml
[commands]
# 允许使用命令的用户ID列表，为空数组则允许所有人使用
# 例如：allowed_users = ["123456789", "987654321"]
allowed_users = []
enable_commands = true
```

权限控制说明：
- `allowed_users = []`（默认）：所有人都能使用 `/impression` 命令
- `allowed_users = ["123456789"]`：只有指定的用户能使用命令，其他人发送命令将无任何响应（静默拒绝）

安装和部署

环境要求
- Python 3.11+
- MaiBot 0.11.0+

依赖安装

```bash
cd ~/MaiBot/plugins/impression_affection_plugin-main
pip install -r requirements.txt
```

配置文件
【更新】 插件首次启动时会自动生成 `config.toml` 配置文件。本版本提供了两个预设配置：

1. config_preset_normal.toml - Normal 难度（推荐默认）
   
```bash
   cp config_preset_normal.toml config.toml
   ```

2. config_preset_nightmare.toml - Nightmare 难度（Galgame 级）
   
```bash
   cp config_preset_nightmare.toml config.toml
   ```

根据需要选择合适的预设配置，或自行修改。

使用指南

自动功能
- 插件启动后自动监听LLM回复事件
- 【增强】 智能分析用户消息并根据难度等级更新印象和好感度
- 【增强】 在 Nightmare 模式下，同时评估观点的真实性和说服力
- 支持权重筛选，仅处理有价值的信息

手动命令（可用）
以下命令可通过聊天窗口使用（需要 `enable_commands = true`）：

- `/impression view <user_id>` - 查看指定用户的印象和好感度信息
- `/impression set <user_id> <score>` - 手动设置用户好感度分数（0-100）
- `/impression list` - 列出所有已记录的用户印象

使用示例：

```
/impression view 123456789
/impression set 123456789 80
/impression list
```

权限控制：
如果配置了 `allowed_users`，未授权用户发送命令将不会有任何响应（静默拒绝）。

LLM工具
- `get_user_impression` - 获取用户印象数据
- `search_impressions` - 搜索印象中的关键词

新增功能
【新】 可通过代码设置用户难度：

```python
impression.set_difficulty("nightmare")  # 设置为 Nightmare 模式
impression.save()
```

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

开发说明
```
插件结构

impression_affection_plugin-main/
├── plugin.py              # 主插件文件
├── config.toml           # 配置文件
├── requirements.txt      # 依赖列表
├── models/               # 数据模型
│   ├── __init__.py
│   ├── database.py
│   ├── user_impression.py          # 【修改】添加 difficulty_level 字段
│   ├── user_message_state.py
│   └── impression_message_record.py
├── services/             # 服务层
│   ├── __init__.py
│   ├── affection_service.py        # 【重写】支持难度系统和 Nightmare 模式
│   ├── text_impression_service.py
│   ├── weight_service.py
│   └── message_service.py
├── components/           # 组件
│   ├── commands.py                 # 【可用】命令组件，支持权限控制
│   └── tools.py
├── clients/              # 客户端
└── utils/               # 工具函数
    ├── __init__.py
    ├── constants.py                # 【修改】添加难度常量定义
    └── helpers.py                  # 【新增】辅助函数
```

扩展开发
- 添加新的印象维度：修改 `UserImpression` 模型
- 自定义权重算法：扩展 `WeightService`
- 【新增】 自定义难度等级：修改 `constants.py` 中的 `DIFFICULTY_LEVELS`
- 【新增】 自定义 Nightmare 评估逻辑：扩展 `AffectionService._evaluate_nightmare_mode()`
- 新增命令组件：继承 `BaseCommand`
- 添加工具组件：继承 `BaseTool`

故障排除

常见问题
1. 插件加载失败：检查配置文件格式和API密钥
2. 印象不更新：确认LLM API连接正常
3. 权重评估异常：检查提示词配置和模型响应
4. 数据库错误：确认文件权限和磁盘空间
5. 【新】 难度设置无效：确认使用的难度等级在支持列表中（easy/normal/hard/very_hard/nightmare）
6. 【新】 Nightmare 模式下好感度一直扣分：这是正常行为，需要真挚和深思熟虑的观点才能加分
7. 【新】 命令无响应：检查 `enable_commands` 是否为 true，以及是否在 `allowed_users` 列表中（如果设置了）
8. 【新】 固定好感度不生效：检查 `fixed_affection_list` 是否为正确的 JSON 格式，且用户ID为字符串

调试模式
在配置文件中设置 `plugin.enabled = false` 可临时禁用插件，用于调试。

版本历史

v3.0.0 ✨ 新功能版本
【新增功能】
- ✅ 难度等级系统：5 个难度级别（easy/normal/hard/very_hard/nightmare）
- ✅ Nightmare 模式：最高难度，聊天可增加也可减少好感度
- ✅ 双向好感度变化：支持观点真实性和说服力的深度评估
- ✅ 难度配置：全局难度设置和单用户难度配置
- ✅ 预设配置文件：提供 Normal 和 Nightmare 两个预设配置
- ✅ 倍数乘数系统：不同难度使用不同的倍数乘数
- ✅ 命令权限控制：支持指定用户才能使用管理命令
- ✅ 管理命令可用：/impression view/set/list 命令已可用
- ✅ 固定好感度列表：特定用户可设置固定好感度，不受聊天影响
- ✅ 可配置初始好感度：通过 initial_score 设置，不再是固定50

【改进内容】
- 改进 AffectionService：完全支持难度系统，修复参数错误，支持固定好感度
- 改进 UserImpression 模型：添加难度等级字段
- 改进常量定义：添加难度和增幅配置
- 改进 MessageService：修复初始化错误
- 改进 Commands：添加权限检查机制，静默拒绝无权限用户

【兼容性】
- ✅ 完全向后兼容，旧数据无需迁移
- ✅ 轻量级实现，不创建新表
- ✅ 配置自动生成，无需手动创建

v2.3.1
- 修复：权重评估消息标记时序问题
- 修复：max_messages配置不生效问题
- 修复：临时ID被.isdigit()过滤导致查重失效
- 修复：数据库查询混入Bot消息问题
- 修复：群聊场景下用户ID混淆问题

v2.2.0
- 增加查重机制，基于主程序message_id进行精确查重
- 优化权重评估流程，避免重复评估
- 改进历史消息获取，支持渐进式查重
- 完善异步处理机制，提升响应速度
- 优化日志输出，减少冗余信息

v2.1.0
- 移除8维印象系统，改为自然语言（更符合"印象"的设计思路）
- 可以获取获取MaiBot数据库的聊天记录，以更好构建印象
- 修改了一些提示词
- 修改了插件的触发机制，不会影响replyer的回复速度

v2.0.0
- 重构为纯LLM文本存储版本
- 移除向量化功能，简化架构
- 优化8维度印象系统
- 改进权重筛选机制
- 完善配置管理系统

许可证

MIT License

作者

HEITIEHU

---

快速参考

5 个难度等级概览

```
Easy (简单)
├── 聊天增幅: +2.0
├── 倍数: 1.0
└── 特点: 最容易，聊天直接增加好感度

Normal (标准) ⭐【推荐】
├── 聊天增幅: +1.5
├── 倍数: 1.0
└── 特点: 平衡难度，聊天+互动方式

Hard (困难)
├── 聊天增幅: +0.5
├── 倍数: 0.8
└── 特点: 聊天贡献不大，需要特殊互动

Very Hard (非常困难)
├── 聊天增幅: +0.2
├── 倍数: 0.6
└── 特点: Galgame级难度

Nightmare (噩梦) 🔥【最高难度】
├── 聊天增幅: ±1.0 (可增可减)
├── 倍数: 0.4
└── 特点: 聊天可能扣分，需要真挚和深思熟虑的观点
```
Nightmare 模式快速指南
```
好感度变化规则（Nightmare 模式）：

强烈同意、深刻观点
  ↓
  +2.0 × 0.4 = +0.8 ✅

友善、友好消息
  ↓
  +1.0 × 0.4 = +0.4 ✅

普通聊天、敷衍
  ↓
  -1.0 × 0.4 = -0.4 ⚠️

轻微不同意、肤浅
  ↓
  -2.0 × 0.4 = -0.8 ❌

完全不同意、虚伪
  ↓
  -5.0 × 0.4 = -2.0 ❌❌
```
配置快速切换
```
bash
# 使用 Normal 难度（推荐）
cp config_preset_normal.toml config.toml

# 使用 Nightmare 难度（挑战）
cp config_preset_nightmare.toml config.toml
```
命令快速参考
```
bash
# 查看用户印象
/impression view 123456789

# 设置好感度（0-100）
/impression set 123456789 80

# 列出所有用户
/impression list

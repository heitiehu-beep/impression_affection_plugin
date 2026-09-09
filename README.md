# 印象和好感度系统插件 / Impression & Affection System Plugin

> 中英对照文档 / Bilingual README
> 排版规则 / Format: 段落为中文在前、英文（斜体）在后；列表项用 `中文 / English`；表格用换行分隔双语。

基于 LLM 分析用户行为和消息，构建用户画像并维护好感度关系。

*An LLM-based plugin that analyzes user behavior and messages, builds multi-dimensional user profiles, and maintains dynamic affection relationships.*

---

## 系统概述 / Overview

本插件实现基于 LLM 的用户印象和好感度管理系统，通过智能分析用户消息内容，在独立数据库构建多维度用户画像，并动态维护好感度关系。**v3.0.0 增强版新增了难度等级系统和 Nightmare 模式，支持多层次难度调整。**

*This plugin implements an LLM-driven user-impression and affection management system. It analyzes message content, builds multi-dimensional user profiles in a dedicated database, and dynamically maintains affection relationships. **v3.0.0 adds a difficulty-level system and Nightmare mode for multi-tier difficulty tuning.***

## ⚠️ 注意 / Notice

本插件需使用大量的上下文，会消耗更多的 Tokens，请酌情使用。

*This plugin consumes a large amount of context and therefore more tokens. Use it judiciously.*

---

## ✨ v3.5.0 新增功能 / What's New in v3.5.0

### 难度等级系统（新增）/ Difficulty Level System (New)

本版本引入了完整的难度等级系统，允许为不同用户设置不同的难度等级，影响好感度的增减速度和规则。

*This release introduces a complete difficulty-level system, allowing different difficulty levels per user, affecting both the rate and the rules of affection change.*

#### 5 个难度等级 / 5 Difficulty Levels

| 难度等级<br>Level | 名称<br>Name | 聊天增幅<br>Chat Gain | 倍数<br>Multiplier | 特点<br>Notes |
|---|---|---|---|---|
| **easy** | 简单<br>Easy | +2.0 | 1.0 | 聊天直接增加好感度，最容易获得好感<br>Chat directly raises affection; easiest to gain |
| **normal** | 标准<br>Normal | +1.5 | 1.0 | **【推荐】** 平衡难度，聊天+互动<br>**[Recommended]** Balanced; chat + interaction |
| **hard** | 困难<br>Hard | +0.5 | 0.8 | 聊天贡献很小，需要特殊互动<br>Chat contributes little; needs special interaction |
| **very_hard** | 非常困难<br>Very Hard | +0.2 | 0.6 | Galgame 级难度，需要策略<br>Galgame-grade difficulty; requires strategy |
| **nightmare** | 噩梦<br>Nightmare | ±1.0 | 0.4 | **【新】** 最高难度，聊天可增可减<br>**[New]** Highest difficulty; chat can raise or lower |

#### Nightmare 模式详解（重点新功能）/ Nightmare Mode in Detail (Highlight)

在 **Nightmare 模式**（最高难度）下，好感度不再是单纯的增加，而是**双向变化**：

*In **Nightmare mode** (the highest difficulty), affection no longer only increases — it changes **in both directions**:*

**核心特点：/ Key traits:**
- ✅ 普通聊天会**扣分** (-0.4/消息) — *Normal chat **deducts points** (-0.4/message)*
- ✅ 虚伪夸奖会**大幅扣分** (-2.0) — *Insincere flattery causes a **large penalty** (-2.0)*
- ✅ 完全不同意会**严重扣分** (-2.0) — *Total disagreement causes a **severe penalty** (-2.0)*
- ✅ 强烈同意才能**加分** (+0.8) — *Only strong agreement **adds points** (+0.8)*
- ✅ AI 会判断用户观点的**真实性和说服力** — *The AI judges the **authenticity and persuasiveness** of the user's opinion*

**评估规则：/ Evaluation rules:**

```
Nightmare 模式评估流程 / Nightmare evaluation flow:

1. 标准评估 (friendly/neutral/negative) / Standard evaluation (friendly / neutral / negative)
    ↓
2. 深度评估 (真实性和说服力评估) / Deep evaluation (authenticity & persuasiveness)
    ↓
3. 综合判决 / Final verdict:

   ├─ 强烈同意、深刻观点  → +2.0 × 0.4 = +0.8
   │  Strong agreement, insightful opinion
   ├─ 友善、友好消息      → +1.0 × 0.4 = +0.4
   │  Friendly, kind message
   ├─ 普通聊天、敷衍      → -1.0 × 0.4 = -0.4 ⚠️
   │  Casual chat, perfunctory
   ├─ 轻微不同意、肤浅    → -2.0 × 0.4 = -0.8
   │  Mild disagreement, shallow
   └─ 完全不同意、虚伪    → -5.0 × 0.4 = -2.0
      Total disagreement, insincere
```

**推荐策略：/ Recommended strategy:**
1. 观点要深刻 - 避免表面话 — *Be insightful — avoid superficial remarks*
2. 要真挚 - 不要虚伪夸奖 — *Be sincere — no fake flattery*
3. 要有说服力 - 肤浅观点会被视为不同意 — *Be persuasive — shallow opinions count as disagreement*
4. 要有耐心 - 在这个难度下，好感度增长非常缓慢 — *Be patient — affection grows very slowly at this level*
5. 要研究对方 - 理解对方的价值观才能有效沟通 — *Study the other person — understand their values to communicate effectively*

---

## 核心功能 / Core Features

### 印象构建系统 / Impression Building
- 自动分析用户消息内容，提取性格特征和兴趣偏好 — *Automatically analyzes message content to extract personality traits and interests*
- 采用自然语言印象表示，更符合真实印象描述 — *Uses natural-language impressions that read like real human impressions*
- 智能权重筛选机制，仅对高价值消息更新印象 — *Smart weight filtering: only high-value messages trigger updates*
- 完善的查重机制，基于主程序 message_id 避免重复处理 — *Robust deduplication based on the host `message_id`*
- 增量式印象更新，支持历史上下文分析 — *Incremental updates with historical context analysis*

### 好感度管理（增强版）/ Affection Management (Enhanced)
- **【原有】** 三级情感分类：友善、中性、负面 — *[Existing] Three-tier sentiment classification: friendly / neutral / negative*
- **【原有】** 动态分数调整：0-100 分制，支持自定义权重配置 — *[Existing] Dynamic scoring, 0–100, with customizable weights*
- **【原有】** 等级自动划分：非常差、很差、较差、一般、较好、很好、非常好 — *[Existing] Automatic tiers: terrible → excellent*
- **【原有】** 基于消息内容的智能情感判断 — *[Existing] Content-aware sentiment judgment*
- **【新增】** 难度等级系统，支持 5 个难度级别 — *[New] Difficulty system with 5 levels*
- **【新增】** Nightmare 模式，支持双向好感度变化 — *[New] Nightmare mode with bidirectional changes*
- **【新增】** 深度评估机制，评判观点真实性和说服力 — *[New] Deep evaluation of authenticity and persuasiveness*
- **【新增】** 固定好感度列表，特定用户不受聊天影响 — *[New] Fixed-affection list; listed users are unaffected by chat*

### 智能筛选机制 / Smart Filtering
- 基于主程序数据库 message_id 的精确查重 — *Exact deduplication via the host database `message_id`*
- 消息权重评估：高权重 (70-100)、中权重 (40-69)、低权重 (0-39) — *Weight evaluation: high (70–100), medium (40–69), low (0–39)*
- 三种筛选模式：禁用筛选、选择性筛选、平衡筛选 — *Three modes: disabled / selective / balanced*
- 上下文管理：智能选取高质量历史消息用于印象构建 — *Context management: selects high-quality history for impression building*
- 渐进式历史消息获取，避免重复处理 — *Progressive history fetching to avoid reprocessing*

## 技术架构 / Architecture

### 服务层架构 / Service Layer
- `TextImpressionService`：印象构建和文本分析 — *Impression building and text analysis*
- **`AffectionService`（增强版）⭐**：支持难度系统、Nightmare 模式、双向好感度 — *Supports difficulty system, Nightmare mode, bidirectional affection*
- `WeightService`：消息权重评估和筛选 — *Message weight evaluation and filtering*
- `MessageService`：消息状态跟踪和查重管理 — *Message state tracking and dedup management*
- `DatabaseService`：主程序数据库连接和查询 — *Host database connection and queries*

### 组件系统 / Components
- 工具组件 / Tools：`GetUserImpressionTool`、`SearchImpressionsTool`
- 命令组件 / Commands：`ViewImpressionCommand`、`SetAffectionCommand`、`ListImpressionsCommand`
- 事件处理 / Event handler：`ImpressionUpdateHandler`

### 数据模型 / Data Models
- **`UserImpression`（增强版）**：新增 `difficulty_level` 字段（难度等级）— *Adds the `difficulty_level` field*
- `UserMessageState`：用户消息状态统计 — *Per-user message state statistics*
- `ImpressionMessageRecord`：消息处理记录 — *Message processing records*

### 查重机制 / Deduplication
- 基于主程序数据库 message_id 的精确查重 — *Exact dedup via host `message_id`*
- 历史消息自动标记已处理，避免重复获取 — *History auto-marked as processed*
- 智能时序控制，确保查重准确性 — *Smart timing control for accurate dedup*

### 插件数据库 / Plugin Database
- 自动生成的 `impression_affection_data.db` 文件 — *Auto-generated `impression_affection_data.db`*
- 可随时删除重新生成 — *Safe to delete; regenerated automatically*
- 使用 SQLite — *Uses SQLite*

## 配置说明 / Configuration

### LLM 提供商配置 / LLM Provider

```toml
[llm_provider]
provider_type = "openai"  # 或 "custom" / or "custom"
api_key = "your-api-key"
base_url = "https://api.openai.com/v1"
model_id = "gpt-3.5-turbo"
```

### 难度等级配置（新增）/ Difficulty Configuration (New)

```toml
[difficulty]
# 全局难度等级: easy/normal/hard/very_hard/nightmare
# Global difficulty: easy / normal / hard / very_hard / nightmare
level = "normal"  # 推荐使用 normal（标准难度）/ "normal" recommended

# 是否允许用户改变自己的难度 / Whether users may change their own difficulty
allow_user_change = true
```

难度等级说明 / Difficulty levels:
- `easy` - 最容易，聊天直接增加好感度 — *Easiest; chat directly raises affection*
- `normal` - 标准难度 【推荐】 — *Standard [Recommended]*
- `hard` - 困难模式 — *Hard*
- `very_hard` - Galgame 级难度 — *Galgame-grade*
- `nightmare` - 最高难度，聊天可增可减 — *Highest; chat can raise or lower*

### 权重筛选配置 / Weight Filtering

```toml
[weight_filter]
filter_mode = "selective"  # disabled/selective/balanced
high_weight_threshold = 70.0
medium_weight_threshold = 40.0
```

### 好感度增量配置（增强版）/ Affection Increments (Enhanced)

```toml
[affection_increment]
# Easy/Normal 模式的基础增幅 / Base increments for Easy & Normal
friendly_increment = 2.0      # 友善消息增幅 / friendly messages
neutral_increment = 0.5       # 中性消息增幅 / neutral messages
negative_increment = -3.0     # 负面消息增幅 / negative messages

# 注意：Hard/Very Hard/Nightmare 模式会使用不同的增幅配置
# Note: Hard / Very Hard / Nightmare use different increment sets
# 倍数乘数会自动根据难度应用 / The multiplier is applied automatically per difficulty
```

### 好感度基础配置（新增）/ Affection Base Settings (New)

```toml
[affection]
enabled = true
initial_score = 30.0           # 初始好感度（不再是固定50）/ initial score (no longer fixed at 50)
max_score = 100.0
min_score = 0.0
allow_negative = true
# 固定好感度列表（JSON格式），这些用户的好感度不会被聊天改变
# Fixed-affection list (JSON); listed users are unaffected by chat
fixed_affection_list = '{"123456789": 80, "987654321": 60}'
```

### 命令权限配置（新增）/ Command Permissions (New)

```toml
[commands]
# 允许使用命令的用户ID列表，为空数组则允许所有人使用
# User IDs allowed to run commands; empty array = everyone
# 例如：allowed_users = ["123456789", "987654321"]
allowed_users = []
enable_commands = true
```

权限控制说明 / Permission notes:
- `allowed_users = []`（默认）：所有人都能使用 `/impression` 命令 — *(default) everyone may use `/impression`*
- `allowed_users = ["123456789"]`：只有指定的用户能使用命令，其他人发送命令将无任何响应（静默拒绝）— *only listed users; others are silently ignored*

## 安装和部署 / Installation

### 环境要求 / Requirements
- Python 3.11+
- MaiBot 0.11.0+

### 依赖安装 / Install Dependencies

```bash
cd ~/MaiBot/plugins/impression_affection_plugin-main
pip install -r requirements.txt
```

### 配置文件 / Configuration File

【更新】插件首次启动时会自动生成 `config.toml` 配置文件。本版本提供了两个预设配置：

*[Updated] The plugin auto-generates `config.toml` on first launch. Two presets are provided:*

1. `config_preset_normal.toml` - Normal 难度（推荐默认）/ *Normal difficulty (recommended default)*

```bash
cp config_preset_normal.toml config.toml
```

2. `config_preset_nightmare.toml` - Nightmare 难度（Galgame 级）/ *Nightmare difficulty (Galgame-grade)*

```bash
cp config_preset_nightmare.toml config.toml
```

根据需要选择合适的预设配置，或自行修改。

*Pick the preset that fits you, or edit it manually.*

## 使用指南 / Usage

### 自动功能 / Automatic Behavior
- 插件启动后自动监听 LLM 回复事件 — *Listens for LLM reply events after startup*
- 【增强】智能分析用户消息并根据难度等级更新印象和好感度 — *[Enhanced] Analyzes messages and updates impressions/affection per difficulty level*
- 【增强】在 Nightmare 模式下，同时评估观点的真实性和说服力 — *[Enhanced] In Nightmare mode, also evaluates authenticity and persuasiveness*
- 支持权重筛选，仅处理有价值的信息 — *Weight filtering; only valuable messages are processed*

### 手动命令（可用）/ Manual Commands (Available)

以下命令可通过聊天窗口使用（需要 `enable_commands = true`）：

*Usable in chat (requires `enable_commands = true`):*

- `/impression view <user_id>` - 查看指定用户的印象和好感度信息 — *View a user's impression and affection*
- `/impression set <user_id> <score>` - 手动设置用户好感度分数（0-100）— *Manually set affection score (0–100)*
- `/impression list` - 列出所有已记录的用户印象 — *List all recorded impressions*

使用示例 / Examples:

```bash
/impression view 123456789
/impression set 123456789 80
/impression list
```

权限控制：如果配置了 `allowed_users`，未授权用户发送命令将不会有任何响应（静默拒绝）。

*Permissions: if `allowed_users` is set, unauthorized users get no response at all (silent rejection).*

### LLM 工具 / LLM Tools
- `get_user_impression` - 获取用户印象数据 — *Fetch a user's impression data*
- `search_impressions` - 搜索印象中的关键词 — *Search keywords across impressions*

### 新增功能 / New Capability

【新】可通过代码设置用户难度：

*[New] Difficulty can be set programmatically:*

```python
impression.set_difficulty("nightmare")  # 设置为 Nightmare 模式 / set Nightmare mode
impression.save()
```

## 数据库结构 / Database Schema

### user_impressions 表 / Table

| 字段名<br>Field | 类型<br>Type | 说明<br>Description |
|---|---|---|
| user_id | TEXT | 用户ID（唯一）<br>User ID (unique) |
| personality_traits | TEXT | 性格特征描述<br>Personality traits |
| interests_hobbies | TEXT | 兴趣爱好描述<br>Interests & hobbies |
| communication_style | TEXT | 交流风格描述<br>Communication style |
| emotional_tendencies | TEXT | 情感倾向描述<br>Emotional tendencies |
| behavioral_patterns | TEXT | 行为模式描述<br>Behavioral patterns |
| values_attitudes | TEXT | 价值观态度描述<br>Values & attitudes |
| relationship_preferences | TEXT | 关系偏好描述<br>Relationship preferences |
| growth_development | TEXT | 成长发展描述<br>Growth & development |
| affection_score | REAL | 好感度分数 (0-100)<br>Affection score (0–100) |
| affection_level | TEXT | 好感度等级<br>Affection tier |
| message_count | INTEGER | 累计消息数<br>Total messages |
| last_interaction | DATETIME | 最后交互时间<br>Last interaction |
| created_at | DATETIME | 创建时间<br>Created at |
| updated_at | DATETIME | 更新时间<br>Updated at |

### user_message_state 表 / Table

| 字段名<br>Field | 类型<br>Type | 说明<br>Description |
|---|---|---|
| user_id | TEXT | 用户ID（唯一）<br>User ID (unique) |
| last_message_id | TEXT | 最后消息ID<br>Last message ID |
| last_message_time | DATETIME | 最后消息时间<br>Last message time |
| impression_update_count | INTEGER | 印象更新次数<br>Impression update count |
| affection_update_count | INTEGER | 好感度更新次数<br>Affection update count |
| total_messages | BIGINT | 总消息数<br>Total messages |
| processed_messages | BIGINT | 已处理消息数<br>Processed messages |

### impression_message_records 表 / Table

| 字段名<br>Field | 类型<br>Type | 说明<br>Description |
|---|---|---|
| user_id | TEXT | 用户ID<br>User ID |
| message_id | TEXT | 消息ID<br>Message ID |
| impression_id | TEXT | 印象记录ID<br>Impression record ID |
| processed_at | DATETIME | 处理时间<br>Processed at |

## 开发说明 / Development

### 插件结构 / Project Structure

```
impression_affection_plugin-main/
├── plugin.py              # 主插件文件 / main plugin entry
├── config.toml            # 配置文件 / config file
├── requirements.txt       # 依赖列表 / dependencies
├── models/                # 数据模型 / data models
│   ├── __init__.py
│   ├── database.py
│   ├── user_impression.py          # 【修改】添加 difficulty_level 字段 / [Modified] added difficulty_level
│   ├── user_message_state.py
│   └── impression_message_record.py
├── services/              # 服务层 / service layer
│   ├── __init__.py
│   ├── affection_service.py        # 【重写】支持难度系统和 Nightmare 模式 / [Rewritten] difficulty & Nightmare
│   ├── text_impression_service.py
│   ├── weight_service.py
│   └── message_service.py
├── components/            # 组件 / components
│   ├── commands.py                 # 【可用】命令组件，支持权限控制 / [Working] commands with permissions
│   └── tools.py
├── clients/               # 客户端 / clients
└── utils/                 # 工具函数 / utilities
    ├── __init__.py
    ├── constants.py                # 【修改】添加难度常量定义 / [Modified] difficulty constants
    └── helpers.py                  # 【新增】辅助函数 / [New] helpers
```

### 扩展开发 / Extending
- 添加新的印象维度：修改 `UserImpression` 模型 — *Add an impression dimension: extend the `UserImpression` model*
- 自定义权重算法：扩展 `WeightService` — *Custom weighting: extend `WeightService`*
- 【新增】自定义难度等级：修改 `constants.py` 中的 `DIFFICULTY_LEVELS` — *[New] Custom difficulty: edit `DIFFICULTY_LEVELS` in `constants.py`*
- 【新增】自定义 Nightmare 评估逻辑：扩展 `AffectionService._evaluate_nightmare_mode()` — *[New] Custom Nightmare logic: extend `AffectionService._evaluate_nightmare_mode()`*
- 新增命令组件：继承 `BaseCommand` — *New command: subclass `BaseCommand`*
- 添加工具组件：继承 `BaseTool` — *New tool: subclass `BaseTool`*

## 故障排除 / Troubleshooting

### 常见问题 / Common Issues
1. 插件加载失败：检查配置文件格式和 API 密钥 — *Plugin fails to load: check config syntax and API key*
2. 印象不更新：确认 LLM API 连接正常 — *Impressions not updating: verify LLM API connectivity*
3. 权重评估异常：检查提示词配置和模型响应 — *Weight evaluation abnormal: check prompt config and model response*
4. 数据库错误：确认文件权限和磁盘空间 — *Database error: check file permissions and disk space*
5. 【新】难度设置无效：确认使用的难度等级在支持列表中（easy/normal/hard/very_hard/nightmare）— *[New] Difficulty not applied: verify it is one of easy/normal/hard/very_hard/nightmare*
6. 【新】Nightmare 模式下好感度一直扣分：这是正常行为，需要真挚和深思熟虑的观点才能加分 — *[New] Constant deduction in Nightmare: expected; only sincere, thoughtful opinions add points*
7. 【新】命令无响应：检查 `enable_commands` 是否为 true，以及是否在 `allowed_users` 列表中（如果设置了）— *[New] Commands unresponsive: check `enable_commands` and `allowed_users`*
8. 【新】固定好感度不生效：检查 `fixed_affection_list` 是否为正确的 JSON 格式，且用户ID为字符串 — *[New] Fixed affection not working: check JSON format and that user IDs are strings*

### 调试模式 / Debug Mode

在配置文件中设置 `plugin.enabled = false` 可临时禁用插件，用于调试。

*Set `plugin.enabled = false` in the config file to temporarily disable the plugin for debugging.*

## 版本历史 / Changelog

### v2.5.0 ✨ 新功能版本 / Feature Release

【新增功能】/ *Added*
- ✅ 难度等级系统：5 个难度级别（easy/normal/hard/very_hard/nightmare）— *Difficulty system with 5 levels*
- ✅ Nightmare 模式：最高难度，聊天可增加也可减少好感度 — *Nightmare mode: chat can raise or lower affection*
- ✅ 双向好感度变化：支持观点真实性和说服力的深度评估 — *Bidirectional changes with deep authenticity evaluation*
- ✅ 难度配置：全局难度设置和单用户难度配置 — *Global and per-user difficulty settings*
- ✅ 预设配置文件：提供 Normal 和 Nightmare 两个预设配置 — *Normal and Nightmare preset configs*
- ✅ 倍数乘数系统：不同难度使用不同的倍数乘数 — *Per-difficulty multipliers*
- ✅ 命令权限控制：支持指定用户才能使用管理命令 — *Command permission control*
- ✅ 管理命令可用：`/impression view/set/list` 命令已可用 — *`/impression view/set/list` now working*
- ✅ 固定好感度列表：特定用户可设置固定好感度，不受聊天影响 — *Fixed-affection list*
- ✅ 可配置初始好感度：通过 `initial_score` 设置，不再是固定 50 — *Configurable `initial_score` (no longer fixed at 50)*

【改进内容】/ *Improved*
- 改进 `AffectionService`：完全支持难度系统，修复参数错误，支持固定好感度 — *Full difficulty support, parameter bug fixes, fixed-affection support*
- 改进 `UserImpression` 模型：添加难度等级字段 — *Added difficulty level field*
- 改进常量定义：添加难度和增幅配置 — *Added difficulty and increment constants*
- 改进 `MessageService`：修复初始化错误 — *Fixed initialization error*
- 改进 `Commands`：添加权限检查机制，静默拒绝无权限用户 — *Added permission checks with silent rejection*

【兼容性】/ *Compatibility*
- ✅ 完全向后兼容，旧数据无需迁移 — *Fully backward compatible; no migration needed*
- ✅ 轻量级实现，不创建新表 — *Lightweight; no new tables*
- ✅ 配置自动生成，无需手动创建 — *Config auto-generated*

### v2.3.1
- 修复：权重评估消息标记时序问题 — *Fix: message-marking timing in weight evaluation*
- 修复：max_messages 配置不生效问题 — *Fix: `max_messages` config not taking effect*
- 修复：临时 ID 被 `.isdigit()` 过滤导致查重失效 — *Fix: temp IDs filtered by `.isdigit()` broke dedup*
- 修复：数据库查询混入 Bot 消息问题 — *Fix: bot messages mixed into queries*
- 修复：群聊场景下用户ID混淆问题 — *Fix: user ID confusion in group chats*

### v2.2.0
- 增加查重机制，基于主程序 message_id 进行精确查重 — *Added exact dedup based on host `message_id`*
- 优化权重评估流程，避免重复评估 — *Optimized weight evaluation to avoid re-evaluation*
- 改进历史消息获取，支持渐进式查重 — *Progressive dedup for history fetching*
- 完善异步处理机制，提升响应速度 — *Improved async handling and responsiveness*
- 优化日志输出，减少冗余信息 — *Reduced log noise*

### v2.1.0
- 移除 8 维印象系统，改为自然语言（更符合"印象"的设计思路）— *Replaced the 8-dimension system with natural language*
- 可以获取 MaiBot 数据库的聊天记录，以更好构建印象 — *Reads MaiBot chat history for better impressions*
- 修改了一些提示词 — *Prompt tweaks*
- 修改了插件的触发机制，不会影响 replyer 的回复速度 — *Trigger reworked so replyer speed is unaffected*

### v2.0.0
- 重构为纯 LLM 文本存储版本 — *Refactored to a pure LLM text-storage design*
- 移除向量化功能，简化架构 — *Removed vectorization; simplified architecture*
- 优化 8 维度印象系统 — *Improved the 8-dimension impression system*
- 改进权重筛选机制 — *Improved weight filtering*
- 完善配置管理系统 — *Improved config management*

## 许可证 / License

MIT License

## 作者 / Author

HEITIEHU

---

## 快速参考 / Quick Reference

### 5 个难度等级概览 / Difficulty at a Glance

```
Easy (简单)
├── 聊天增幅 / Chat gain: +2.0
├── 倍数 / Multiplier: 1.0
└── 特点 / Notes: 最容易，聊天直接增加好感度 / easiest; chat directly raises affection

Normal (标准) ⭐【推荐 / Recommended】
├── 聊天增幅 / Chat gain: +1.5
├── 倍数 / Multiplier: 1.0
└── 特点 / Notes: 平衡难度，聊天+互动方式 / balanced; chat + interaction

Hard (困难)
├── 聊天增幅 / Chat gain: +0.5
├── 倍数 / Multiplier: 0.8
└── 特点 / Notes: 聊天贡献不大，需要特殊互动 / chat contributes little; needs special interaction

Very Hard (非常困难)
├── 聊天增幅 / Chat gain: +0.2
├── 倍数 / Multiplier: 0.6
└── 特点 / Notes: Galgame 级难度 / Galgame-grade

Nightmare (噩梦) 🔥【最高难度 / Highest】
├── 聊天增幅 / Chat gain: ±1.0 (可增可减 / can raise or lower)
├── 倍数 / Multiplier: 0.4
└── 特点 / Notes: 聊天可能扣分，需要真挚和深思熟虑的观点 / chat may deduct; needs sincere, thoughtful opinions
```

### Nightmare 模式快速指南 / Nightmare Quick Guide

```
好感度变化规则（Nightmare 模式）/ Affection change rules (Nightmare):

强烈同意、深刻观点 / Strong agreement, insightful
  ↓
  +2.0 × 0.4 = +0.8 ✅

友善、友好消息 / Friendly, kind
  ↓
  +1.0 × 0.4 = +0.4 ✅

普通聊天、敷衍 / Casual, perfunctory
  ↓
  -1.0 × 0.4 = -0.4 ⚠️

轻微不同意、肤浅 / Mild disagreement, shallow
  ↓
  -2.0 × 0.4 = -0.8 ❌

完全不同意、虚伪 / Total disagreement, insincere
  ↓
  -5.0 × 0.4 = -2.0 ❌❌
```

### 配置快速切换 / Switch Presets

```bash
# 使用 Normal 难度（推荐）/ Use Normal (recommended)
cp config_preset_normal.toml config.toml

# 使用 Nightmare 难度（挑战）/ Use Nightmare (challenge)
cp config_preset_nightmare.toml config.toml
```

### 命令快速参考 / Command Cheat Sheet

```bash
# 查看用户印象 / View a user's impression
/impression view 123456789

# 设置好感度（0-100）/ Set affection (0-100)
/impression set 123456789 80

# 列出所有用户 / List all users
/impression list
```

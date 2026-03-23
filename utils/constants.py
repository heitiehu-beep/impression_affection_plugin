"""
常量定义
"""

# 好感度等级定义
AFFECTION_LEVELS = {
    (90, 100): "非常好",
    (80, 89): "很好",
    (70, 79): "较好",
    (50, 69): "一般",
    (30, 49): "较差",
    (10, 29): "很差",
    (0, 9): "非常差",
}

# 权重等级
WEIGHT_LEVELS = {
    "high": "高权重",
    "medium": "中权重",
    "low": "低权重"
}

# 评论类型
COMMENT_TYPES = {
    "friendly": "友善",
    "neutral": "中性",
    "negative": "差劲"
}

# 难度等级定义
DIFFICULTY_LEVELS = {
    "easy": {
        "name": "简单",
        "description": "聊天即可增加好感度，友好消息+2.0，中性+0.5，负面-3.0",
        "chat_affects": True,  # 聊天直接增加
        "multiplier": 1.0,
        "allow_negative": True  # 允许降低好感度
    },
    "normal": {
        "name": "标准",
        "description": "聊天+互动方式，需要一定的互动才能有效增加好感度",
        "chat_affects": True,
        "multiplier": 1.0,
        "allow_negative": True
    },
    "hard": {
        "name": "困难",
        "description": "需要特殊互动和表现，聊天贡献不大。需要完成特定任务或表现",
        "chat_affects": False,
        "multiplier": 0.8,
        "allow_negative": True
    },
    "very_hard": {
        "name": "非常困难",
        "description": "Galgame级难度。需要特定的对话内容、时机和表现组合",
        "chat_affects": False,
        "multiplier": 0.6,
        "allow_negative": True
    },
    "nightmare": {
        "name": "噩梦",
        "description": "最高难度。聊天可增加也可降低好感度，取决于人工智能的判断。完全不同意会扣分。",
        "chat_affects": True,  # 特殊：可增加也可减少
        "multiplier": 0.4,
        "allow_negative": True,
        "is_nightmare": True,  # 特殊标记
        "disagreement_penalty": 5.0,  # 完全不同意时扣分
        "minor_disagreement_penalty": 2.0  # 轻微不同意时扣分
    }
}

# 好感度增幅定义
AFFECTION_INCREMENTS = {
    "easy": {
        "friendly": 2.0,
        "neutral": 0.5,
        "negative": -3.0,
    },
    "normal": {
        "friendly": 1.5,
        "neutral": 0.3,
        "negative": -2.5,
    },
    "hard": {
        "friendly": 0.5,
        "neutral": 0.1,
        "negative": -1.5,
    },
    "very_hard": {
        "friendly": 0.2,
        "neutral": 0.0,
        "negative": -1.0,
    },
    "nightmare": {
        "friendly": 1.0,      # 非常同意时增加
        "neutral": -1.0,      # 普通聊天会扣分
        "negative": -5.0,     # 完全不同意大幅扣分
        # 特殊评价
        "strong_agreement": 2.0,      # 强烈同意
        "minor_disagreement": -2.0,   # 轻微不同意
        "strong_disagreement": -5.0   # 强烈不同意
    }
}

# 默认配置
DEFAULT_CONFIG = {
    "plugin": {
        "enabled": True,
        "config_version": "3.0.0"
    },
    "difficulty": {
        "level": "normal",
        "allow_user_change": True
    },
    "affection_increment": {
        "friendly_increment": 2.0,
        "neutral_increment": 0.5,
        "negative_increment": -3.0
    },
    "commands": {
        "allowed_users": [],
        "enable_commands": True
    },
    "features": {
        "auto_update": True,
        "enable_commands": True,
        "enable_tools": True,
        "enable_difficulty_system": True
    }
}

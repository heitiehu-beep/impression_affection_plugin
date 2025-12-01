"""
常量定义
"""

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

# 默认配置
DEFAULT_CONFIG = {
    "plugin": {
        "enabled": True,
        "config_version": "2.0.0"
    },
    "llm_provider": {
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1"
    },
    "impression": {
        "max_context_entries": 30
    },
    "weight_filter": {
        "filter_mode": "selective",
        "high_weight_threshold": 70.0,
        "medium_weight_threshold": 40.0
    },
    "affection_increment": {
        "friendly_increment": 2.0,
        "neutral_increment": 0.5,
        "negative_increment": -3.0
    },
    "features": {
        "auto_update": True,
        "enable_commands": True,
        "enable_tools": True
    }
}

"""
工具函数
"""

from typing import Dict, Tuple, Any


def get_affection_level(score: float) -> str:
    """
    根据分数获取好感度等级

    Args:
        score: 好感度分数 (0-100)

    Returns:
        好感度等级字符串
    """
    from .constants import AFFECTION_LEVELS

    if not isinstance(score, (int, float)):
        return "一般"

    score = float(score)

    for (min_score, max_score), level in AFFECTION_LEVELS.items():
        if min_score <= score <= max_score:
            return level

    return "一般"


def validate_config(config: Dict[str, Any], required_keys: list) -> Tuple[bool, str]:
    """
    验证配置

    Args:
        config: 配置字典
        required_keys: 必需的键列表

    Returns:
        (是否有效, 错误信息)
    """
    for key in required_keys:
        if key not in config:
            return False, f"缺少配置项: {key}"

        if not config[key]:
            return False, f"配置项为空: {key}"

    return True, ""


def safe_json_parse(json_str: str) -> Dict[str, Any]:
    """
    安全地解析JSON字符串

    Args:
        json_str: JSON字符串

    Returns:
        解析后的字典
    """
    import json
    import re

    try:
        return json.loads(json_str.strip())
    except json.JSONDecodeError:
        # 尝试提取JSON
        json_match = re.search(r'\{.*\}', json_str, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except:
                pass
    return {}

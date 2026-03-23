"""
用户印象模型
"""

from peewee import Model, TextField, FloatField, IntegerField, DateTimeField
from datetime import datetime
from .database import db
from ..utils.constants import DIFFICULTY_LEVELS  # 修复：从常量导入


class UserImpression(Model):
    """用户印象模型 - 存储用户的性格特征和行为模式

    """

    user_id = TextField(index=True, unique=True)

    # 多维度文本印象字段
    personality_traits = TextField(default="")  # 性格特征描述
    interests_hobbies = TextField(default="")     # 兴趣爱好描述
    communication_style = TextField(default="")  # 交流风格描述
    emotional_tendencies = TextField(default="")  # 情感倾向描述
    behavioral_patterns = TextField(default="")  # 行为模式描述
    values_attitudes = TextField(default="")     # 价值观态度描述
    relationship_preferences = TextField(default="")  # 关系偏好描述
    growth_development = TextField(default="")    # 成长发展描述

    # 好感度信息
    affection_score = FloatField(default=50.0)  # 好感度分数(0-100)
    affection_level = TextField(default="一般")  # 好感度等级

    difficulty_level = TextField(default="normal")  # 难度等级: easy/normal/hard/very_hard/nightmare

    # 统计信息
    message_count = IntegerField(default=0)  # 累计消息数
    last_interaction = DateTimeField(default=datetime.now)  # 最后交互时间

    # 印象版本控制
    impression_version = IntegerField(default=1)  # 印象版本号
    previous_impression = TextField(default="")  # 上一次的印象(用于对比)
    impression_update_count = IntegerField(default=0)  # 印象更新次数

    # 时间戳
    created_at = DateTimeField(default=datetime.now)
    updated_at = DateTimeField(default=datetime.now)

    class Meta:
        database = db
        table_name = "user_impressions"
        indexes = (
            (('user_id', 'updated_at'), False),  # 复合索引用于查询
        )

    def update_timestamps(self):
        """更新时间戳"""
        self.updated_at = datetime.now()

    def set_difficulty(self, difficulty_level: str):
        """设置难度等级"""
        valid_levels = list(DIFFICULTY_LEVELS.keys())
        if difficulty_level in valid_levels:
            self.difficulty_level = difficulty_level
            self.update_timestamps()
        else:
            raise ValueError(f"无效的难度等级: {difficulty_level}，有效等级: {valid_levels}")

    def increment_impression_version(self):
        """增加印象版本号"""
        self.impression_version += 1
        self.impression_update_count += 1
        self.update_timestamps()

    def set_impression_with_version(self, new_impression: str):
        """设置新印象并更新版本信息"""
        # 保存当前印象为历史印象
        if self.personality_traits:
            self.previous_impression = self.personality_traits

        # 设置新印象
        self.personality_traits = new_impression

        # 更新版本信息
        self.increment_impression_version()

    def get_impression_change_summary(self) -> str:
        """获取印象变化摘要"""
        if not self.previous_impression:
            return f"初始印象 (版本 {self.impression_version})"

        return f"从版本 {self.impression_version - 1} 更新到版本 {self.impression_version}"

    def get_impression_summary(self) -> str:
        """获取印象摘要"""
        dimensions = []

        if self.personality_traits.strip():
            dimensions.append(f"性格: {self.personality_traits}")
        if self.interests_hobbies.strip():
            dimensions.append(f"兴趣: {self.interests_hobbies}")
        if self.communication_style.strip():
            dimensions.append(f"交流: {self.communication_style}")
        if self.emotional_tendencies.strip():
            dimensions.append(f"情感: {self.emotional_tendencies}")
        if self.behavioral_patterns.strip():
            dimensions.append(f"行为: {self.behavioral_patterns}")
        if self.values_attitudes.strip():
            dimensions.append(f"价值观: {self.values_attitudes}")
        if self.relationship_preferences.strip():
            dimensions.append(f"关系: {self.relationship_preferences}")
        if self.growth_development.strip():
            dimensions.append(f"成长: {self.growth_development}")

        return " | ".join(dimensions) if dimensions else "暂无印象数据"

    def set_dimension(self, dimension: str, content: str):
        """设置特定维度的内容"""
        dimension_map = {
            "personality": "personality_traits",
            "interests": "interests_hobbies",
            "communication": "communication_style",
            "emotional": "emotional_tendencies",
            "behavior": "behavioral_patterns",
            "values": "values_attitudes",
            "relationship": "relationship_preferences",
            "growth": "growth_development"
        }

        if dimension in dimension_map:
            setattr(self, dimension_map[dimension], content)
            self.update_timestamps()
        else:
            raise ValueError(f"未知维度: {dimension}")

    def get_dimension(self, dimension: str) -> str:
        """获取特定维度的内容"""
        dimension_map = {
            "personality": "personality_traits",
            "interests": "interests_hobbies",
            "communication": "communication_style",
            "emotional": "emotional_tendencies",
            "behavior": "behavioral_patterns",
            "values": "values_attitudes",
            "relationship": "relationship_preferences",
            "growth": "growth_development"
        }

        return getattr(self, dimension_map.get(dimension, ""), "")

"""
用户印象模型 - 纯文本多维度版本
"""

from peewee import Model, TextField, FloatField, IntegerField, DateTimeField
from datetime import datetime
from .database import db


class UserImpression(Model):
    """用户印象模型 - 存储用户的性格特征和行为模式"""

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

    # 统计信息
    message_count = IntegerField(default=0)  # 累计消息数
    last_interaction = DateTimeField(default=datetime.now)  # 最后交互时间
    
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

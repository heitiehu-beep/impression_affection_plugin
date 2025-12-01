"""
LLM客户端 - 统一的LLM API调用接口
"""

import json
from typing import Dict, Any, Tuple, Optional
from abc import ABC, abstractmethod


class BaseLLMProvider(ABC):
    """LLM提供商基类"""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> Tuple[bool, str]:
        """生成文本"""
        pass


class OpenAIProvider(BaseLLMProvider):
    """OpenAI格式提供商"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key")
        self.base_url = config.get("base_url", "https://api.openai.com/v1")
        self.model_id = config.get("model_id")

    async def generate(self, prompt: str, **kwargs) -> Tuple[bool, str]:
        """使用OpenAI API生成文本"""
        try:
            import openai

            client = openai.AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

            temperature = kwargs.get("temperature", 0.3)
            max_tokens = kwargs.get("max_tokens", 200)

            response = await client.chat.completions.create(
                model=self.model_id,
                messages=[{"role": "user", "content": prompt}],
                temperature=temperature,
                max_tokens=max_tokens
            )

            content = response.choices[0].message.content
            return True, content

        except Exception as e:
            return False, f"OpenAI API调用失败: {str(e)}"


class CustomProvider(BaseLLMProvider):
    """自定义API提供商"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.api_key = config.get("api_key")
        self.api_endpoint = config.get("api_endpoint")
        self.model_id = config.get("model_id")

    async def generate(self, prompt: str, **kwargs) -> Tuple[bool, str]:
        """使用自定义API生成文本"""
        try:
            import httpx

            temperature = kwargs.get("temperature", 0.3)
            max_tokens = kwargs.get("max_tokens", 200)

            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    self.api_endpoint,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": self.model_id,
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": temperature,
                        "max_tokens": max_tokens
                    }
                )

                response.raise_for_status()
                result = response.json()

                # 根据不同API格式解析
                if "choices" in result:
                    content = result["choices"][0]["message"]["content"]
                elif "content" in result:
                    content = result["content"]
                else:
                    return False, "API返回格式未知"

                return True, content

        except Exception as e:
            return False, f"自定义API调用失败: {str(e)}"


class LLMClient:
    """LLM客户端 - 统一的LLM调用接口"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.provider_type = config.get("provider_type", "openai")
        self.provider = self._create_provider()

    def _create_provider(self) -> BaseLLMProvider:
        """创建提供商实例"""
        if self.provider_type == "openai":
            return OpenAIProvider(self.config)
        elif self.provider_type == "custom":
            return CustomProvider(self.config)
        else:
            raise ValueError(f"不支持的提供商类型: {self.provider_type}")

    async def generate(self, prompt: str, **kwargs) -> Tuple[bool, str]:
        """生成文本"""
        if not self.config.get("api_key") or not self.config.get("model_id"):
            return False, "LLM未配置: 缺少api_key或model_id"

        return await self.provider.generate(prompt, **kwargs)

    async def generate_impression_analysis(self, prompt: str) -> Tuple[bool, str]:
        """生成印象分析 - 专用接口"""
        # 进一步增大max_tokens，确保有足够的空间返回完整的JSON
        # 印象分析需要更多token，因为需要生成印象描述和原因
        # 增大到2000，避免响应被截断
        return await self.generate(prompt, temperature=0.3, max_tokens=2000)

    async def generate_affection_analysis(self, prompt: str) -> Tuple[bool, str]:
        """生成好感度分析 - 专用接口"""
        # 增大max_tokens，确保返回完整的JSON
        return await self.generate(prompt, temperature=0.3, max_tokens=1500)

    async def generate_weight_evaluation(self, prompt: str) -> Tuple[bool, str]:
        """生成权重评估 - 专用接口"""
        # 增大max_tokens
        return await self.generate(prompt, temperature=0.2, max_tokens=1000)

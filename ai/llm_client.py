"""
ai/llm_client.py — DeepSeek API 统一调用封装（OpenAI 兼容 SDK）
"""
from __future__ import annotations
import json
import time
from typing import Optional, Dict, List
from loguru import logger

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning("openai 库未安装，AI功能不可用。请运行: pip install openai")


class LLMClient:
    """
    DeepSeek API 封装，兼容 OpenAI SDK。
    内置：每日 token 预算控制、重试机制、JSON解析。
    """

    def __init__(self, config: dict):
        self.config = config.get("ai", {})
        self.enabled = self.config.get("enabled", False)
        self.api_key = self.config.get("api_key", "")
        self.api_base = self.config.get("api_base_url", "https://api.deepseek.com")
        self.model = self.config.get("model", "deepseek-chat")
        self.max_tokens = self.config.get("max_tokens", 2000)
        self.temperature = self.config.get("temperature", 0.1)
        self.daily_budget = self.config.get("daily_token_budget", 200000)
        self._daily_used: int = 0
        self._client = None

        if self.enabled and self.api_key:
            self._init_client()

    def _init_client(self):
        if not OPENAI_AVAILABLE:
            logger.error("openai 库未安装，无法初始化 DeepSeek 客户端")
            self.enabled = False
            return
        try:
            self._client = OpenAI(api_key=self.api_key, base_url=self.api_base)
            logger.info(f"✅ DeepSeek 客户端初始化成功（模型: {self.model}）")
        except Exception as e:
            logger.error(f"❌ DeepSeek 客户端初始化失败: {e}")
            self.enabled = False

    def chat(self, messages: List[Dict], system: str = None,
             max_tokens: int = None, retries: int = 3) -> Optional[str]:
        """
        发送对话请求，返回文本响应。
        支持自动重试 + token 预算检查。
        """
        if not self.enabled or not self._client:
            logger.debug("AI未启用或未配置，跳过LLM调用")
            return None

        if self._daily_used >= self.daily_budget:
            logger.warning(f"今日Token预算已耗尽（{self._daily_used}/{self.daily_budget}），跳过AI调用")
            return None

        full_messages = []
        if system:
            full_messages.append({"role": "system", "content": system})
        full_messages.extend(messages)

        for attempt in range(retries):
            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=full_messages,
                    max_tokens=max_tokens or self.max_tokens,
                    temperature=self.temperature,
                )
                content = response.choices[0].message.content
                tokens = response.usage.total_tokens if response.usage else 0
                self._daily_used += tokens
                logger.debug(f"LLM调用成功，消耗{tokens}Token，今日已用{self._daily_used}/{self.daily_budget}")
                return content
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"LLM调用失败（第{attempt+1}次）: {e}，等待{wait}s重试")
                time.sleep(wait)

        logger.error("LLM调用连续失败，放弃")
        return None

    def chat_json(self, messages: List[Dict], system: str = None,
                  max_tokens: int = None) -> Optional[Dict]:
        """
        调用LLM并解析JSON响应。
        自动处理 ```json ... ``` 包裹。
        """
        response = self.chat(messages, system, max_tokens)
        if not response:
            return None
        return self._parse_json(response)

    @staticmethod
    def _parse_json(text: str) -> Optional[Dict]:
        """解析LLM返回的JSON，支持多种格式"""
        text = text.strip()
        # 去除 markdown 代码块
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.rfind("```")
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.rfind("```")
            text = text[start:end].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # 尝试提取第一个 { ... }
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except Exception:
                    pass
            logger.warning(f"JSON解析失败，原始响应: {text[:200]}")
            return None

    @property
    def daily_used(self) -> int:
        return self._daily_used

    @property
    def daily_remaining(self) -> int:
        return max(0, self.daily_budget - self._daily_used)

    def reset_daily_counter(self):
        self._daily_used = 0
        logger.info("每日Token计数已重置")

    def is_available(self) -> bool:
        return self.enabled and self._client is not None

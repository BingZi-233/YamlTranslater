"""
OpenAI API 客户端模块
"""
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

import aiohttp
import backoff
from pydantic import BaseModel

from ..config import APIConfig
from ..utils import APIError, RateLimitError, log


@dataclass
class APIUsage:
    """API 使用情况"""
    prompt_tokens: int  # 提示词使用的token数
    completion_tokens: int  # 补全使用的token数
    total_tokens: int  # 总token数
    estimated_cost: float  # 估算成本（美元）


class ChatMessage(BaseModel):
    """聊天消息"""
    role: str  # 角色：system, user, assistant
    content: str  # 消息内容


class ChatResponse(BaseModel):
    """聊天响应"""
    id: str  # 响应ID
    choices: List[Dict[str, Any]]  # 响应选项列表
    usage: Dict[str, int]  # 使用情况
    created: int  # 创建时间戳


class OpenAIClient:
    """OpenAI API 客户端"""

    def __init__(self, config: APIConfig):
        """初始化 OpenAI API 客户端
        
        Args:
            config: API配置
        """
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self._last_request_time = 0.0
        self._request_count = 0
        self._total_tokens = 0
        
        # 初始化请求头
        self._headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.key}",
        }

    async def __aenter__(self):
        """异步上下文管理器入口"""
        if not self._session:
            self._session = aiohttp.ClientSession(
                base_url=self.config.endpoint,
                headers=self._headers,
            )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """异步上下文管理器出口"""
        if self._session:
            await self._session.close()
            self._session = None

    @backoff.on_exception(
        backoff.expo,
        (aiohttp.ClientError, RateLimitError),
        max_tries=3,
        max_time=30,
    )
    async def translate(self, text: str, system_prompt: str) -> str:
        """翻译文本
        
        Args:
            text: 要翻译的文本
            system_prompt: 系统提示词
            
        Returns:
            str: 翻译后的文本
            
        Raises:
            APIError: API调用错误
            RateLimitError: 达到速率限制
        """
        try:
            # 构建消息列表
            messages = [
                ChatMessage(role="system", content=system_prompt),
                ChatMessage(role="user", content=text),
            ]
            
            # 调用API
            response = await self._chat_completion(messages)
            
            # 提取翻译结果
            if not response.choices:
                raise APIError("Empty response from API")
            
            translated_text = response.choices[0].get("message", {}).get("content", "")
            if not translated_text:
                raise APIError("No translation in response")
            
            # 更新统计信息
            self._update_stats(response.usage)
            
            return translated_text
            
        except aiohttp.ClientError as e:
            log.error(f"API request failed: {str(e)}")
            raise APIError("API request failed", details=str(e))
        except Exception as e:
            log.error(f"Translation failed: {str(e)}")
            raise APIError("Translation failed", details=str(e))

    async def _chat_completion(self, messages: List[ChatMessage]) -> ChatResponse:
        """调用聊天补全API
        
        Args:
            messages: 消息列表
            
        Returns:
            ChatResponse: API响应
            
        Raises:
            APIError: API调用错误
            RateLimitError: 达到速率限制
        """
        if not self._session:
            raise APIError("Client session not initialized")
        
        # 检查并等待速率限制
        await self._wait_for_rate_limit()
        
        try:
            # 准备请求数据
            data = {
                "model": self.config.model,
                "messages": [msg.dict() for msg in messages],
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
            }
            
            # 发送请求
            async with self._session.post("/v1/chat/completions", json=data) as response:
                # 更新请求计数和时间
                self._request_count += 1
                self._last_request_time = time.time()
                
                # 检查响应状态
                if response.status == 429:
                    raise RateLimitError("API rate limit exceeded")
                elif response.status != 200:
                    error_data = await response.text()
                    raise APIError(f"API request failed with status {response.status}", details=error_data)
                
                # 解析响应
                response_data = await response.json()
                return ChatResponse(**response_data)
                
        except aiohttp.ClientError as e:
            log.error(f"API request failed: {str(e)}")
            raise APIError("API request failed", details=str(e))
        except json.JSONDecodeError as e:
            log.error(f"Failed to parse API response: {str(e)}")
            raise APIError("Failed to parse API response", details=str(e))
        except Exception as e:
            log.error(f"Chat completion failed: {str(e)}")
            raise APIError("Chat completion failed", details=str(e))

    async def _wait_for_rate_limit(self) -> None:
        """等待速率限制
        
        根据配置的速率限制计算等待时间
        """
        if self._request_count >= self.config.rate_limit:
            # 计算距离上次请求的时间
            elapsed = time.time() - self._last_request_time
            
            # 如果时间不足1分钟，则等待
            if elapsed < 60:
                wait_time = 60 - elapsed
                log.debug(f"Rate limit reached, waiting for {wait_time:.2f} seconds")
                await asyncio.sleep(wait_time)
            
            # 重置计数器
            self._request_count = 0

    def _update_stats(self, usage: Dict[str, int]) -> None:
        """更新API使用统计
        
        Args:
            usage: API使用情况
        """
        self._total_tokens += usage.get("total_tokens", 0)

    def get_usage(self) -> APIUsage:
        """获取API使用情况
        
        Returns:
            APIUsage: API使用统计
        """
        return APIUsage(
            prompt_tokens=0,  # TODO: 实现详细统计
            completion_tokens=0,  # TODO: 实现详细统计
            total_tokens=self._total_tokens,
            estimated_cost=self._calculate_cost(self._total_tokens),
        )

    @staticmethod
    def _calculate_cost(tokens: int) -> float:
        """计算API使用成本
        
        Args:
            tokens: 使用的token数
            
        Returns:
            float: 成本（美元）
        """
        # 使用GPT-3.5-turbo的价格：$0.002 per 1K tokens
        return (tokens / 1000) * 0.002 
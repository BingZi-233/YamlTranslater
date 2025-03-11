"""
翻译模块
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Union

import openai
from openai import AsyncOpenAI
from pydantic import BaseModel

from ..config import APIConfig, BlacklistConfig, TranslationConfig
from ..utils import (
    APIError,
    AuthenticationError,
    NetworkError,
    RateLimitError,
    TimeoutError,
    TranslationError,
    log,
)


class TranslationRequest(BaseModel):
    """翻译请求模型"""
    text: str
    prompt: str
    model: str
    max_tokens: int
    temperature: float


class TranslationResponse(BaseModel):
    """翻译响应模型"""
    translated_text: str
    tokens_used: int
    model_used: str
    time_taken: float


class Translator:
    """翻译器"""

    def __init__(
        self,
        api_config: APIConfig,
        translation_config: TranslationConfig,
        blacklist_config: BlacklistConfig,
    ):
        """初始化翻译器
        
        Args:
            api_config: API配置
            translation_config: 翻译配置
            blacklist_config: 黑名单配置
        """
        self.api_config = api_config
        self.translation_config = translation_config
        self.blacklist_config = blacklist_config
        
        # 初始化OpenAI客户端
        self._client = AsyncOpenAI(
            api_key=api_config.key,
            base_url=api_config.endpoint,
            timeout=api_config.timeout,
        )
        
        # 初始化重试计数器
        self._retry_counts: Dict[str, int] = {}

    async def translate(self, text: str, prompt: str) -> TranslationResponse:
        """翻译文本
        
        Args:
            text: 要翻译的文本
            prompt: 翻译提示词
            
        Returns:
            TranslationResponse: 翻译响应
            
        Raises:
            TranslationError: 翻译错误
            APIError: API调用错误
        """
        # 保护黑名单词汇
        protected_text = self._protect_blacklist_words(text)
        
        # 创建翻译请求
        request = TranslationRequest(
            text=protected_text,
            prompt=prompt,
            model=self.api_config.model,
            max_tokens=self.api_config.max_tokens,
            temperature=self.api_config.temperature,
        )
        
        start_time = time.time()
        try:
            # 调用API
            response = await self._call_api(request)
            
            # 恢复黑名单词汇
            translated_text = self._restore_blacklist_words(response.translated_text)
            
            # 计算耗时
            time_taken = time.time() - start_time
            
            return TranslationResponse(
                translated_text=translated_text,
                tokens_used=response.tokens_used,
                model_used=response.model_used,
                time_taken=time_taken,
            )
            
        except Exception as e:
            log.error(f"Translation failed: {str(e)}")
            raise TranslationError("Translation failed", details=str(e))

    async def translate_batch(
        self,
        texts: List[str],
        prompt: str,
        max_concurrent: Optional[int] = None,
    ) -> List[TranslationResponse]:
        """批量翻译文本
        
        Args:
            texts: 要翻译的文本列表
            prompt: 翻译提示词
            max_concurrent: 最大并发数，默认使用配置值
            
        Returns:
            List[TranslationResponse]: 翻译响应列表
        """
        max_concurrent = max_concurrent or self.translation_config.max_concurrent
        
        # 创建任务列表
        tasks = [self.translate(text, prompt) for text in texts]
        
        # 使用信号量限制并发
        semaphore = asyncio.Semaphore(max_concurrent)
        async def bounded_translate(task):
            async with semaphore:
                return await task
        
        # 并发执行翻译
        return await asyncio.gather(
            *(bounded_translate(task) for task in tasks),
            return_exceptions=True
        )

    async def _call_api(self, request: TranslationRequest) -> TranslationResponse:
        """调用OpenAI API
        
        Args:
            request: 翻译请求
            
        Returns:
            TranslationResponse: 翻译响应
            
        Raises:
            APIError: API调用错误
            AuthenticationError: 认证错误
            RateLimitError: 速率限制错误
            NetworkError: 网络错误
            TimeoutError: 超时错误
        """
        try:
            # 构建消息列表
            messages = [
                {"role": "system", "content": request.prompt},
                {"role": "user", "content": request.text},
            ]
            
            # 调用API
            response = await self._client.chat.completions.create(
                model=request.model,
                messages=messages,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
            )
            
            # 提取翻译结果
            translated_text = response.choices[0].message.content
            tokens_used = response.usage.total_tokens
            model_used = response.model
            
            return TranslationResponse(
                translated_text=translated_text,
                tokens_used=tokens_used,
                model_used=model_used,
                time_taken=0,  # 会在上层函数中计算
            )
            
        except openai.AuthenticationError as e:
            raise AuthenticationError("API authentication failed", details=str(e))
        except openai.RateLimitError as e:
            raise RateLimitError("API rate limit exceeded", details=str(e))
        except openai.APITimeoutError as e:
            raise TimeoutError("API request timed out", timeout=self.api_config.timeout)
        except openai.APIConnectionError as e:
            raise NetworkError("API connection failed", details=str(e))
        except openai.APIError as e:
            raise APIError("API call failed", status_code=e.status_code, response=str(e))
        except Exception as e:
            raise APIError("Unexpected error during API call", details=str(e))

    def _protect_blacklist_words(self, text: str) -> str:
        """保护黑名单词汇
        
        Args:
            text: 原始文本
            
        Returns:
            str: 处理后的文本
        """
        result = text
        for word in self.blacklist_config.words:
            if not self.blacklist_config.case_sensitive:
                # 不区分大小写，使用特殊标记保护
                result = result.replace(word, f"__PROTECTED_{word}__")
            else:
                # 区分大小写，保持原有大小写
                result = result.replace(word, f"__PROTECTED_{word}__")
        return result

    def _restore_blacklist_words(self, text: str) -> str:
        """恢复黑名单词汇
        
        Args:
            text: 包含保护标记的文本
            
        Returns:
            str: 恢复后的文本
        """
        result = text
        for word in self.blacklist_config.words:
            result = result.replace(f"__PROTECTED_{word}__", word)
        return result

    async def close(self) -> None:
        """关闭翻译器，清理资源"""
        await self._client.close() 
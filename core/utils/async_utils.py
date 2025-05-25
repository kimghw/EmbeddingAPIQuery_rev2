"""
비동기/동기 처리 유틸리티
"""
import asyncio
import functools
from typing import Any, Awaitable, Callable, TypeVar, Union
from concurrent.futures import ThreadPoolExecutor
import logging

logger = logging.getLogger(__name__)

T = TypeVar('T')

class AsyncSyncBridge:
    """비동기와 동기 코드 간의 브리지 클래스"""
    
    def __init__(self, max_workers: int = 4):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def run_sync_in_thread(self, func: Callable[..., T], *args, **kwargs) -> T:
        """동기 함수를 비동기 컨텍스트에서 실행"""
        try:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                self.executor, 
                functools.partial(func, *args, **kwargs)
            )
        except Exception as e:
            logger.error(f"Error running sync function in thread: {e}")
            raise
    
    def run_async_in_sync(self, coro: Awaitable[T]) -> T:
        """비동기 함수를 동기 컨텍스트에서 실행"""
        try:
            # 이미 실행 중인 이벤트 루프가 있는지 확인
            try:
                loop = asyncio.get_running_loop()
                # 이미 실행 중인 루프가 있으면 새 스레드에서 실행
                import threading
                result = None
                exception = None
                
                def run_in_thread():
                    nonlocal result, exception
                    try:
                        new_loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(new_loop)
                        result = new_loop.run_until_complete(coro)
                        new_loop.close()
                    except Exception as e:
                        exception = e
                
                thread = threading.Thread(target=run_in_thread)
                thread.start()
                thread.join()
                
                if exception:
                    raise exception
                return result
                
            except RuntimeError:
                # 실행 중인 루프가 없으면 직접 실행
                return asyncio.run(coro)
                
        except Exception as e:
            logger.error(f"Error running async function in sync: {e}")
            raise
    
    def __del__(self):
        """리소스 정리"""
        if hasattr(self, 'executor'):
            self.executor.shutdown(wait=True)

# 전역 브리지 인스턴스
_bridge = AsyncSyncBridge()

def sync_to_async(func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    """동기 함수를 비동기 함수로 변환하는 데코레이터"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs) -> T:
        return await _bridge.run_sync_in_thread(func, *args, **kwargs)
    return wrapper

def async_to_sync(func: Callable[..., Awaitable[T]]) -> Callable[..., T]:
    """비동기 함수를 동기 함수로 변환하는 데코레이터"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> T:
        coro = func(*args, **kwargs)
        return _bridge.run_async_in_sync(coro)
    return wrapper

class AsyncContextManager:
    """비동기 컨텍스트 매니저 유틸리티"""
    
    def __init__(self, async_context_manager):
        self.async_context_manager = async_context_manager
        self.resource = None
    
    async def __aenter__(self):
        self.resource = await self.async_context_manager.__aenter__()
        return self.resource
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.async_context_manager.__aexit__(exc_type, exc_val, exc_tb)
    
    def __enter__(self):
        """동기 컨텍스트에서 사용할 수 있도록 변환"""
        return _bridge.run_async_in_sync(self.__aenter__())
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """동기 컨텍스트에서 사용할 수 있도록 변환"""
        return _bridge.run_async_in_sync(self.__aexit__(exc_type, exc_val, exc_tb))

def ensure_async(func_or_coro: Union[Callable[..., T], Awaitable[T]]) -> Awaitable[T]:
    """함수나 코루틴을 비동기로 보장"""
    if asyncio.iscoroutine(func_or_coro):
        return func_or_coro
    elif asyncio.iscoroutinefunction(func_or_coro):
        return func_or_coro()
    else:
        # 동기 함수인 경우 비동기로 변환
        return _bridge.run_sync_in_thread(func_or_coro)

async def gather_with_concurrency(limit: int, *awaitables: Awaitable[T]) -> list[T]:
    """동시 실행 수를 제한하여 비동기 작업들을 실행"""
    semaphore = asyncio.Semaphore(limit)
    
    async def limited_task(awaitable: Awaitable[T]) -> T:
        async with semaphore:
            return await awaitable
    
    return await asyncio.gather(*[limited_task(aw) for aw in awaitables])

class RetryAsyncDecorator:
    """비동기 함수용 재시도 데코레이터"""
    
    def __init__(self, max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
        self.max_retries = max_retries
        self.delay = delay
        self.backoff = backoff
    
    def __call__(self, func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_exception = None
            current_delay = self.delay
            
            for attempt in range(self.max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < self.max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1} failed for {func.__name__}: {e}. "
                            f"Retrying in {current_delay} seconds..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= self.backoff
                    else:
                        logger.error(
                            f"All {self.max_retries + 1} attempts failed for {func.__name__}: {e}"
                        )
            
            raise last_exception
        
        return wrapper

# 편의 함수들
def retry_async(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """비동기 함수용 재시도 데코레이터"""
    return RetryAsyncDecorator(max_retries, delay, backoff)

async def timeout_after(seconds: float, coro: Awaitable[T]) -> T:
    """지정된 시간 후 타임아웃하는 비동기 함수"""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        logger.error(f"Operation timed out after {seconds} seconds")
        raise

def is_async_context() -> bool:
    """현재 비동기 컨텍스트에서 실행 중인지 확인"""
    try:
        asyncio.get_running_loop()
        return True
    except RuntimeError:
        return False

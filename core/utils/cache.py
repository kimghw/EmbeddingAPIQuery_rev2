"""
캐싱 시스템 구현
"""
import asyncio
import time
import json
import hashlib
from typing import Any, Optional, Dict, Callable, TypeVar, Union
from datetime import datetime, timedelta
from enum import Enum
import functools
import weakref

from .logging import create_logger, LogCategory

logger = create_logger("cache", LogCategory.PERFORMANCE)

T = TypeVar('T')


class CacheStrategy(str, Enum):
    """캐시 전략"""
    LRU = "LRU"          # Least Recently Used
    LFU = "LFU"          # Least Frequently Used
    FIFO = "FIFO"        # First In First Out
    TTL = "TTL"          # Time To Live


class CacheEntry:
    """캐시 엔트리"""
    
    def __init__(self, key: str, value: Any, ttl: Optional[int] = None):
        self.key = key
        self.value = value
        self.created_at = datetime.now()
        self.accessed_at = datetime.now()
        self.access_count = 1
        self.ttl = ttl
        self.expires_at = datetime.now() + timedelta(seconds=ttl) if ttl else None
    
    def is_expired(self) -> bool:
        """만료 여부 확인"""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def touch(self):
        """액세스 시간 및 카운트 업데이트"""
        self.accessed_at = datetime.now()
        self.access_count += 1
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "key": self.key,
            "created_at": self.created_at.isoformat(),
            "accessed_at": self.accessed_at.isoformat(),
            "access_count": self.access_count,
            "ttl": self.ttl,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_expired": self.is_expired()
        }


class InMemoryCache:
    """인메모리 캐시"""
    
    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Optional[int] = 300,
        strategy: CacheStrategy = CacheStrategy.LRU
    ):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.strategy = strategy
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        
        # 통계
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        
        logger.info(
            f"Cache initialized",
            max_size=max_size,
            default_ttl=default_ttl,
            strategy=strategy.value
        )
    
    async def get(self, key: str) -> Optional[Any]:
        """캐시에서 값 가져오기"""
        async with self._lock:
            if key not in self._cache:
                self.misses += 1
                logger.debug(f"Cache miss: {key}")
                return None
            
            entry = self._cache[key]
            
            # 만료 확인
            if entry.is_expired():
                del self._cache[key]
                self.misses += 1
                logger.debug(f"Cache expired: {key}")
                return None
            
            # 액세스 정보 업데이트
            entry.touch()
            self.hits += 1
            logger.debug(f"Cache hit: {key}")
            return entry.value
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        ttl: Optional[int] = None
    ):
        """캐시에 값 저장"""
        async with self._lock:
            # TTL 설정
            effective_ttl = ttl if ttl is not None else self.default_ttl
            
            # 기존 엔트리 업데이트 또는 새 엔트리 생성
            if key in self._cache:
                self._cache[key] = CacheEntry(key, value, effective_ttl)
            else:
                # 캐시 크기 확인 및 정리
                if len(self._cache) >= self.max_size:
                    await self._evict()
                
                self._cache[key] = CacheEntry(key, value, effective_ttl)
            
            logger.debug(
                f"Cache set: {key}",
                ttl=effective_ttl,
                cache_size=len(self._cache)
            )
    
    async def delete(self, key: str) -> bool:
        """캐시에서 키 삭제"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                logger.debug(f"Cache deleted: {key}")
                return True
            return False
    
    async def clear(self):
        """캐시 전체 삭제"""
        async with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")
    
    async def _evict(self):
        """캐시 정리 (전략에 따라)"""
        if not self._cache:
            return
        
        if self.strategy == CacheStrategy.LRU:
            # 가장 오래 전에 액세스된 항목 제거
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].accessed_at
            )
        elif self.strategy == CacheStrategy.LFU:
            # 가장 적게 액세스된 항목 제거
            least_used_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].access_count
            )
            oldest_key = least_used_key
        elif self.strategy == CacheStrategy.FIFO:
            # 가장 먼저 생성된 항목 제거
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].created_at
            )
        else:  # TTL
            # 만료된 항목들 먼저 제거
            expired_keys = [
                k for k, v in self._cache.items() 
                if v.is_expired()
            ]
            if expired_keys:
                oldest_key = expired_keys[0]
            else:
                oldest_key = min(
                    self._cache.keys(),
                    key=lambda k: self._cache[k].created_at
                )
        
        del self._cache[oldest_key]
        self.evictions += 1
        logger.debug(f"Cache evicted: {oldest_key}")
    
    async def cleanup_expired(self):
        """만료된 엔트리들 정리"""
        async with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
    
    def get_stats(self) -> Dict[str, Any]:
        """캐시 통계 반환"""
        total_requests = self.hits + self.misses
        hit_rate = (self.hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "hit_rate": round(hit_rate, 2),
            "strategy": self.strategy.value,
            "default_ttl": self.default_ttl
        }
    
    def get_entries_info(self) -> Dict[str, Dict[str, Any]]:
        """모든 엔트리 정보 반환"""
        return {key: entry.to_dict() for key, entry in self._cache.items()}


class DistributedCache:
    """분산 캐시 (Redis 등과 연동 가능)"""
    
    def __init__(self, redis_client=None, key_prefix: str = "graphapi:"):
        self.redis_client = redis_client
        self.key_prefix = key_prefix
        self.fallback_cache = InMemoryCache()
    
    def _make_key(self, key: str) -> str:
        """키에 프리픽스 추가"""
        return f"{self.key_prefix}{key}"
    
    async def get(self, key: str) -> Optional[Any]:
        """분산 캐시에서 값 가져오기"""
        full_key = self._make_key(key)
        
        if self.redis_client:
            try:
                value = await self.redis_client.get(full_key)
                if value:
                    return json.loads(value)
            except Exception as e:
                logger.warning(f"Redis get failed: {e}, falling back to memory cache")
        
        # Redis 실패 시 메모리 캐시 사용
        return await self.fallback_cache.get(key)
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """분산 캐시에 값 저장"""
        full_key = self._make_key(key)
        serialized_value = json.dumps(value, default=str)
        
        if self.redis_client:
            try:
                if ttl:
                    await self.redis_client.setex(full_key, ttl, serialized_value)
                else:
                    await self.redis_client.set(full_key, serialized_value)
                
                # 메모리 캐시에도 저장 (빠른 액세스용)
                await self.fallback_cache.set(key, value, ttl)
                return
            except Exception as e:
                logger.warning(f"Redis set failed: {e}, falling back to memory cache")
        
        # Redis 실패 시 메모리 캐시만 사용
        await self.fallback_cache.set(key, value, ttl)
    
    async def delete(self, key: str) -> bool:
        """분산 캐시에서 키 삭제"""
        full_key = self._make_key(key)
        
        redis_deleted = False
        if self.redis_client:
            try:
                redis_deleted = await self.redis_client.delete(full_key) > 0
            except Exception as e:
                logger.warning(f"Redis delete failed: {e}")
        
        memory_deleted = await self.fallback_cache.delete(key)
        return redis_deleted or memory_deleted


class CacheManager:
    """캐시 매니저"""
    
    def __init__(self):
        self.caches: Dict[str, Union[InMemoryCache, DistributedCache]] = {}
        self._cleanup_task: Optional[asyncio.Task] = None
    
    def create_cache(
        self,
        name: str,
        cache_type: str = "memory",
        **kwargs
    ) -> Union[InMemoryCache, DistributedCache]:
        """캐시 생성"""
        if cache_type == "memory":
            cache = InMemoryCache(**kwargs)
        elif cache_type == "distributed":
            cache = DistributedCache(**kwargs)
        else:
            raise ValueError(f"Unknown cache type: {cache_type}")
        
        self.caches[name] = cache
        logger.info(f"Cache created: {name} ({cache_type})")
        return cache
    
    def get_cache(self, name: str) -> Optional[Union[InMemoryCache, DistributedCache]]:
        """캐시 가져오기"""
        return self.caches.get(name)
    
    def start_cleanup_task(self, interval: int = 300):
        """정리 작업 시작"""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(
                self._periodic_cleanup(interval)
            )
            logger.info(f"Cache cleanup task started (interval: {interval}s)")
    
    def stop_cleanup_task(self):
        """정리 작업 중지"""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            logger.info("Cache cleanup task stopped")
    
    async def _periodic_cleanup(self, interval: int):
        """주기적 정리 작업"""
        while True:
            try:
                await asyncio.sleep(interval)
                
                for name, cache in self.caches.items():
                    if isinstance(cache, InMemoryCache):
                        await cache.cleanup_expired()
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """모든 캐시 통계 반환"""
        stats = {}
        for name, cache in self.caches.items():
            if isinstance(cache, InMemoryCache):
                stats[name] = cache.get_stats()
            else:
                stats[name] = {"type": "distributed", "name": name}
        return stats


# 전역 캐시 매니저
_cache_manager = CacheManager()

def get_cache_manager() -> CacheManager:
    """전역 캐시 매니저 반환"""
    return _cache_manager


# 캐시 데코레이터들
def cache_result(
    cache_name: str = "default",
    ttl: Optional[int] = None,
    key_generator: Optional[Callable] = None
):
    """결과 캐싱 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # 캐시 가져오기
            cache = _cache_manager.get_cache(cache_name)
            if cache is None:
                cache = _cache_manager.create_cache(cache_name)
            
            # 캐시 키 생성
            if key_generator:
                cache_key = key_generator(*args, **kwargs)
            else:
                cache_key = _generate_cache_key(func, args, kwargs)
            
            # 캐시에서 값 확인
            cached_value = await cache.get(cache_key)
            if cached_value is not None:
                logger.debug(f"Cache hit for {func.__name__}: {cache_key}")
                return cached_value
            
            # 함수 실행
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 결과 캐싱
            await cache.set(cache_key, result, ttl)
            logger.debug(f"Cached result for {func.__name__}: {cache_key}")
            
            return result
        
        return wrapper
    
    return decorator


def cache_invalidate(cache_name: str = "default", key_pattern: Optional[str] = None):
    """캐시 무효화 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # 함수 실행
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            # 캐시 무효화
            cache = _cache_manager.get_cache(cache_name)
            if cache:
                if key_pattern:
                    # 패턴 매칭 키 삭제 (간단한 구현)
                    if isinstance(cache, InMemoryCache):
                        keys_to_delete = [
                            key for key in cache._cache.keys()
                            if key_pattern in key
                        ]
                        for key in keys_to_delete:
                            await cache.delete(key)
                else:
                    # 전체 캐시 클리어
                    await cache.clear()
                
                logger.debug(f"Cache invalidated for {func.__name__}")
            
            return result
        
        return wrapper
    
    return decorator


def _generate_cache_key(func: Callable, args: tuple, kwargs: dict) -> str:
    """캐시 키 생성"""
    # 함수 이름과 인자들을 조합하여 해시 생성
    key_parts = [func.__name__]
    
    # 위치 인자들
    for arg in args:
        if hasattr(arg, '__dict__'):
            # 객체인 경우 클래스명과 주요 속성들 사용
            key_parts.append(f"{arg.__class__.__name__}:{id(arg)}")
        else:
            key_parts.append(str(arg))
    
    # 키워드 인자들
    for key, value in sorted(kwargs.items()):
        key_parts.append(f"{key}:{value}")
    
    # 해시 생성
    key_string = ":".join(key_parts)
    return hashlib.md5(key_string.encode()).hexdigest()


# 편의 함수들
async def get_cached(cache_name: str, key: str) -> Optional[Any]:
    """캐시에서 값 가져오기"""
    cache = _cache_manager.get_cache(cache_name)
    if cache:
        return await cache.get(key)
    return None


async def set_cached(
    cache_name: str, 
    key: str, 
    value: Any, 
    ttl: Optional[int] = None
):
    """캐시에 값 저장"""
    cache = _cache_manager.get_cache(cache_name)
    if cache is None:
        cache = _cache_manager.create_cache(cache_name)
    
    await cache.set(key, value, ttl)


async def delete_cached(cache_name: str, key: str) -> bool:
    """캐시에서 키 삭제"""
    cache = _cache_manager.get_cache(cache_name)
    if cache:
        return await cache.delete(key)
    return False


async def clear_cache(cache_name: str):
    """캐시 전체 삭제"""
    cache = _cache_manager.get_cache(cache_name)
    if cache:
        await cache.clear()


# 특화된 캐시들
class GraphAPICache:
    """Graph API 전용 캐시"""
    
    def __init__(self):
        self.cache = _cache_manager.create_cache(
            "graph_api",
            max_size=500,
            default_ttl=3600  # 1시간
        )
    
    async def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """사용자 프로필 캐시에서 가져오기"""
        return await self.cache.get(f"user_profile:{user_id}")
    
    async def set_user_profile(self, user_id: str, profile: Dict[str, Any]):
        """사용자 프로필 캐시에 저장"""
        await self.cache.set(f"user_profile:{user_id}", profile, ttl=3600)
    
    async def get_access_token(self, user_id: str) -> Optional[str]:
        """액세스 토큰 캐시에서 가져오기"""
        return await self.cache.get(f"access_token:{user_id}")
    
    async def set_access_token(self, user_id: str, token: str, expires_in: int):
        """액세스 토큰 캐시에 저장"""
        # 만료 시간보다 5분 일찍 캐시 만료
        ttl = max(expires_in - 300, 60)
        await self.cache.set(f"access_token:{user_id}", token, ttl=ttl)


# 전역 Graph API 캐시
_graph_api_cache = GraphAPICache()

def get_graph_api_cache() -> GraphAPICache:
    """Graph API 캐시 반환"""
    return _graph_api_cache

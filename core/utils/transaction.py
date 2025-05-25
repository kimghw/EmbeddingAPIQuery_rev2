"""
데이터베이스 트랜잭션 관리 유틸리티
"""
import asyncio
from contextlib import asynccontextmanager, contextmanager
from typing import AsyncGenerator, Generator, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import logging

from .logging import create_logger, LogCategory
from ..exceptions import DatabaseError

logger = create_logger("transaction", LogCategory.DATABASE)


class TransactionManager:
    """비동기 트랜잭션 매니저"""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self._transaction_depth = 0
        self._savepoints: Dict[str, Any] = {}
    
    @asynccontextmanager
    async def transaction(self, rollback_on_exception: bool = True) -> AsyncGenerator[AsyncSession, None]:
        """트랜잭션 컨텍스트 매니저"""
        self._transaction_depth += 1
        transaction_id = f"tx_{self._transaction_depth}"
        
        logger.info(
            f"Starting transaction: {transaction_id}",
            transaction_id=transaction_id,
            depth=self._transaction_depth
        )
        
        try:
            if self._transaction_depth == 1:
                # 최상위 트랜잭션
                async with self.session.begin():
                    yield self.session
                    logger.info(f"Transaction committed: {transaction_id}")
            else:
                # 중첩 트랜잭션 - 세이브포인트 사용
                savepoint_name = f"sp_{self._transaction_depth}"
                savepoint = await self.session.begin_nested()
                self._savepoints[savepoint_name] = savepoint
                
                try:
                    yield self.session
                    await savepoint.commit()
                    logger.info(f"Savepoint committed: {savepoint_name}")
                except Exception:
                    await savepoint.rollback()
                    logger.warning(f"Savepoint rolled back: {savepoint_name}")
                    raise
                finally:
                    self._savepoints.pop(savepoint_name, None)
                    
        except Exception as e:
            if rollback_on_exception:
                logger.error(
                    f"Transaction failed: {transaction_id}",
                    error=str(e),
                    error_type=type(e).__name__
                )
            raise DatabaseError(
                f"Transaction failed: {str(e)}",
                operation=f"transaction_{transaction_id}"
            ) from e
        finally:
            self._transaction_depth -= 1
    
    @asynccontextmanager
    async def savepoint(self, name: Optional[str] = None) -> AsyncGenerator[AsyncSession, None]:
        """세이브포인트 컨텍스트 매니저"""
        savepoint_name = name or f"sp_{len(self._savepoints) + 1}"
        
        logger.debug(f"Creating savepoint: {savepoint_name}")
        
        try:
            savepoint = await self.session.begin_nested()
            self._savepoints[savepoint_name] = savepoint
            
            yield self.session
            
            await savepoint.commit()
            logger.debug(f"Savepoint committed: {savepoint_name}")
            
        except Exception as e:
            await savepoint.rollback()
            logger.warning(
                f"Savepoint rolled back: {savepoint_name}",
                error=str(e)
            )
            raise
        finally:
            self._savepoints.pop(savepoint_name, None)
    
    async def rollback_to_savepoint(self, name: str):
        """특정 세이브포인트로 롤백"""
        if name in self._savepoints:
            savepoint = self._savepoints[name]
            await savepoint.rollback()
            logger.info(f"Rolled back to savepoint: {name}")
        else:
            raise DatabaseError(f"Savepoint not found: {name}")


class SyncTransactionManager:
    """동기 트랜잭션 매니저"""
    
    def __init__(self, session: Session):
        self.session = session
        self._transaction_depth = 0
        self._savepoints: Dict[str, Any] = {}
    
    @contextmanager
    def transaction(self, rollback_on_exception: bool = True) -> Generator[Session, None, None]:
        """트랜잭션 컨텍스트 매니저"""
        self._transaction_depth += 1
        transaction_id = f"tx_{self._transaction_depth}"
        
        logger.info(
            f"Starting sync transaction: {transaction_id}",
            transaction_id=transaction_id,
            depth=self._transaction_depth
        )
        
        try:
            if self._transaction_depth == 1:
                # 최상위 트랜잭션
                with self.session.begin():
                    yield self.session
                    logger.info(f"Sync transaction committed: {transaction_id}")
            else:
                # 중첩 트랜잭션 - 세이브포인트 사용
                savepoint_name = f"sp_{self._transaction_depth}"
                savepoint = self.session.begin_nested()
                self._savepoints[savepoint_name] = savepoint
                
                try:
                    yield self.session
                    savepoint.commit()
                    logger.info(f"Sync savepoint committed: {savepoint_name}")
                except Exception:
                    savepoint.rollback()
                    logger.warning(f"Sync savepoint rolled back: {savepoint_name}")
                    raise
                finally:
                    self._savepoints.pop(savepoint_name, None)
                    
        except Exception as e:
            if rollback_on_exception:
                logger.error(
                    f"Sync transaction failed: {transaction_id}",
                    error=str(e),
                    error_type=type(e).__name__
                )
            raise DatabaseError(
                f"Sync transaction failed: {str(e)}",
                operation=f"sync_transaction_{transaction_id}"
            ) from e
        finally:
            self._transaction_depth -= 1


class BatchTransactionManager:
    """배치 작업용 트랜잭션 매니저"""
    
    def __init__(self, session: AsyncSession, batch_size: int = 100):
        self.session = session
        self.batch_size = batch_size
        self.current_batch = 0
        self.total_processed = 0
    
    @asynccontextmanager
    async def batch_transaction(self) -> AsyncGenerator[AsyncSession, None]:
        """배치 트랜잭션 컨텍스트 매니저"""
        logger.info(
            f"Starting batch transaction",
            batch_size=self.batch_size,
            current_batch=self.current_batch
        )
        
        try:
            async with self.session.begin():
                yield self.session
                
                self.current_batch += 1
                logger.info(
                    f"Batch transaction completed",
                    batch_number=self.current_batch,
                    total_processed=self.total_processed
                )
                
        except Exception as e:
            logger.error(
                f"Batch transaction failed",
                batch_number=self.current_batch,
                error=str(e)
            )
            raise DatabaseError(
                f"Batch transaction failed: {str(e)}",
                operation=f"batch_transaction_{self.current_batch}"
            ) from e
    
    async def process_in_batches(self, items, processor_func):
        """아이템들을 배치로 나누어 처리"""
        total_items = len(items)
        logger.info(f"Processing {total_items} items in batches of {self.batch_size}")
        
        for i in range(0, total_items, self.batch_size):
            batch = items[i:i + self.batch_size]
            
            async with self.batch_transaction():
                for item in batch:
                    await processor_func(item, self.session)
                    self.total_processed += 1
                
                # 중간 커밋
                await self.session.commit()
                
                logger.debug(
                    f"Processed batch {self.current_batch}",
                    items_in_batch=len(batch),
                    total_processed=self.total_processed,
                    remaining=total_items - self.total_processed
                )


class TransactionDecorator:
    """트랜잭션 데코레이터"""
    
    def __init__(self, rollback_on_exception: bool = True):
        self.rollback_on_exception = rollback_on_exception
    
    def __call__(self, func):
        if asyncio.iscoroutinefunction(func):
            async def async_wrapper(*args, **kwargs):
                # 첫 번째 인자에서 session을 찾기
                session = None
                for arg in args:
                    if isinstance(arg, AsyncSession):
                        session = arg
                        break
                
                if not session:
                    # kwargs에서 session 찾기
                    session = kwargs.get('session')
                
                if not session:
                    raise ValueError("Session not found in function arguments")
                
                tx_manager = TransactionManager(session)
                async with tx_manager.transaction(self.rollback_on_exception):
                    return await func(*args, **kwargs)
            
            return async_wrapper
        else:
            def sync_wrapper(*args, **kwargs):
                # 첫 번째 인자에서 session을 찾기
                session = None
                for arg in args:
                    if isinstance(arg, Session):
                        session = arg
                        break
                
                if not session:
                    # kwargs에서 session 찾기
                    session = kwargs.get('session')
                
                if not session:
                    raise ValueError("Session not found in function arguments")
                
                tx_manager = SyncTransactionManager(session)
                with tx_manager.transaction(self.rollback_on_exception):
                    return func(*args, **kwargs)
            
            return sync_wrapper


# 편의 데코레이터들
def transactional(rollback_on_exception: bool = True):
    """트랜잭션 데코레이터"""
    return TransactionDecorator(rollback_on_exception)


def requires_transaction(func):
    """트랜잭션이 필요한 함수임을 명시하는 데코레이터"""
    func._requires_transaction = True
    return func


# 유틸리티 함수들
async def execute_in_transaction(session: AsyncSession, operations: list):
    """여러 작업을 하나의 트랜잭션으로 실행"""
    tx_manager = TransactionManager(session)
    
    async with tx_manager.transaction():
        results = []
        for operation in operations:
            if asyncio.iscoroutinefunction(operation):
                result = await operation(session)
            else:
                result = operation(session)
            results.append(result)
        
        return results


def execute_in_sync_transaction(session: Session, operations: list):
    """여러 동기 작업을 하나의 트랜잭션으로 실행"""
    tx_manager = SyncTransactionManager(session)
    
    with tx_manager.transaction():
        results = []
        for operation in operations:
            result = operation(session)
            results.append(result)
        
        return results


async def bulk_insert_with_transaction(
    session: AsyncSession,
    model_class,
    data_list: list,
    batch_size: int = 100
):
    """대량 데이터를 트랜잭션으로 배치 삽입"""
    batch_manager = BatchTransactionManager(session, batch_size)
    
    async def insert_item(item_data, session):
        item = model_class(**item_data)
        session.add(item)
    
    await batch_manager.process_in_batches(data_list, insert_item)
    
    logger.info(
        f"Bulk insert completed",
        model=model_class.__name__,
        total_items=len(data_list),
        batches=batch_manager.current_batch
    )


class TransactionContext:
    """트랜잭션 컨텍스트 정보"""
    
    def __init__(self):
        self.transaction_id: Optional[str] = None
        self.start_time: Optional[float] = None
        self.operations: list = []
        self.metadata: Dict[str, Any] = {}
    
    def add_operation(self, operation: str, **kwargs):
        """작업 기록 추가"""
        self.operations.append({
            "operation": operation,
            "timestamp": asyncio.get_event_loop().time(),
            "metadata": kwargs
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """트랜잭션 요약 정보 반환"""
        return {
            "transaction_id": self.transaction_id,
            "duration": asyncio.get_event_loop().time() - self.start_time if self.start_time else None,
            "operations_count": len(self.operations),
            "operations": self.operations,
            "metadata": self.metadata
        }

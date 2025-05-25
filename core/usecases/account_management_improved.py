"""
개선된 계정 관리 유즈케이스 - 비동기/동기 처리 개선 및 에러 표준화 적용
"""
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime
import logging

from ..domain.user import User
from ..domain.account import Account
from ..ports.repository import UserRepository, AccountRepository
from ..ports.graph_api import GraphAPIPort
from ..ports.config import ConfigPort
from ..exceptions import (
    ResourceNotFoundError, 
    ValidationError, 
    DuplicateResourceError,
    AuthenticationError,
    BusinessLogicError
)
from ..utils.error_handler import (
    handle_errors, 
    ErrorContext, 
    OperationTimer,
    create_error_response,
    create_success_response
)
from ..utils.async_utils import (
    async_to_sync, 
    sync_to_async, 
    retry_async,
    timeout_after,
    gather_with_concurrency
)

logger = logging.getLogger(__name__)

# Request/Response Models
class CreateAccountRequest(BaseModel):
    """Request model for creating an account."""
    user_id: str
    email: str = Field(..., description="Email address for the account")
    display_name: Optional[str] = Field(None, description="Display name for the account")


class CreateAccountResponse(BaseModel):
    """Response model for account creation."""
    account_id: str
    email: str
    display_name: Optional[str]
    is_active: bool
    created_at: datetime
    message: str = "Account created successfully"


class AccountDetailResponse(BaseModel):
    """Response model for account details."""
    account_id: str
    user_id: str
    email: str
    display_name: Optional[str]
    is_active: bool
    token_expires_at: Optional[datetime]
    last_sync_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class AccountListResponse(BaseModel):
    """Response model for account list."""
    accounts: List[AccountDetailResponse]
    total_count: int
    active_count: int


class UpdateAccountRequest(BaseModel):
    """Request model for updating an account."""
    display_name: Optional[str] = None
    is_active: Optional[bool] = None


class UpdateAccountResponse(BaseModel):
    """Response model for account update."""
    account_id: str
    message: str = "Account updated successfully"


class AuthorizeAccountRequest(BaseModel):
    """Request model for account authorization."""
    account_id: str
    authorization_code: str
    state: Optional[str] = None


class AuthorizeAccountResponse(BaseModel):
    """Response model for account authorization."""
    account_id: str
    email: str
    token_expires_at: datetime
    message: str = "Account authorized successfully"


class BatchAccountOperationRequest(BaseModel):
    """Request model for batch account operations."""
    account_ids: List[str]
    operation: str  # 'activate', 'deactivate', 'refresh_tokens'
    concurrency_limit: int = Field(default=5, ge=1, le=20)


class BatchAccountOperationResponse(BaseModel):
    """Response model for batch account operations."""
    total_processed: int
    successful: int
    failed: int
    results: List[dict]


# Use Case Implementation
class ImprovedAccountManagementUseCase:
    """개선된 계정 관리 유즈케이스"""
    
    def __init__(
        self,
        user_repository: UserRepository,
        account_repository: AccountRepository,
        graph_api: GraphAPIPort,
        config: ConfigPort
    ):
        self.user_repository = user_repository
        self.account_repository = account_repository
        self.graph_api = graph_api
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    def _create_error_context(self, operation: str, **kwargs) -> ErrorContext:
        """에러 컨텍스트 생성"""
        return ErrorContext(
            operation=operation,
            user_id=kwargs.get('user_id'),
            account_id=kwargs.get('account_id'),
            additional_context=kwargs
        )
    
    @handle_errors("create_account")
    async def create_account(self, request: CreateAccountRequest) -> CreateAccountResponse:
        """
        계정 생성 - 개선된 에러 처리 및 로깅
        """
        async with OperationTimer("create_account"):
            # 사용자 존재 확인
            user = await self.user_repository.find_by_id(request.user_id)
            if not user:
                raise ResourceNotFoundError("User", request.user_id)
            
            # 중복 계정 확인
            existing_account = await self.account_repository.find_by_email(request.email)
            if existing_account:
                raise DuplicateResourceError("Account", request.email)
            
            # 계정 생성
            account = Account(
                user_id=request.user_id,
                email_address=request.email,
                display_name=request.display_name
            )
            
            # 저장
            saved_account = await self.account_repository.save(account)
            
            self.logger.info(
                f"Account created successfully: {saved_account.id}",
                extra={
                    "account_id": saved_account.id,
                    "user_id": request.user_id,
                    "email": request.email
                }
            )
            
            return CreateAccountResponse(
                account_id=saved_account.id,
                email=saved_account.email_address,
                display_name=saved_account.display_name,
                is_active=saved_account.is_active(),
                created_at=saved_account.created_at
            )
    
    @handle_errors("get_account_by_id")
    async def get_account_by_id(self, account_id: str) -> Optional[AccountDetailResponse]:
        """계정 상세 조회"""
        account = await self.account_repository.find_by_id(account_id)
        if not account:
            return None
        
        return self._convert_to_detail_response(account)
    
    @handle_errors("get_accounts_by_user_id")
    async def get_accounts_by_user_id(self, user_id: str) -> AccountListResponse:
        """사용자별 계정 목록 조회"""
        accounts = await self.account_repository.find_by_user_id(user_id)
        return self._convert_to_list_response(accounts)
    
    @handle_errors("get_all_accounts")
    async def get_all_accounts(self, skip: int = 0, limit: int = 100) -> AccountListResponse:
        """전체 계정 목록 조회 (페이징)"""
        accounts = await self.account_repository.find_all(skip=skip, limit=limit)
        return self._convert_to_list_response(accounts)
    
    @handle_errors("get_active_accounts")
    async def get_active_accounts(self) -> AccountListResponse:
        """활성 계정 목록 조회"""
        accounts = await self.account_repository.find_active_accounts()
        return self._convert_to_list_response(accounts)
    
    @handle_errors("update_account")
    async def update_account(
        self, 
        account_id: str, 
        request: UpdateAccountRequest
    ) -> UpdateAccountResponse:
        """계정 정보 업데이트"""
        async with OperationTimer("update_account"):
            account = await self.account_repository.find_by_id(account_id)
            if not account:
                raise ResourceNotFoundError("Account", account_id)
            
            # 필드 업데이트
            if request.display_name is not None:
                account.display_name = request.display_name
            
            if request.is_active is not None:
                if request.is_active:
                    account.activate()
                else:
                    account.deactivate()
            
            # 저장
            await self.account_repository.update(account)
            
            self.logger.info(
                f"Account updated successfully: {account_id}",
                extra={"account_id": account_id, "updates": request.dict(exclude_unset=True)}
            )
            
            return UpdateAccountResponse(account_id=account_id)
    
    @handle_errors("delete_account")
    async def delete_account(self, account_id: str) -> bool:
        """계정 삭제"""
        async with OperationTimer("delete_account"):
            account = await self.account_repository.find_by_id(account_id)
            if not account:
                raise ResourceNotFoundError("Account", account_id)
            
            result = await self.account_repository.delete(account_id)
            
            if result:
                self.logger.info(f"Account deleted successfully: {account_id}")
            
            return result
    
    @handle_errors("get_authorization_url")
    async def get_authorization_url(self, account_id: str) -> str:
        """OAuth 인증 URL 생성"""
        account = await self.account_repository.find_by_id(account_id)
        if not account:
            raise ResourceNotFoundError("Account", account_id)
        
        state = str(account_id)
        return await self.graph_api.get_authorization_url(state=state)
    
    @handle_errors("authorize_account")
    @retry_async(max_retries=3, delay=1.0)
    async def authorize_account(
        self, 
        request: AuthorizeAccountRequest
    ) -> AuthorizeAccountResponse:
        """계정 OAuth 인증 - 재시도 로직 포함"""
        async with OperationTimer("authorize_account"):
            account = await self.account_repository.find_by_id(request.account_id)
            if not account:
                raise ResourceNotFoundError("Account", request.account_id)
            
            # State 파라미터 검증
            if request.state and request.state != str(request.account_id):
                raise ValidationError("Invalid state parameter")
            
            try:
                # 토큰 교환 (타임아웃 적용)
                token_info = await timeout_after(
                    30.0,  # 30초 타임아웃
                    self.graph_api.exchange_code_for_token(
                        code=request.authorization_code,
                        state=request.state
                    )
                )
                
                # 계정 토큰 정보 업데이트
                await self.account_repository.update_token_info(
                    account_id=request.account_id,
                    token_info=token_info
                )
                
                # 업데이트된 계정 조회
                updated_account = await self.account_repository.find_by_id(request.account_id)
                
                self.logger.info(
                    f"Account authorized successfully: {request.account_id}",
                    extra={"account_id": request.account_id, "email": updated_account.email_address}
                )
                
                return AuthorizeAccountResponse(
                    account_id=request.account_id,
                    email=updated_account.email_address,
                    token_expires_at=updated_account.token_expires_at
                )
                
            except Exception as e:
                raise AuthenticationError(f"Failed to authorize account: {str(e)}")
    
    @handle_errors("refresh_account_token")
    @retry_async(max_retries=2, delay=2.0)
    async def refresh_account_token(self, account_id: str) -> bool:
        """계정 토큰 갱신 - 재시도 로직 포함"""
        async with OperationTimer("refresh_account_token"):
            account = await self.account_repository.find_by_id(account_id)
            if not account:
                raise ResourceNotFoundError("Account", account_id)
            
            if not account.refresh_token:
                raise ValidationError("No refresh token available for account")
            
            try:
                # 토큰 갱신
                token_info = await timeout_after(
                    20.0,  # 20초 타임아웃
                    self.graph_api.refresh_token(account)
                )
                
                # 계정 토큰 정보 업데이트
                await self.account_repository.update_token_info(
                    account_id=account_id,
                    token_info=token_info
                )
                
                self.logger.info(f"Token refreshed successfully: {account_id}")
                return True
                
            except Exception as e:
                raise AuthenticationError(f"Failed to refresh token: {str(e)}")
    
    @handle_errors("batch_account_operation")
    async def batch_account_operation(
        self, 
        request: BatchAccountOperationRequest
    ) -> BatchAccountOperationResponse:
        """배치 계정 작업 - 동시성 제한 적용"""
        async with OperationTimer("batch_account_operation"):
            operation_func = self._get_batch_operation_func(request.operation)
            
            # 동시성 제한을 적용하여 배치 작업 실행
            tasks = [
                operation_func(account_id) 
                for account_id in request.account_ids
            ]
            
            results = await gather_with_concurrency(
                request.concurrency_limit, 
                *tasks
            )
            
            # 결과 집계
            successful = sum(1 for result in results if result.get('success', False))
            failed = len(results) - successful
            
            self.logger.info(
                f"Batch operation completed: {request.operation}",
                extra={
                    "operation": request.operation,
                    "total": len(request.account_ids),
                    "successful": successful,
                    "failed": failed
                }
            )
            
            return BatchAccountOperationResponse(
                total_processed=len(results),
                successful=successful,
                failed=failed,
                results=results
            )
    
    def _get_batch_operation_func(self, operation: str):
        """배치 작업 함수 반환"""
        async def activate_account(account_id: str) -> dict:
            try:
                await self.update_account(
                    account_id, 
                    UpdateAccountRequest(is_active=True)
                )
                return {"account_id": account_id, "success": True}
            except Exception as e:
                return {"account_id": account_id, "success": False, "error": str(e)}
        
        async def deactivate_account(account_id: str) -> dict:
            try:
                await self.update_account(
                    account_id, 
                    UpdateAccountRequest(is_active=False)
                )
                return {"account_id": account_id, "success": True}
            except Exception as e:
                return {"account_id": account_id, "success": False, "error": str(e)}
        
        async def refresh_token(account_id: str) -> dict:
            try:
                await self.refresh_account_token(account_id)
                return {"account_id": account_id, "success": True}
            except Exception as e:
                return {"account_id": account_id, "success": False, "error": str(e)}
        
        operations = {
            'activate': activate_account,
            'deactivate': deactivate_account,
            'refresh_tokens': refresh_token
        }
        
        if operation not in operations:
            raise ValidationError(f"Unsupported batch operation: {operation}")
        
        return operations[operation]
    
    def _convert_to_detail_response(self, account: Account) -> AccountDetailResponse:
        """Account 도메인 객체를 DetailResponse로 변환"""
        return AccountDetailResponse(
            account_id=account.id,
            user_id=account.user_id,
            email=account.email_address,
            display_name=account.display_name,
            is_active=account.is_active(),
            token_expires_at=account.token_expires_at,
            last_sync_at=account.last_sync_at,
            created_at=account.created_at,
            updated_at=account.updated_at
        )
    
    def _convert_to_list_response(self, accounts: List[Account]) -> AccountListResponse:
        """Account 리스트를 ListResponse로 변환"""
        account_details = []
        active_count = 0
        
        for account in accounts:
            if account.is_active():
                active_count += 1
            
            account_details.append(self._convert_to_detail_response(account))
        
        return AccountListResponse(
            accounts=account_details,
            total_count=len(accounts),
            active_count=active_count
        )
    
    # 동기 버전 메서드들 (CLI에서 사용)
    @async_to_sync
    def create_account_sync(self, request: CreateAccountRequest) -> CreateAccountResponse:
        """동기 버전 계정 생성"""
        return self.create_account(request)
    
    @async_to_sync
    def get_account_by_id_sync(self, account_id: str) -> Optional[AccountDetailResponse]:
        """동기 버전 계정 조회"""
        return self.get_account_by_id(account_id)
    
    @async_to_sync
    def get_accounts_by_user_id_sync(self, user_id: str) -> AccountListResponse:
        """동기 버전 사용자 계정 목록 조회"""
        return self.get_accounts_by_user_id(user_id)
    
    @async_to_sync
    def update_account_sync(
        self, 
        account_id: str, 
        request: UpdateAccountRequest
    ) -> UpdateAccountResponse:
        """동기 버전 계정 업데이트"""
        return self.update_account(account_id, request)
    
    @async_to_sync
    def delete_account_sync(self, account_id: str) -> bool:
        """동기 버전 계정 삭제"""
        return self.delete_account(account_id)
    
    @async_to_sync
    def authorize_account_sync(
        self, 
        request: AuthorizeAccountRequest
    ) -> AuthorizeAccountResponse:
        """동기 버전 계정 인증"""
        return self.authorize_account(request)
    
    @async_to_sync
    def refresh_account_token_sync(self, account_id: str) -> bool:
        """동기 버전 토큰 갱신"""
        return self.refresh_account_token(account_id)


# 하위 호환성을 위한 별칭
AccountManagementUseCase = ImprovedAccountManagementUseCase

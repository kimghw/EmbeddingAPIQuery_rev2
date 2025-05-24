"""Account management use cases."""

from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime

from ..domain.user import User
from ..domain.account import Account
from ..ports.repository import UserRepository, AccountRepository
from ..ports.graph_api import GraphAPIPort
from ..ports.config import ConfigPort


# Request/Response Models
class CreateAccountRequest(BaseModel):
    """Request model for creating an account."""
    user_id: UUID
    email: str = Field(..., description="Email address for the account")
    display_name: Optional[str] = Field(None, description="Display name for the account")
    is_active: bool = Field(True, description="Whether the account is active")


class CreateAccountResponse(BaseModel):
    """Response model for account creation."""
    account_id: UUID
    email: str
    display_name: Optional[str]
    is_active: bool
    created_at: datetime
    message: str = "Account created successfully"


class AccountDetailResponse(BaseModel):
    """Response model for account details."""
    account_id: UUID
    user_id: UUID
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
    account_id: UUID
    message: str = "Account updated successfully"


class AuthorizeAccountRequest(BaseModel):
    """Request model for account authorization."""
    account_id: UUID
    authorization_code: str
    state: Optional[str] = None


class AuthorizeAccountResponse(BaseModel):
    """Response model for account authorization."""
    account_id: UUID
    email: str
    token_expires_at: datetime
    message: str = "Account authorized successfully"


# Use Case Implementation
class AccountManagementUseCase:
    """Use case for managing user accounts."""
    
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
    
    async def create_account(self, request: CreateAccountRequest) -> CreateAccountResponse:
        """
        Create a new account for a user.
        
        Args:
            request: Account creation request
            
        Returns:
            Account creation response
            
        Raises:
            ValueError: If user doesn't exist or account already exists
        """
        # Validate user exists
        user = await self.user_repository.find_by_id(request.user_id)
        if not user:
            raise ValueError(f"User with ID {request.user_id} not found")
        
        # Check if account already exists
        existing_account = await self.account_repository.find_by_email(request.email)
        if existing_account:
            raise ValueError(f"Account with email {request.email} already exists")
        
        # Create new account
        account = Account(
            user_id=request.user_id,
            email=request.email,
            display_name=request.display_name,
            is_active=request.is_active
        )
        
        # Save account
        saved_account = await self.account_repository.save(account)
        
        return CreateAccountResponse(
            account_id=saved_account.id,
            email=saved_account.email,
            display_name=saved_account.display_name,
            is_active=saved_account.is_active,
            created_at=saved_account.created_at
        )
    
    async def get_account_by_id(self, account_id: UUID) -> Optional[AccountDetailResponse]:
        """
        Get account details by ID.
        
        Args:
            account_id: Account ID
            
        Returns:
            Account details or None if not found
        """
        account = await self.account_repository.find_by_id(account_id)
        if not account:
            return None
        
        return AccountDetailResponse(
            account_id=account.id,
            user_id=account.user_id,
            email=account.email,
            display_name=account.display_name,
            is_active=account.is_active,
            token_expires_at=account.token_expires_at,
            last_sync_at=account.last_sync_at,
            created_at=account.created_at,
            updated_at=account.updated_at
        )
    
    async def get_accounts_by_user_id(self, user_id: UUID) -> AccountListResponse:
        """
        Get all accounts for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of user's accounts
        """
        accounts = await self.account_repository.find_by_user_id(user_id)
        
        account_details = []
        active_count = 0
        
        for account in accounts:
            if account.is_active:
                active_count += 1
            
            account_details.append(AccountDetailResponse(
                account_id=account.id,
                user_id=account.user_id,
                email=account.email,
                display_name=account.display_name,
                is_active=account.is_active,
                token_expires_at=account.token_expires_at,
                last_sync_at=account.last_sync_at,
                created_at=account.created_at,
                updated_at=account.updated_at
            ))
        
        return AccountListResponse(
            accounts=account_details,
            total_count=len(accounts),
            active_count=active_count
        )
    
    async def get_all_accounts(self, skip: int = 0, limit: int = 100) -> AccountListResponse:
        """
        Get all accounts with pagination.
        
        Args:
            skip: Number of accounts to skip
            limit: Maximum number of accounts to return
            
        Returns:
            Paginated list of accounts
        """
        accounts = await self.account_repository.find_all(skip=skip, limit=limit)
        
        account_details = []
        active_count = 0
        
        for account in accounts:
            if account.is_active:
                active_count += 1
            
            account_details.append(AccountDetailResponse(
                account_id=account.id,
                user_id=account.user_id,
                email=account.email,
                display_name=account.display_name,
                is_active=account.is_active,
                token_expires_at=account.token_expires_at,
                last_sync_at=account.last_sync_at,
                created_at=account.created_at,
                updated_at=account.updated_at
            ))
        
        return AccountListResponse(
            accounts=account_details,
            total_count=len(accounts),
            active_count=active_count
        )
    
    async def get_active_accounts(self) -> AccountListResponse:
        """
        Get all active accounts.
        
        Returns:
            List of active accounts
        """
        accounts = await self.account_repository.find_active_accounts()
        
        account_details = []
        for account in accounts:
            account_details.append(AccountDetailResponse(
                account_id=account.id,
                user_id=account.user_id,
                email=account.email,
                display_name=account.display_name,
                is_active=account.is_active,
                token_expires_at=account.token_expires_at,
                last_sync_at=account.last_sync_at,
                created_at=account.created_at,
                updated_at=account.updated_at
            ))
        
        return AccountListResponse(
            accounts=account_details,
            total_count=len(accounts),
            active_count=len(accounts)
        )
    
    async def update_account(
        self, 
        account_id: UUID, 
        request: UpdateAccountRequest
    ) -> UpdateAccountResponse:
        """
        Update account information.
        
        Args:
            account_id: Account ID to update
            request: Update request data
            
        Returns:
            Update response
            
        Raises:
            ValueError: If account not found
        """
        account = await self.account_repository.find_by_id(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")
        
        # Update fields if provided
        if request.display_name is not None:
            account.display_name = request.display_name
        
        if request.is_active is not None:
            account.is_active = request.is_active
        
        # Save updated account
        await self.account_repository.update(account)
        
        return UpdateAccountResponse(account_id=account_id)
    
    async def delete_account(self, account_id: UUID) -> bool:
        """
        Delete an account.
        
        Args:
            account_id: Account ID to delete
            
        Returns:
            True if deleted successfully
            
        Raises:
            ValueError: If account not found
        """
        account = await self.account_repository.find_by_id(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")
        
        return await self.account_repository.delete(account_id)
    
    async def get_authorization_url(self, account_id: UUID) -> str:
        """
        Get OAuth authorization URL for account.
        
        Args:
            account_id: Account ID
            
        Returns:
            Authorization URL
            
        Raises:
            ValueError: If account not found
        """
        account = await self.account_repository.find_by_id(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")
        
        # Use account ID as state parameter for security
        state = str(account_id)
        return await self.graph_api.get_authorization_url(state=state)
    
    async def authorize_account(
        self, 
        request: AuthorizeAccountRequest
    ) -> AuthorizeAccountResponse:
        """
        Authorize account with OAuth code.
        
        Args:
            request: Authorization request
            
        Returns:
            Authorization response
            
        Raises:
            ValueError: If account not found or authorization fails
        """
        account = await self.account_repository.find_by_id(request.account_id)
        if not account:
            raise ValueError(f"Account with ID {request.account_id} not found")
        
        # Validate state parameter
        if request.state and request.state != str(request.account_id):
            raise ValueError("Invalid state parameter")
        
        # Exchange code for token
        token_info = await self.graph_api.exchange_code_for_token(
            code=request.authorization_code,
            state=request.state
        )
        
        # Update account with token information
        await self.account_repository.update_token_info(
            account_id=request.account_id,
            token_info=token_info
        )
        
        # Get updated account
        updated_account = await self.account_repository.find_by_id(request.account_id)
        
        return AuthorizeAccountResponse(
            account_id=request.account_id,
            email=updated_account.email,
            token_expires_at=updated_account.token_expires_at
        )
    
    async def refresh_account_token(self, account_id: UUID) -> bool:
        """
        Refresh account access token.
        
        Args:
            account_id: Account ID
            
        Returns:
            True if token refreshed successfully
            
        Raises:
            ValueError: If account not found or refresh fails
        """
        account = await self.account_repository.find_by_id(account_id)
        if not account:
            raise ValueError(f"Account with ID {account_id} not found")
        
        if not account.refresh_token:
            raise ValueError("No refresh token available for account")
        
        # Refresh token
        token_info = await self.graph_api.refresh_token(account)
        
        # Update account with new token information
        await self.account_repository.update_token_info(
            account_id=account_id,
            token_info=token_info
        )
        
        return True


# Custom Exceptions
class AccountManagementError(Exception):
    """Base exception for account management errors."""
    pass


class AccountNotFoundError(AccountManagementError):
    """Account not found error."""
    pass


class AccountAlreadyExistsError(AccountManagementError):
    """Account already exists error."""
    pass


class AccountAuthorizationError(AccountManagementError):
    """Account authorization error."""
    pass

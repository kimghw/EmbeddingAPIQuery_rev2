"""FastAPI routers implementation."""

import logging
from datetime import datetime, UTC
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from fastapi.responses import JSONResponse

from .dependencies import (
    get_account_usecase, get_email_usecase, get_transmission_usecase,
    get_config_dependency, get_graph_api_dependency, get_external_api_dependency,
    get_db_adapter_dependency
)
from .schemas import (
    # Base schemas
    BaseResponse, ErrorResponse,
    # Account schemas
    AccountCreate, AccountUpdate, AccountResponse, AccountListResponse,
    AccountCreateResponse, AuthorizationUrlResponse, AuthorizeAccountRequest,
    AuthorizeAccountResponse,
    # Email schemas
    EmailResponse, EmailListResponse, EmailDetectionRequest, EmailDetectionResponse,
    EmailFilterParams, PaginationParams,
    # Transmission schemas
    TransmissionRecordResponse, TransmissionListResponse, TransmissionRequest,
    TransmissionResponse, TransmissionSummaryResponse, RetryTransmissionRequest,
    TransmissionFilterParams,
    # Health and config schemas
    HealthCheckResponse, DatabaseHealthResponse, ConfigurationResponse,
    ConnectionTestResponse,
    # Statistics schemas
    SystemStatisticsResponse
)

from core.usecases.account_management import AccountManagementUseCase
from core.usecases.email_detection import EmailDetectionUseCase
from core.usecases.external_transmission import ExternalTransmissionUseCase


logger = logging.getLogger(__name__)


def create_api_router() -> APIRouter:
    """Create and configure the main API router."""
    router = APIRouter()
    
    # Include sub-routers
    router.include_router(
        create_account_router(),
        prefix="/accounts",
        tags=["accounts"]
    )
    
    router.include_router(
        create_email_router(),
        prefix="/emails",
        tags=["emails"]
    )
    
    router.include_router(
        create_transmission_router(),
        prefix="/transmissions",
        tags=["transmissions"]
    )
    
    router.include_router(
        create_health_router(),
        prefix="/health",
        tags=["health"]
    )
    
    router.include_router(
        create_config_router(),
        prefix="/config",
        tags=["configuration"]
    )
    
    return router


def create_account_router() -> APIRouter:
    """Create account management router."""
    router = APIRouter()
    
    @router.get("/", response_model=AccountListResponse)
    async def list_accounts(
        user_id: Optional[UUID] = Query(None, description="Filter by user ID"),
        active_only: bool = Query(False, description="Show only active accounts"),
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Page size"),
        account_usecase: AccountManagementUseCase = Depends(get_account_usecase)
    ):
        """List accounts with optional filtering."""
        try:
            if user_id:
                result = await account_usecase.get_user_accounts(user_id)
                accounts = result.accounts
            elif active_only:
                result = await account_usecase.get_active_accounts()
                accounts = result.accounts
            else:
                # For now, return empty list - would need to implement get_all_accounts
                accounts = []
            
            return AccountListResponse(
                success=True,
                accounts=[AccountResponse.from_orm(acc) for acc in accounts],
                total=len(accounts),
                message="Accounts retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error listing accounts: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/", response_model=AccountCreateResponse)
    async def create_account(
        account_data: AccountCreate,
        account_usecase: AccountManagementUseCase = Depends(get_account_usecase)
    ):
        """Create a new account."""
        try:
            result = await account_usecase.create_account(
                username=account_data.username,
                email=account_data.email,
                display_name=account_data.display_name
            )
            
            if result.success:
                return AccountCreateResponse(
                    success=True,
                    account=AccountResponse.from_orm(result.account),
                    message="Account created successfully"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating account: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/{account_id}", response_model=AccountResponse)
    async def get_account(
        account_id: UUID,
        account_usecase: AccountManagementUseCase = Depends(get_account_usecase)
    ):
        """Get account by ID."""
        try:
            result = await account_usecase.get_account_by_id(account_id)
            
            if result.success and result.account:
                return AccountResponse.from_orm(result.account)
            else:
                raise HTTPException(status_code=404, detail="Account not found")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting account {account_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.put("/{account_id}", response_model=AccountResponse)
    async def update_account(
        account_id: UUID,
        account_data: AccountUpdate,
        account_usecase: AccountManagementUseCase = Depends(get_account_usecase)
    ):
        """Update account."""
        try:
            result = await account_usecase.update_account(
                account_id,
                display_name=account_data.display_name,
                is_active=account_data.is_active
            )
            
            if result.success:
                return AccountResponse.from_orm(result.account)
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating account {account_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.delete("/{account_id}", response_model=BaseResponse)
    async def delete_account(
        account_id: UUID,
        account_usecase: AccountManagementUseCase = Depends(get_account_usecase)
    ):
        """Delete account."""
        try:
            result = await account_usecase.remove_account(account_id)
            
            if result.success:
                return BaseResponse(
                    success=True,
                    message="Account deleted successfully"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting account {account_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/{account_id}/authorization-url", response_model=AuthorizationUrlResponse)
    async def get_authorization_url(
        account_id: UUID,
        account_usecase: AccountManagementUseCase = Depends(get_account_usecase)
    ):
        """Get OAuth authorization URL for account."""
        try:
            result = await account_usecase.get_authorization_url(account_id)
            
            if result.success:
                return AuthorizationUrlResponse(
                    success=True,
                    authorization_url=result.authorization_url,
                    message="Authorization URL generated successfully"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting authorization URL for account {account_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/{account_id}/authorize", response_model=AuthorizeAccountResponse)
    async def authorize_account(
        account_id: UUID,
        auth_data: AuthorizeAccountRequest,
        account_usecase: AccountManagementUseCase = Depends(get_account_usecase)
    ):
        """Authorize account with OAuth code."""
        try:
            result = await account_usecase.authorize_account(
                account_id,
                auth_data.authorization_code
            )
            
            if result.success:
                return AuthorizeAccountResponse(
                    success=True,
                    account=AccountResponse.from_orm(result.account),
                    message="Account authorized successfully"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error authorizing account {account_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router


def create_email_router() -> APIRouter:
    """Create email management router."""
    router = APIRouter()
    
    @router.get("/", response_model=EmailListResponse)
    async def list_emails(
        account_id: Optional[UUID] = Query(None, description="Filter by account ID"),
        status: Optional[str] = Query(None, description="Filter by processing status"),
        sender: Optional[str] = Query(None, description="Filter by sender"),
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Page size"),
        email_usecase: EmailDetectionUseCase = Depends(get_email_usecase)
    ):
        """List emails with optional filtering."""
        try:
            if account_id:
                result = await email_usecase.get_emails_by_account(account_id, limit=size)
                emails = result.emails
            elif status:
                result = await email_usecase.get_emails_by_status(status, limit=size)
                emails = result.emails
            else:
                # For now, return empty list - would need to implement get_recent_emails
                emails = []
            
            return EmailListResponse(
                success=True,
                emails=[EmailResponse.from_orm(email) for email in emails],
                total=len(emails),
                message="Emails retrieved successfully"
            )
            
        except Exception as e:
            logger.error(f"Error listing emails: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/{email_id}", response_model=EmailResponse)
    async def get_email(
        email_id: UUID,
        email_usecase: EmailDetectionUseCase = Depends(get_email_usecase)
    ):
        """Get email by ID."""
        try:
            result = await email_usecase.get_email_by_id(email_id)
            
            if result.success and result.email:
                return EmailResponse.from_orm(result.email)
            else:
                raise HTTPException(status_code=404, detail="Email not found")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting email {email_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/detect", response_model=EmailDetectionResponse)
    async def detect_emails(
        detection_request: EmailDetectionRequest,
        background_tasks: BackgroundTasks,
        email_usecase: EmailDetectionUseCase = Depends(get_email_usecase)
    ):
        """Detect new emails from Microsoft Graph API."""
        try:
            if detection_request.account_id:
                result = await email_usecase.detect_emails_for_account(
                    detection_request.account_id,
                    limit=detection_request.limit,
                    use_delta=detection_request.use_delta
                )
            else:
                result = await email_usecase.detect_emails_for_all_accounts(
                    limit=detection_request.limit,
                    use_delta=detection_request.use_delta
                )
            
            if result.success:
                return EmailDetectionResponse(
                    success=True,
                    emails=[EmailResponse.from_orm(email) for email in result.emails],
                    new_count=result.new_count,
                    updated_count=result.updated_count,
                    total_processed=len(result.emails),
                    message="Email detection completed successfully"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error detecting emails: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router


def create_transmission_router() -> APIRouter:
    """Create transmission management router."""
    router = APIRouter()
    
    @router.get("/", response_model=TransmissionListResponse)
    async def list_transmissions(
        email_id: Optional[UUID] = Query(None, description="Filter by email ID"),
        status: Optional[str] = Query(None, description="Filter by transmission status"),
        page: int = Query(1, ge=1, description="Page number"),
        size: int = Query(20, ge=1, le=100, description="Page size"),
        transmission_usecase: ExternalTransmissionUseCase = Depends(get_transmission_usecase)
    ):
        """List transmission records with optional filtering."""
        try:
            result = await transmission_usecase.get_transmission_records(
                email_id=email_id,
                status=status,
                limit=size
            )
            
            if result.success:
                return TransmissionListResponse(
                    success=True,
                    transmissions=[TransmissionRecordResponse.from_orm(t) for t in result.transmission_records],
                    total=len(result.transmission_records),
                    message="Transmission records retrieved successfully"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error listing transmissions: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/send", response_model=TransmissionResponse)
    async def send_emails(
        transmission_request: TransmissionRequest,
        background_tasks: BackgroundTasks,
        transmission_usecase: ExternalTransmissionUseCase = Depends(get_transmission_usecase)
    ):
        """Send emails to external API."""
        try:
            result = await transmission_usecase.transmit_pending_emails(
                limit=transmission_request.limit,
                endpoint=transmission_request.endpoint
            )
            
            if result.success:
                return TransmissionResponse(
                    success=True,
                    transmission_records=[TransmissionRecordResponse.from_orm(t) for t in result.transmission_records],
                    total_processed=result.total_processed,
                    successful_count=result.successful_count,
                    failed_count=result.failed_count,
                    message="Email transmission completed"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error sending emails: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.post("/retry", response_model=TransmissionResponse)
    async def retry_failed_transmissions(
        retry_request: RetryTransmissionRequest,
        background_tasks: BackgroundTasks,
        transmission_usecase: ExternalTransmissionUseCase = Depends(get_transmission_usecase)
    ):
        """Retry failed transmissions."""
        try:
            result = await transmission_usecase.retry_failed_transmissions(
                limit=retry_request.limit
            )
            
            if result.success:
                return TransmissionResponse(
                    success=True,
                    transmission_records=[TransmissionRecordResponse.from_orm(t) for t in result.transmission_records],
                    total_processed=result.total_processed,
                    successful_count=result.successful_count,
                    failed_count=result.failed_count,
                    message="Retry completed"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error retrying transmissions: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/summary", response_model=TransmissionSummaryResponse)
    async def get_transmission_summary(
        transmission_usecase: ExternalTransmissionUseCase = Depends(get_transmission_usecase)
    ):
        """Get transmission status summary."""
        try:
            result = await transmission_usecase.get_transmission_summary()
            
            if result.success:
                return TransmissionSummaryResponse(
                    success=True,
                    summary=result.summary,
                    message="Transmission summary retrieved successfully"
                )
            else:
                raise HTTPException(status_code=400, detail=result.error)
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting transmission summary: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router


def create_health_router() -> APIRouter:
    """Create health check router."""
    router = APIRouter()
    
    @router.get("/", response_model=HealthCheckResponse)
    async def health_check(
        config = Depends(get_config_dependency),
        db_adapter = Depends(get_db_adapter_dependency),
        graph_api = Depends(get_graph_api_dependency),
        external_api = Depends(get_external_api_dependency)
    ):
        """Comprehensive health check."""
        try:
            services = {}
            
            # Check database
            try:
                services["database"] = await db_adapter.health_check()
            except Exception as e:
                logger.error(f"Database health check failed: {e}")
                services["database"] = False
            
            # Check Graph API
            try:
                services["graph_api"] = await graph_api.health_check()
            except Exception as e:
                logger.error(f"Graph API health check failed: {e}")
                services["graph_api"] = False
            
            # Check External API
            try:
                services["external_api"] = await external_api.health_check()
            except Exception as e:
                logger.error(f"External API health check failed: {e}")
                services["external_api"] = False
            
            # Overall status
            all_healthy = all(services.values())
            status = "healthy" if all_healthy else "unhealthy"
            
            return HealthCheckResponse(
                status=status,
                services=services,
                timestamp=datetime.now(UTC)
            )
            
        except Exception as e:
            logger.error(f"Health check error: {e}")
            return HealthCheckResponse(
                status="error",
                services={},
                timestamp=datetime.now(UTC)
            )
    
    @router.get("/database", response_model=DatabaseHealthResponse)
    async def database_health(
        db_adapter = Depends(get_db_adapter_dependency)
    ):
        """Database-specific health check."""
        try:
            is_healthy = await db_adapter.health_check()
            
            return DatabaseHealthResponse(
                status="healthy" if is_healthy else "unhealthy",
                connection=is_healthy,
                timestamp=datetime.now(UTC)
            )
            
        except Exception as e:
            logger.error(f"Database health check error: {e}")
            return DatabaseHealthResponse(
                status="error",
                connection=False,
                timestamp=datetime.now(UTC)
            )
    
    return router


def create_config_router() -> APIRouter:
    """Create configuration router."""
    router = APIRouter()
    
    @router.get("/", response_model=ConfigurationResponse)
    async def get_configuration(
        config = Depends(get_config_dependency)
    ):
        """Get current configuration (with sensitive data masked)."""
        try:
            # Safely get environment with fallback
            try:
                environment = config.get_environment()
            except Exception:
                environment = "development"  # fallback
            
            return ConfigurationResponse(
                environment=environment,
                database_url_masked=config.get_database_url().split('@')[-1] if '@' in config.get_database_url() else config.get_database_url(),
                graph_api_endpoint=config.get_graph_api_endpoint(),
                external_api_url=config.get_external_api_url(),
                client_id_masked=config.get_client_id()[:8] + "..." if config.get_client_id() else "Not set",
                client_secret_configured=bool(config.get_client_secret()),
                external_api_key_configured=bool(config.get_external_api_key())
            )
            
        except Exception as e:
            logger.error(f"Error getting configuration: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @router.get("/test-connections", response_model=ConnectionTestResponse)
    async def test_connections(
        graph_api = Depends(get_graph_api_dependency),
        external_api = Depends(get_external_api_dependency)
    ):
        """Test connections to external services."""
        try:
            # Test Graph API
            graph_healthy = await graph_api.health_check()
            
            # Test External API
            external_test_result = await external_api.test_connection()
            
            tests = {
                "graph_api": {
                    "passed": graph_healthy,
                    "message": "Graph API connection OK" if graph_healthy else "Graph API connection failed"
                },
                "external_api": external_test_result["tests"]
            }
            
            # Overall result
            all_passed = graph_healthy and external_test_result["overall_result"]["passed"]
            overall_result = {
                "passed": all_passed,
                "message": "All connections OK" if all_passed else "Some connections failed"
            }
            
            return ConnectionTestResponse(
                timestamp=datetime.now(UTC),
                tests=tests,
                overall_result=overall_result
            )
            
        except Exception as e:
            logger.error(f"Error testing connections: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    return router


# Error handlers
async def handle_validation_error(request, exc):
    """Handle validation errors."""
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            success=False,
            error_code="VALIDATION_ERROR",
            message="Validation failed",
            details={"errors": exc.errors()}
        ).dict()
    )


async def handle_http_exception(request, exc):
    """Handle HTTP exceptions."""
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            success=False,
            error_code=f"HTTP_{exc.status_code}",
            message=exc.detail
        ).dict()
    )


async def handle_general_exception(request, exc):
    """Handle general exceptions."""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            success=False,
            error_code="INTERNAL_SERVER_ERROR",
            message="An internal server error occurred"
        ).dict()
    )

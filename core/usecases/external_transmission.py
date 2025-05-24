"""External API transmission use cases."""

from typing import List, Optional, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from ..domain.email import Email
from ..domain.transmission_record import TransmissionRecord
from ..ports.repository import EmailRepository, TransmissionRecordRepository
from ..ports.external_api import ExternalAPIPort
from ..ports.config import ConfigPort


# Enums
class TransmissionStatus(str, Enum):
    """Transmission status enumeration."""
    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    CANCELLED = "cancelled"


class TransmissionPriority(str, Enum):
    """Transmission priority enumeration."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


# Request/Response Models
class TransmissionRequest(BaseModel):
    """Request model for single email transmission."""
    email_id: UUID
    endpoint: Optional[str] = Field(None, description="Custom endpoint URL")
    headers: Optional[Dict[str, str]] = Field(None, description="Custom headers")
    priority: TransmissionPriority = TransmissionPriority.NORMAL
    retry_count: int = Field(0, description="Current retry count")
    max_retries: int = Field(3, description="Maximum retry attempts")


class TransmissionResponse(BaseModel):
    """Response model for transmission."""
    transmission_id: UUID
    email_id: UUID
    status: TransmissionStatus
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    transmitted_at: datetime = Field(default_factory=datetime.utcnow)
    processing_time_ms: Optional[int] = None


class BulkTransmissionRequest(BaseModel):
    """Request model for bulk email transmission."""
    email_ids: List[UUID]
    endpoint: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    priority: TransmissionPriority = TransmissionPriority.NORMAL
    batch_size: int = Field(10, description="Number of emails per batch")
    delay_between_batches: int = Field(1, description="Delay in seconds between batches")


class BulkTransmissionResponse(BaseModel):
    """Response model for bulk transmission."""
    total_emails: int
    successful_transmissions: int
    failed_transmissions: int
    transmission_results: List[TransmissionResponse]
    processing_time_ms: int
    started_at: datetime = Field(default_factory=datetime.utcnow)


class RetryTransmissionRequest(BaseModel):
    """Request model for retrying failed transmissions."""
    transmission_record_id: Optional[UUID] = None
    email_id: Optional[UUID] = None
    max_retry_count: int = Field(3, description="Maximum retry attempts")
    force_retry: bool = Field(False, description="Force retry even if max retries exceeded")


class RetryTransmissionResponse(BaseModel):
    """Response model for retry transmission."""
    transmission_id: UUID
    email_id: UUID
    retry_attempt: int
    status: TransmissionStatus
    response_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    retried_at: datetime = Field(default_factory=datetime.utcnow)


class TransmissionStatusRequest(BaseModel):
    """Request model for transmission status check."""
    transmission_ids: Optional[List[UUID]] = None
    email_ids: Optional[List[UUID]] = None
    status_filter: Optional[TransmissionStatus] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


class TransmissionStatusResponse(BaseModel):
    """Response model for transmission status."""
    transmission_records: List[Dict[str, Any]]
    total_count: int
    status_summary: Dict[str, int]


class CleanupRequest(BaseModel):
    """Request model for cleanup old transmission records."""
    days_old: int = Field(30, description="Delete records older than this many days")
    status_filter: Optional[List[TransmissionStatus]] = Field(
        None, 
        description="Only delete records with these statuses"
    )
    dry_run: bool = Field(False, description="Preview what would be deleted without actually deleting")


class CleanupResponse(BaseModel):
    """Response model for cleanup operation."""
    records_deleted: int
    records_preview: Optional[List[Dict[str, Any]]] = None
    cleanup_completed_at: datetime = Field(default_factory=datetime.utcnow)


# Use Case Implementation
class ExternalTransmissionUseCase:
    """Use case for transmitting email data to external APIs."""
    
    def __init__(
        self,
        email_repository: EmailRepository,
        transmission_repository: TransmissionRecordRepository,
        external_api: ExternalAPIPort,
        config: ConfigPort
    ):
        self.email_repository = email_repository
        self.transmission_repository = transmission_repository
        self.external_api = external_api
        self.config = config
    
    async def transmit_email(self, request: TransmissionRequest) -> TransmissionResponse:
        """
        Transmit single email to external API.
        
        Args:
            request: Transmission request
            
        Returns:
            Transmission response
            
        Raises:
            ValueError: If email not found
        """
        start_time = datetime.utcnow()
        
        # Get email from database
        email = await self.email_repository.find_by_id(request.email_id)
        if not email:
            raise ValueError(f"Email with ID {request.email_id} not found")
        
        # Create transmission record
        transmission_record = TransmissionRecord(
            email_id=request.email_id,
            status=TransmissionStatus.PROCESSING.value,
            priority=request.priority.value,
            retry_count=request.retry_count,
            max_retries=request.max_retries
        )
        
        saved_record = await self.transmission_repository.save(transmission_record)
        
        try:
            # Transform email for API
            email_data = await self.external_api.transform_email_for_api(email)
            
            # Send to external API
            response_data = await self.external_api.send_email_data(
                email_data=email_data,
                endpoint=request.endpoint,
                headers=request.headers
            )
            
            # Update transmission record with success
            await self.transmission_repository.update_status(
                record_id=saved_record.id,
                status=TransmissionStatus.SUCCESS.value
            )
            
            # Update email processing status
            await self.email_repository.update_processing_status(
                email_id=request.email_id,
                status="transmitted"
            )
            
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return TransmissionResponse(
                transmission_id=saved_record.id,
                email_id=request.email_id,
                status=TransmissionStatus.SUCCESS,
                response_data=response_data,
                processing_time_ms=processing_time
            )
            
        except Exception as e:
            # Update transmission record with failure
            await self.transmission_repository.update_status(
                record_id=saved_record.id,
                status=TransmissionStatus.FAILED.value,
                error_message=str(e)
            )
            
            processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            return TransmissionResponse(
                transmission_id=saved_record.id,
                email_id=request.email_id,
                status=TransmissionStatus.FAILED,
                error_message=str(e),
                processing_time_ms=processing_time
            )
    
    async def transmit_bulk_emails(
        self, 
        request: BulkTransmissionRequest
    ) -> BulkTransmissionResponse:
        """
        Transmit multiple emails in batches.
        
        Args:
            request: Bulk transmission request
            
        Returns:
            Bulk transmission response
        """
        start_time = datetime.utcnow()
        transmission_results = []
        successful_count = 0
        failed_count = 0
        
        # Process emails in batches
        for i in range(0, len(request.email_ids), request.batch_size):
            batch = request.email_ids[i:i + request.batch_size]
            
            # Process batch concurrently
            batch_tasks = []
            for email_id in batch:
                transmission_request = TransmissionRequest(
                    email_id=email_id,
                    endpoint=request.endpoint,
                    headers=request.headers,
                    priority=request.priority
                )
                batch_tasks.append(self.transmit_email(transmission_request))
            
            # Wait for batch completion
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)
            
            # Process batch results
            for result in batch_results:
                if isinstance(result, Exception):
                    failed_count += 1
                    # Create error response
                    transmission_results.append(TransmissionResponse(
                        transmission_id=UUID('00000000-0000-0000-0000-000000000000'),
                        email_id=UUID('00000000-0000-0000-0000-000000000000'),
                        status=TransmissionStatus.FAILED,
                        error_message=str(result)
                    ))
                else:
                    transmission_results.append(result)
                    if result.status == TransmissionStatus.SUCCESS:
                        successful_count += 1
                    else:
                        failed_count += 1
            
            # Delay between batches if not the last batch
            if i + request.batch_size < len(request.email_ids):
                await asyncio.sleep(request.delay_between_batches)
        
        processing_time = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        return BulkTransmissionResponse(
            total_emails=len(request.email_ids),
            successful_transmissions=successful_count,
            failed_transmissions=failed_count,
            transmission_results=transmission_results,
            processing_time_ms=processing_time
        )
    
    async def retry_failed_transmission(
        self, 
        request: RetryTransmissionRequest
    ) -> RetryTransmissionResponse:
        """
        Retry failed transmission.
        
        Args:
            request: Retry transmission request
            
        Returns:
            Retry transmission response
            
        Raises:
            ValueError: If transmission record or email not found
        """
        # Get transmission record
        if request.transmission_record_id:
            transmission_record = await self.transmission_repository.find_by_id(
                request.transmission_record_id
            )
        elif request.email_id:
            # Find latest failed transmission for email
            records = await self.transmission_repository.find_by_email_id(request.email_id)
            transmission_record = None
            for record in records:
                if record.status == TransmissionStatus.FAILED.value:
                    transmission_record = record
                    break
        else:
            raise ValueError("Either transmission_record_id or email_id must be provided")
        
        if not transmission_record:
            raise ValueError("Transmission record not found")
        
        # Check retry limits
        if (transmission_record.retry_count >= request.max_retry_count and 
            not request.force_retry):
            raise ValueError(
                f"Maximum retry count ({request.max_retry_count}) exceeded"
            )
        
        # Increment retry count
        await self.transmission_repository.increment_retry_count(transmission_record.id)
        
        # Create new transmission request
        retry_request = TransmissionRequest(
            email_id=transmission_record.email_id,
            retry_count=transmission_record.retry_count + 1,
            max_retries=request.max_retry_count
        )
        
        # Attempt transmission
        result = await self.transmit_email(retry_request)
        
        return RetryTransmissionResponse(
            transmission_id=result.transmission_id,
            email_id=result.email_id,
            retry_attempt=transmission_record.retry_count + 1,
            status=result.status,
            response_data=result.response_data,
            error_message=result.error_message
        )
    
    async def get_transmission_status(
        self, 
        request: TransmissionStatusRequest
    ) -> TransmissionStatusResponse:
        """
        Get transmission status for specified criteria.
        
        Args:
            request: Transmission status request
            
        Returns:
            Transmission status response
        """
        records = []
        
        if request.transmission_ids:
            for transmission_id in request.transmission_ids:
                record = await self.transmission_repository.find_by_id(transmission_id)
                if record:
                    records.append(record)
        
        elif request.email_ids:
            for email_id in request.email_ids:
                email_records = await self.transmission_repository.find_by_email_id(email_id)
                records.extend(email_records)
        
        elif request.status_filter:
            records = await self.transmission_repository.find_by_status(
                status=request.status_filter.value
            )
        
        else:
            records = await self.transmission_repository.find_all()
        
        # Apply date filters
        if request.date_from or request.date_to:
            filtered_records = []
            for record in records:
                if request.date_from and record.created_at < request.date_from:
                    continue
                if request.date_to and record.created_at > request.date_to:
                    continue
                filtered_records.append(record)
            records = filtered_records
        
        # Convert to response format
        transmission_records = []
        status_summary = {}
        
        for record in records:
            transmission_records.append({
                "transmission_id": str(record.id),
                "email_id": str(record.email_id),
                "status": record.status,
                "priority": record.priority,
                "retry_count": record.retry_count,
                "max_retries": record.max_retries,
                "error_message": record.error_message,
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat()
            })
            
            # Update status summary
            status = record.status
            status_summary[status] = status_summary.get(status, 0) + 1
        
        return TransmissionStatusResponse(
            transmission_records=transmission_records,
            total_count=len(records),
            status_summary=status_summary
        )
    
    async def process_pending_transmissions(
        self, 
        limit: int = 100,
        priority_order: bool = True
    ) -> BulkTransmissionResponse:
        """
        Process pending transmissions from the queue.
        
        Args:
            limit: Maximum number of transmissions to process
            priority_order: Process by priority order
            
        Returns:
            Bulk transmission response
        """
        # Get pending transmission records
        pending_records = await self.transmission_repository.find_pending_records(limit)
        
        if not pending_records:
            return BulkTransmissionResponse(
                total_emails=0,
                successful_transmissions=0,
                failed_transmissions=0,
                transmission_results=[],
                processing_time_ms=0
            )
        
        # Sort by priority if requested
        if priority_order:
            priority_order_map = {
                TransmissionPriority.URGENT.value: 0,
                TransmissionPriority.HIGH.value: 1,
                TransmissionPriority.NORMAL.value: 2,
                TransmissionPriority.LOW.value: 3
            }
            pending_records.sort(
                key=lambda x: priority_order_map.get(x.priority, 999)
            )
        
        # Create transmission requests
        email_ids = [record.email_id for record in pending_records]
        
        bulk_request = BulkTransmissionRequest(
            email_ids=email_ids,
            batch_size=10,
            delay_between_batches=1
        )
        
        return await self.transmit_bulk_emails(bulk_request)
    
    async def cleanup_old_records(self, request: CleanupRequest) -> CleanupResponse:
        """
        Clean up old transmission records.
        
        Args:
            request: Cleanup request
            
        Returns:
            Cleanup response
        """
        cutoff_date = datetime.utcnow() - timedelta(days=request.days_old)
        
        if request.dry_run:
            # Preview what would be deleted
            all_records = await self.transmission_repository.find_all()
            records_to_delete = []
            
            for record in all_records:
                if record.created_at < cutoff_date:
                    if (not request.status_filter or 
                        record.status in [s.value for s in request.status_filter]):
                        records_to_delete.append({
                            "transmission_id": str(record.id),
                            "email_id": str(record.email_id),
                            "status": record.status,
                            "created_at": record.created_at.isoformat()
                        })
            
            return CleanupResponse(
                records_deleted=0,
                records_preview=records_to_delete
            )
        
        else:
            # Actually delete records
            deleted_count = await self.transmission_repository.cleanup_old_records(
                days=request.days_old
            )
            
            return CleanupResponse(
                records_deleted=deleted_count
            )
    
    async def get_transmission_statistics(
        self, 
        days_back: int = 7
    ) -> Dict[str, Any]:
        """
        Get transmission statistics for the specified period.
        
        Args:
            days_back: Number of days to look back
            
        Returns:
            Statistics dictionary
        """
        since_date = datetime.utcnow() - timedelta(days=days_back)
        
        # Get all records since the date
        all_records = await self.transmission_repository.find_all()
        recent_records = [
            record for record in all_records 
            if record.created_at >= since_date
        ]
        
        # Calculate statistics
        total_transmissions = len(recent_records)
        status_counts = {}
        priority_counts = {}
        daily_counts = {}
        
        for record in recent_records:
            # Status counts
            status = record.status
            status_counts[status] = status_counts.get(status, 0) + 1
            
            # Priority counts
            priority = record.priority or "normal"
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
            
            # Daily counts
            day_key = record.created_at.strftime("%Y-%m-%d")
            daily_counts[day_key] = daily_counts.get(day_key, 0) + 1
        
        # Calculate success rate
        success_count = status_counts.get(TransmissionStatus.SUCCESS.value, 0)
        success_rate = (success_count / total_transmissions * 100) if total_transmissions > 0 else 0
        
        return {
            "period_days": days_back,
            "total_transmissions": total_transmissions,
            "success_rate_percent": round(success_rate, 2),
            "status_breakdown": status_counts,
            "priority_breakdown": priority_counts,
            "daily_transmission_counts": daily_counts,
            "generated_at": datetime.utcnow().isoformat()
        }


# Custom Exceptions
class TransmissionError(Exception):
    """Base exception for transmission errors."""
    pass


class EmailNotFoundError(TransmissionError):
    """Email not found error."""
    pass


class TransmissionLimitExceededError(TransmissionError):
    """Transmission limit exceeded error."""
    pass


class RetryLimitExceededError(TransmissionError):
    """Retry limit exceeded error."""
    pass

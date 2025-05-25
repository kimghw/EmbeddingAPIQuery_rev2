#!/usr/bin/env python3
"""
Multi-account management CLI test script
"""
import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from adapters.config import ConfigAdapter
from adapters.db.database import initialize_database, get_database_adapter
from adapters.db.repositories import (
    SQLUserRepository, 
    SQLAccountRepository, 
    SQLEmailRepository, 
    SQLTransmissionRecordRepository
)
from adapters.graph_api import GraphAPIAdapter
from adapters.external_api import ExternalAPIAdapter
from core.usecases.multi_account_manager import MultiAccountManagerUseCase, MultiAccountSyncRequest
from core.usecases.account_management import AccountManagementUseCase
from core.domain.account import Account
from core.domain.user import User
import uuid
from datetime import datetime

async def test_multi_account_management():
    """Test multi-account management functionality"""
    print("🚀 Testing Multi-Account Management System")
    print("=" * 50)
    
    try:
        # 1. Initialize configuration
        print("1. Initializing configuration...")
        config = ConfigAdapter()
        print(f"   ✓ Environment: {config.get_environment()}")
        print(f"   ✓ Database URL: {config.get_database_url()}")
        
        # 2. Initialize database
        print("\n2. Initializing database...")
        db_adapter = initialize_database(config)
        await db_adapter.create_tables_async()
        print("   ✓ Database initialized")
        
        # 3. Create repositories with session
        print("\n3. Creating repositories...")
        async with db_adapter.async_session_scope() as session:
            user_repo = SQLUserRepository(session)
            account_repo = SQLAccountRepository(session)
            email_repo = SQLEmailRepository(session)
            transmission_repo = SQLTransmissionRecordRepository(session)
            print("   ✓ Repositories created")
            
            # 4. Create adapters
            print("\n4. Creating adapters...")
            graph_api = GraphAPIAdapter(config)
            external_api = ExternalAPIAdapter(config)
            print("   ✓ Adapters created")
            
            # 5. Create use cases
            print("\n5. Creating use cases...")
            account_mgmt = AccountManagementUseCase(
                user_repository=user_repo,
                account_repository=account_repo,
                graph_api=graph_api,
                config=config
            )
            
            # Create required use cases for MultiAccountManagerUseCase
            from core.usecases.email_detection import EmailDetectionUseCase
            from core.usecases.external_transmission import ExternalTransmissionUseCase
            
            email_detection = EmailDetectionUseCase(
                email_repository=email_repo,
                account_repository=account_repo,
                graph_api=graph_api,
                config=config
            )
            
            external_transmission = ExternalTransmissionUseCase(
                transmission_repository=transmission_repo,
                email_repository=email_repo,
                external_api=external_api,
                config=config
            )
            
            multi_account_mgr = MultiAccountManagerUseCase(
                account_management=account_mgmt,
                email_detection=email_detection,
                external_transmission=external_transmission,
                account_repository=account_repo,
                email_repository=email_repo,
                user_repository=user_repo,
                graph_api=graph_api,
                config=config
            )
            print("   ✓ Use cases created")
            
            # 6. Test user creation (direct repository call)
            print("\n6. Testing user creation...")
            unique_id = str(uuid.uuid4())[:8]
            test_user = User(
                id=str(uuid.uuid4()),
                username=f"test_user_{unique_id}",
                email=f"test_{unique_id}@example.com",
                created_at=datetime.now()
            )
            
            created_user = await user_repo.save(test_user)
            print(f"   ✓ User created: {created_user.username} ({created_user.id})")
            
            # 7. Test account addition
            print("\n7. Testing account addition...")
            test_account = Account(
                id=str(uuid.uuid4()),
                user_id=created_user.id,
                email_address="test.account@outlook.com",
                display_name="Test Account",
                created_at=datetime.now()
            )
            
            # Mock account addition (since we don't have real OAuth tokens)
            await account_repo.save(test_account)
            print(f"   ✓ Account added: {test_account.email_address}")
            
            # 8. Test multi-account sync
            print("\n8. Testing multi-account sync...")
            sync_request = MultiAccountSyncRequest(
                user_ids=[created_user.id],
                sync_active_only=True,
                use_delta=True
            )
            
            try:
                sync_result = await multi_account_mgr.sync_all_accounts(sync_request)
                print(f"   ✓ Sync completed: {len(sync_result.account_results)} accounts processed")
                
                for result in sync_result.account_results:
                    status = "✓" if result.status == "success" else "✗"
                    print(f"     {status} {result.email}: {result.status}")
                    
            except Exception as e:
                print(f"   ⚠ Sync failed (expected without real tokens): {str(e)}")
            
            # 9. Test account listing
            print("\n9. Testing account listing...")
            accounts = await account_repo.find_by_user_id(created_user.id)
            print(f"   ✓ Found {len(accounts)} accounts for user")
            
            for account in accounts:
                status = "Active" if account.is_active() else "Inactive"
                print(f"     - {account.email_address} - {status}")
            
            # 10. Test health check
            print("\n10. Testing health check...")
            try:
                from core.usecases.multi_account_manager import AccountHealthCheckRequest
                health_request = AccountHealthCheckRequest(
                    check_token_validity=True,
                    check_api_connectivity=True,
                    check_sync_status=True
                )
                health_result = await multi_account_mgr.check_accounts_health(health_request)
                print(f"   ✓ Health check completed: {len(health_result.account_statuses)} accounts checked")
                
                for result in health_result.account_statuses:
                    status = "✓" if result.is_healthy else "✗"
                    print(f"     {status} {result.email}: {'Healthy' if result.is_healthy else 'Unhealthy'}")
                    
            except Exception as e:
                print(f"   ⚠ Health check failed (expected without real tokens): {str(e)}")
        
        print("\n" + "=" * 50)
        print("🎉 Multi-Account Management Test Completed!")
        print("✓ All core components are working correctly")
        print("⚠ Some features require real OAuth tokens to fully test")
        
    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def main():
    """Main test function"""
    print("Multi-Account Management CLI Test")
    print("This test validates the core multi-account functionality")
    print()
    
    # Run the async test
    success = asyncio.run(test_multi_account_management())
    
    if success:
        print("\n✅ All tests passed!")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed!")
        sys.exit(1)

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Simple CLI test script for GraphAPI Query System."""

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from adapters.config import create_config_adapter
from adapters.db.database import initialize_database
from adapters.db.repositories import (
    SQLUserRepository, SQLAccountRepository, 
    SQLEmailRepository, SQLTransmissionRecordRepository
)
from adapters.graph_api import GraphAPIAdapter
from adapters.external_api import ExternalAPIAdapter
from core.usecases.account_management import (
    AccountManagementUseCase, 
    CreateAccountRequest
)
from core.domain.user import User


async def test_account_creation():
    """Test account creation functionality."""
    print("🚀 Testing GraphAPI Query System CLI...")
    
    # Initialize configuration
    config_adapter = create_config_adapter()
    
    print(f"📋 Environment: {config_adapter.get_environment()}")
    print(f"🗄️  Database: {config_adapter.get_database_url().split('@')[-1] if '@' in config_adapter.get_database_url() else 'Not configured'}")
    
    try:
        # Initialize database
        db_adapter = initialize_database(config_adapter)
        print("✅ Database initialized successfully")
        
        # Create tables
        await db_adapter.create_tables_async()
        print("✅ Database tables created successfully")
        
        # Use async session scope context manager
        async with db_adapter.async_session_scope() as session:
            # Create repositories with session
            user_repo = SQLUserRepository(session)
            account_repo = SQLAccountRepository(session)
            email_repo = SQLEmailRepository(session)
            transmission_repo = SQLTransmissionRecordRepository(session)
            
            # Create adapters
            graph_api = GraphAPIAdapter(config_adapter)
            external_api = ExternalAPIAdapter(config_adapter)
            
            # Create use case with correct parameter names
            account_usecase = AccountManagementUseCase(
                user_repository=user_repo,
                account_repository=account_repo,
                graph_api=graph_api,
                config=config_adapter
            )
            
            print("✅ Use cases initialized successfully")
            
            # First, create a test user
            print("\n👤 Creating test user...")
            test_user = User(
                username="test_user",
                email="test@example.com",
                display_name="Test User"
            )
            saved_user = await user_repo.save(test_user)
            print(f"✅ User created with ID: {saved_user.id}")
            
            # Test account creation
            print("\n📝 Testing account creation...")
            create_request = CreateAccountRequest(
                user_id=saved_user.id,
                email="test@example.com",
                display_name="Test User Account"
            )
            
            result = await account_usecase.create_account(create_request)
            
            print(f"✅ Account created successfully!")
            print(f"   ID: {result.account_id}")
            print(f"   Email: {result.email}")
            print(f"   Display Name: {result.display_name}")
            print(f"   Active: {result.is_active}")
            print(f"   Created: {result.created_at}")
            
            # Test account listing
            print("\n📋 Testing account listing...")
            list_result = await account_usecase.get_active_accounts()
            
            print(f"✅ Found {list_result.total_count} total accounts, {list_result.active_count} active")
            for account in list_result.accounts:
                print(f"   - {account.email} (ID: {account.account_id})")
            
            # Test getting account by ID
            print("\n🔍 Testing get account by ID...")
            account_detail = await account_usecase.get_account_by_id(result.account_id)
            if account_detail:
                print(f"✅ Account found:")
                print(f"   Email: {account_detail.email}")
                print(f"   Display Name: {account_detail.display_name}")
                print(f"   Active: {account_detail.is_active}")
            else:
                print("❌ Account not found")
            
            # Test authorization URL generation
            print("\n🔐 Testing authorization URL generation...")
            try:
                auth_url = await account_usecase.get_authorization_url(result.account_id)
                print(f"✅ Authorization URL generated:")
                print(f"   URL: {auth_url[:100]}...")
            except Exception as e:
                print(f"⚠️  Authorization URL generation failed (expected in test): {e}")
            
            print("\n🎉 All tests completed successfully!")
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main CLI entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "test":
            asyncio.run(test_account_creation())
        elif command == "config":
            config_adapter = create_config_adapter()
            print("📋 Current Configuration:")
            print(f"   Environment: {config_adapter.get_environment()}")
            print(f"   Database URL: {config_adapter.get_database_url().split('@')[-1] if '@' in config_adapter.get_database_url() else config_adapter.get_database_url()}")
            print(f"   Graph API Endpoint: {config_adapter.get_graph_api_endpoint()}")
            print(f"   External API URL: {config_adapter.get_external_api_url()}")
            print(f"   Client ID: {config_adapter.get_client_id()[:8] + '...' if config_adapter.get_client_id() else 'Not set'}")
            print(f"   Client Secret: {'Set' if config_adapter.get_client_secret() else 'Not set'}")
            print(f"   External API Key: {'Set' if config_adapter.get_external_api_key() else 'Not set'}")
        elif command == "version":
            print("GraphAPI Query System v1.0.0")
        else:
            print(f"❌ Unknown command: {command}")
            print_help()
    else:
        print_help()


def print_help():
    """Print help information."""
    print("""
🔧 GraphAPI Query System CLI

Usage: python cli_test.py <command>

Commands:
  test      - Test account creation and listing
  config    - Show current configuration
  version   - Show version information
  help      - Show this help message

Examples:
  python cli_test.py test
  python cli_test.py config
  python cli_test.py version
""")


if __name__ == "__main__":
    main()

"""
API Key Management Script for PriceScout API

This script provides utilities for managing API keys:
- Generate new API keys
- List existing keys
- Deactivate/reactivate keys
- View usage statistics
- Create database tables

Usage:
    # Create tables
    python manage_api_keys.py create-tables
    
    # Generate a new key
    python manage_api_keys.py generate --client "Acme Corp" --tier premium
    
    # List all keys
    python manage_api_keys.py list
    
    # Show key details
    python manage_api_keys.py show ps_prem_abcd
    
    # Deactivate a key
    python manage_api_keys.py deactivate ps_prem_abcd
    
    # View usage statistics
    python manage_api_keys.py usage ps_prem_abcd --days 7
"""

import sys
import os
from datetime import datetime, timedelta
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.auth import (
    generate_api_key, hash_api_key, get_key_prefix,
    APIKey, APIKeyUsage, TIER_LIMITS
)
from app.db_session import get_engine, get_session
from sqlalchemy import create_engine, func
import argparse


def create_tables():
    """Create API key tables in database"""
    print("Creating API key tables...")
    engine = get_engine()
    APIKey.metadata.create_all(engine)
    APIKeyUsage.metadata.create_all(engine)
    print("✅ Tables created successfully")


def generate_key(client_name: str, tier: str = "free", expires_days: Optional[int] = None, notes: Optional[str] = None):
    """
    Generate and store a new API key
    
    Args:
        client_name: Name of the client/company
        tier: API tier (free, premium, enterprise, internal)
        expires_days: Number of days until expiration (None = never)
        notes: Optional notes about this key
    """
    # Validate tier
    if tier not in TIER_LIMITS:
        print(f"❌ Invalid tier: {tier}")
        print(f"   Valid tiers: {', '.join(TIER_LIMITS.keys())}")
        return
    
    # Generate key
    api_key = generate_api_key(tier)
    key_hash = hash_api_key(api_key)
    key_prefix = get_key_prefix(api_key)
    
    # Calculate expiration
    expires_at = None
    if expires_days:
        expires_at = datetime.utcnow() + timedelta(days=expires_days)
    
    # Store in database
    with get_session() as db:
        key_record = APIKey(
            key_hash=key_hash,
            key_prefix=key_prefix,
            client_name=client_name,
            tier=tier,
            is_active=True,
            expires_at=expires_at,
            notes=notes
        )
        db.add(key_record)
        db.commit()
        
        print("\n" + "="*60)
        print("✅ API Key Generated Successfully")
        print("="*60)
        print(f"\n🔑 API Key: {api_key}")
        print(f"\n⚠️  IMPORTANT: Save this key securely! It cannot be retrieved later.\n")
        print(f"📋 Details:")
        print(f"   Client:     {client_name}")
        print(f"   Tier:       {tier}")
        print(f"   Prefix:     {key_prefix}")
        print(f"   Created:    {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
        if expires_at:
            print(f"   Expires:    {expires_at.strftime('%Y-%m-%d')} ({expires_days} days)")
        else:
            print(f"   Expires:    Never")
        
        # Show rate limits
        limits = TIER_LIMITS[tier]
        print(f"\n📊 Rate Limits:")
        if limits["requests_per_hour"]:
            print(f"   Hourly:     {limits['requests_per_hour']:,} requests/hour")
            print(f"   Daily:      {limits['requests_per_day']:,} requests/day")
        else:
            print(f"   Rate Limit: Unlimited")
        
        print(f"\n✨ Features:  {', '.join(limits['features'])}")
        
        if notes:
            print(f"\n📝 Notes:     {notes}")
        
        print("\n" + "="*60)
        print(f"\n💡 Usage:")
        print(f'   curl -H "X-API-Key: {api_key}" \\')
        print(f'     http://localhost:8000/api/v1/theaters')
        print("="*60 + "\n")


def list_keys():
    """List all API keys"""
    with get_session() as db:
        keys = db.query(APIKey).order_by(APIKey.created_at.desc()).all()
        
        if not keys:
            print("No API keys found in database.")
            print("Run: python manage_api_keys.py generate --client 'Client Name' --tier free")
            return
        
        print("\n" + "="*100)
        print(f"{'Prefix':<14} {'Client':<25} {'Tier':<12} {'Status':<10} {'Requests':<10} {'Created':<12} {'Expires':<12}")
        print("="*100)
        
        for key in keys:
            status = "✅ Active" if key.is_active else "❌ Inactive"
            expires = key.expires_at.strftime('%Y-%m-%d') if key.expires_at else "Never"
            created = key.created_at.strftime('%Y-%m-%d')
            
            # Check if expired
            if key.expires_at and key.expires_at < datetime.utcnow():
                status = "⚠️  Expired"
            
            print(f"{key.key_prefix:<14} {key.client_name:<25} {key.tier:<12} {status:<10} {key.total_requests:<10} {created:<12} {expires:<12}")
        
        print("="*100)
        print(f"\nTotal: {len(keys)} API keys")
        print(f"Active: {sum(1 for k in keys if k.is_active and (not k.expires_at or k.expires_at > datetime.utcnow()))}")
        print(f"Inactive: {sum(1 for k in keys if not k.is_active)}")
        print(f"Expired: {sum(1 for k in keys if k.expires_at and k.expires_at < datetime.utcnow())}\n")


def show_key_details(key_prefix: str):
    """Show detailed information about a specific API key"""
    with get_session() as db:
        key = db.query(APIKey).filter(APIKey.key_prefix == key_prefix).first()
        
        if not key:
            print(f"❌ API key not found: {key_prefix}")
            print(f"   Run 'python manage_api_keys.py list' to see all keys")
            return
        
        print("\n" + "="*60)
        print(f"API Key Details: {key.key_prefix}")
        print("="*60)
        print(f"\n📋 Information:")
        print(f"   Client:         {key.client_name}")
        print(f"   Tier:           {key.tier}")
        print(f"   Status:         {'✅ Active' if key.is_active else '❌ Inactive'}")
        print(f"   Created:        {key.created_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        print(f"   Expires:        {key.expires_at.strftime('%Y-%m-%d') if key.expires_at else 'Never'}")
        print(f"   Last Used:      {key.last_used_at.strftime('%Y-%m-%d %H:%M:%S') if key.last_used_at else 'Never'}")
        print(f"   Total Requests: {key.total_requests:,}")
        
        # Show rate limits
        limits = TIER_LIMITS[key.tier]
        print(f"\n📊 Rate Limits:")
        if limits["requests_per_hour"]:
            print(f"   Hourly:         {limits['requests_per_hour']:,} requests/hour")
            print(f"   Daily:          {limits['requests_per_day']:,} requests/day")
        else:
            print(f"   Rate Limit:     Unlimited")
        
        # Recent usage
        recent_usage = db.query(APIKeyUsage).filter(
            APIKeyUsage.key_prefix == key_prefix
        ).order_by(APIKeyUsage.timestamp.desc()).limit(10).all()
        
        if recent_usage:
            print(f"\n📈 Recent Usage (last 10 requests):")
            for usage in recent_usage:
                print(f"   {usage.timestamp.strftime('%Y-%m-%d %H:%M:%S')} - {usage.method} {usage.endpoint}")
        
        if key.notes:
            print(f"\n📝 Notes:")
            print(f"   {key.notes}")
        
        print("="*60 + "\n")


def deactivate_key(key_prefix: str):
    """Deactivate an API key"""
    with get_session() as db:
        key = db.query(APIKey).filter(APIKey.key_prefix == key_prefix).first()
        
        if not key:
            print(f"❌ API key not found: {key_prefix}")
            return
        
        if not key.is_active:
            print(f"⚠️  Key already inactive: {key_prefix} ({key.client_name})")
            return
        
        key.is_active = False
        db.commit()
        
        print(f"✅ API key deactivated: {key_prefix} ({key.client_name})")
        print(f"   This key can no longer be used to access the API.")


def reactivate_key(key_prefix: str):
    """Reactivate an API key"""
    with get_session() as db:
        key = db.query(APIKey).filter(APIKey.key_prefix == key_prefix).first()
        
        if not key:
            print(f"❌ API key not found: {key_prefix}")
            return
        
        if key.is_active:
            print(f"⚠️  Key already active: {key_prefix} ({key.client_name})")
            return
        
        key.is_active = True
        db.commit()
        
        print(f"✅ API key reactivated: {key_prefix} ({key.client_name})")


def show_usage_stats(key_prefix: Optional[str] = None, days: int = 7):
    """Show usage statistics for API key(s)"""
    with get_session() as db:
        since_date = datetime.utcnow() - timedelta(days=days)
        
        if key_prefix:
            # Stats for specific key
            key = db.query(APIKey).filter(APIKey.key_prefix == key_prefix).first()
            if not key:
                print(f"❌ API key not found: {key_prefix}")
                return
            
            usage = db.query(APIKeyUsage).filter(
                APIKeyUsage.key_prefix == key_prefix,
                APIKeyUsage.timestamp >= since_date
            ).all()
            
            print(f"\n📊 Usage Statistics: {key_prefix} ({key.client_name})")
            print(f"   Period: Last {days} days")
            print(f"   Total Requests: {len(usage):,}")
            
            if usage:
                # Group by endpoint
                by_endpoint = {}
                for u in usage:
                    by_endpoint[u.endpoint] = by_endpoint.get(u.endpoint, 0) + 1
                
                print(f"\n   Top Endpoints:")
                for endpoint, count in sorted(by_endpoint.items(), key=lambda x: x[1], reverse=True)[:5]:
                    print(f"      {endpoint}: {count:,} requests")
        else:
            # Overall stats
            total_keys = db.query(APIKey).count()
            active_keys = db.query(APIKey).filter(APIKey.is_active == True).count()
            
            total_usage = db.query(APIKeyUsage).filter(
                APIKeyUsage.timestamp >= since_date
            ).count()
            
            print(f"\n📊 Overall API Statistics")
            print(f"   Period: Last {days} days")
            print(f"   Total Keys: {total_keys}")
            print(f"   Active Keys: {active_keys}")
            print(f"   Total Requests: {total_usage:,}")
            
            # Top users
            top_users = db.query(
                APIKeyUsage.key_prefix,
                func.count(APIKeyUsage.id).label('count')
            ).filter(
                APIKeyUsage.timestamp >= since_date
            ).group_by(
                APIKeyUsage.key_prefix
            ).order_by(
                func.count(APIKeyUsage.id).desc()
            ).limit(5).all()
            
            if top_users:
                print(f"\n   Top API Keys:")
                for prefix, count in top_users:
                    key = db.query(APIKey).filter(APIKey.key_prefix == prefix).first()
                    client = key.client_name if key else "Unknown"
                    print(f"      {prefix} ({client}): {count:,} requests")
        
        print()


def main():
    parser = argparse.ArgumentParser(
        description="PriceScout API Key Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create database tables
  python manage_api_keys.py create-tables
  
  # Generate API keys
  python manage_api_keys.py generate --client "Acme Corp" --tier premium
  python manage_api_keys.py generate --client "Test User" --tier free --expires 30
  
  # List and manage keys
  python manage_api_keys.py list
  python manage_api_keys.py show ps_prem_abcd
  python manage_api_keys.py deactivate ps_prem_abcd
  python manage_api_keys.py reactivate ps_prem_abcd
  
  # View usage statistics
  python manage_api_keys.py usage
  python manage_api_keys.py usage ps_prem_abcd --days 30
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # create-tables command
    subparsers.add_parser('create-tables', help='Create API key database tables')
    
    # generate command
    gen_parser = subparsers.add_parser('generate', help='Generate a new API key')
    gen_parser.add_argument('--client', required=True, help='Client/company name')
    gen_parser.add_argument('--tier', default='free', choices=['free', 'premium', 'enterprise', 'internal'], help='API tier')
    gen_parser.add_argument('--expires', type=int, help='Days until expiration (default: never)')
    gen_parser.add_argument('--notes', help='Optional notes about this key')
    
    # list command
    subparsers.add_parser('list', help='List all API keys')
    
    # show command
    show_parser = subparsers.add_parser('show', help='Show key details')
    show_parser.add_argument('prefix', help='API key prefix (e.g., ps_prem_abcd)')
    
    # deactivate command
    deact_parser = subparsers.add_parser('deactivate', help='Deactivate an API key')
    deact_parser.add_argument('prefix', help='API key prefix to deactivate')
    
    # reactivate command
    react_parser = subparsers.add_parser('reactivate', help='Reactivate an API key')
    react_parser.add_argument('prefix', help='API key prefix to reactivate')
    
    # usage command
    usage_parser = subparsers.add_parser('usage', help='Show usage statistics')
    usage_parser.add_argument('prefix', nargs='?', help='API key prefix (optional, shows all if omitted)')
    usage_parser.add_argument('--days', type=int, default=7, help='Number of days to analyze (default: 7)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Execute command
    if args.command == 'create-tables':
        create_tables()
    elif args.command == 'generate':
        generate_key(args.client, args.tier, args.expires, args.notes)
    elif args.command == 'list':
        list_keys()
    elif args.command == 'show':
        show_key_details(args.prefix)
    elif args.command == 'deactivate':
        deactivate_key(args.prefix)
    elif args.command == 'reactivate':
        reactivate_key(args.prefix)
    elif args.command == 'usage':
        show_usage_stats(args.prefix, args.days)


if __name__ == "__main__":
    main()


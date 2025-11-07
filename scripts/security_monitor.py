#!/usr/bin/env python3
"""
Security Event Monitor for Price Scout
Analyzes security event logs and alerts on suspicious patterns.

Usage:
    python scripts/security_monitor.py [--days N] [--alert]
    
Options:
    --days N    Analyze events from the last N days (default: 7)
    --alert     Send alerts for critical security events
"""

import os
import json
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Configuration
SECURITY_LOG_FILE = "security_events.log"
ALERT_THRESHOLD_FAILED_LOGINS = 10  # Alert if any user has 10+ failed logins
ALERT_THRESHOLD_FILE_REJECTIONS = 5  # Alert if 5+ files rejected
ALERT_THRESHOLD_UNIQUE_IPS = 3  # Alert if same user from 3+ IPs (if IP tracking added)


class SecurityMonitor:
    def __init__(self, log_file: str = SECURITY_LOG_FILE):
        self.log_file = log_file
        self.events = []
        
    def load_events(self, days: int = 7):
        """Load security events from the last N days."""
        if not os.path.exists(self.log_file):
            print(f"⚠️  Log file not found: {self.log_file}")
            print(f"📝 Events will be logged to this file once security features are used.")
            return
        
        cutoff_date = datetime.now() - timedelta(days=days)
        
        with open(self.log_file, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    event = json.loads(line.strip())
                    event_time = datetime.fromisoformat(event['timestamp'])
                    
                    if event_time >= cutoff_date:
                        self.events.append(event)
                except (json.JSONDecodeError, KeyError, ValueError) as e:
                    print(f"⚠️  Skipped malformed log entry: {e}")
                    continue
        
        print(f"📊 Loaded {len(self.events)} events from the last {days} days\n")
    
    def analyze_failed_logins(self):
        """Analyze failed login attempts."""
        failed_logins = defaultdict(list)
        
        for event in self.events:
            if event.get('event_type') == 'failed_login':
                username = event.get('username', 'unknown')
                failed_logins[username].append(event['timestamp'])
        
        print("🔐 Failed Login Analysis")
        print("=" * 60)
        
        if not failed_logins:
            print("✅ No failed login attempts detected\n")
            return []
        
        alerts = []
        for username, timestamps in sorted(failed_logins.items(), 
                                          key=lambda x: len(x[1]), 
                                          reverse=True):
            count = len(timestamps)
            status = "🔴 ALERT" if count >= ALERT_THRESHOLD_FAILED_LOGINS else "⚠️  WARNING" if count >= 5 else "ℹ️  INFO"
            
            print(f"{status} - User '{username}': {count} failed attempts")
            
            if count >= ALERT_THRESHOLD_FAILED_LOGINS:
                alerts.append({
                    'type': 'excessive_failed_logins',
                    'username': username,
                    'count': count,
                    'severity': 'high'
                })
        
        print()
        return alerts
    
    def analyze_lockouts(self):
        """Analyze account lockouts."""
        lockouts = defaultdict(int)
        
        for event in self.events:
            if event.get('event_type') == 'account_locked':
                username = event.get('username', 'unknown')
                lockouts[username] += 1
        
        print("🔒 Account Lockout Analysis")
        print("=" * 60)
        
        if not lockouts:
            print("✅ No account lockouts detected\n")
            return []
        
        alerts = []
        for username, count in sorted(lockouts.items(), key=lambda x: x[1], reverse=True):
            print(f"⚠️  User '{username}': {count} lockout(s)")
            
            if count >= 3:
                alerts.append({
                    'type': 'repeated_lockouts',
                    'username': username,
                    'count': count,
                    'severity': 'medium'
                })
        
        print()
        return alerts
    
    def analyze_file_uploads(self):
        """Analyze file upload activity."""
        rejected_uploads = []
        accepted_uploads = []
        
        for event in self.events:
            if event.get('event_type') == 'file_upload_rejected':
                rejected_uploads.append(event)
            elif event.get('event_type') == 'file_upload_accepted':
                accepted_uploads.append(event)
        
        print("📁 File Upload Analysis")
        print("=" * 60)
        print(f"✅ Accepted uploads: {len(accepted_uploads)}")
        print(f"❌ Rejected uploads: {len(rejected_uploads)}")
        
        if rejected_uploads:
            print("\n🔍 Rejection Reasons:")
            rejection_reasons = defaultdict(int)
            rejection_by_user = defaultdict(int)
            
            for event in rejected_uploads:
                reason = event.get('details', {}).get('reason', 'unknown')
                username = event.get('username', 'unknown')
                rejection_reasons[reason] += 1
                rejection_by_user[username] += 1
            
            for reason, count in sorted(rejection_reasons.items(), 
                                       key=lambda x: x[1], 
                                       reverse=True):
                print(f"   • {reason}: {count} time(s)")
            
            print("\n👤 Rejections by User:")
            for username, count in sorted(rejection_by_user.items(), 
                                         key=lambda x: x[1], 
                                         reverse=True):
                print(f"   • {username}: {count} rejection(s)")
        
        print()
        
        alerts = []
        if len(rejected_uploads) >= ALERT_THRESHOLD_FILE_REJECTIONS:
            alerts.append({
                'type': 'excessive_file_rejections',
                'count': len(rejected_uploads),
                'severity': 'medium'
            })
        
        return alerts
    
    def analyze_session_activity(self):
        """Analyze session-related events."""
        session_timeouts = 0
        password_changes = 0
        
        for event in self.events:
            if event.get('event_type') == 'session_timeout':
                session_timeouts += 1
            elif event.get('event_type') == 'password_changed':
                password_changes += 1
        
        print("🕐 Session & Account Activity")
        print("=" * 60)
        print(f"⏱️  Session timeouts: {session_timeouts}")
        print(f"🔑 Password changes: {password_changes}")
        print()
        
        return []
    
    def generate_summary(self):
        """Generate overall security summary."""
        print("=" * 60)
        print("📋 SECURITY SUMMARY")
        print("=" * 60)
        
        event_types = defaultdict(int)
        for event in self.events:
            event_types[event.get('event_type', 'unknown')] += 1
        
        print(f"Total events: {len(self.events)}")
        print("\nEvent breakdown:")
        for event_type, count in sorted(event_types.items(), 
                                       key=lambda x: x[1], 
                                       reverse=True):
            print(f"   • {event_type}: {count}")
        print()
    
    def run_analysis(self, days: int = 7):
        """Run full security analysis."""
        print("\n" + "=" * 60)
        print("🛡️  PRICE SCOUT SECURITY MONITOR")
        print("=" * 60)
        print(f"Analysis Period: Last {days} days")
        print(f"Log File: {self.log_file}")
        print("=" * 60 + "\n")
        
        self.load_events(days)
        
        all_alerts = []
        all_alerts.extend(self.analyze_failed_logins())
        all_alerts.extend(self.analyze_lockouts())
        all_alerts.extend(self.analyze_file_uploads())
        all_alerts.extend(self.analyze_session_activity())
        
        self.generate_summary()
        
        return all_alerts
    
    def send_alerts(self, alerts):
        """Send alerts for critical security events."""
        if not alerts:
            print("✅ No security alerts to send\n")
            return
        
        print("🚨 SECURITY ALERTS")
        print("=" * 60)
        
        high_priority = [a for a in alerts if a.get('severity') == 'high']
        medium_priority = [a for a in alerts if a.get('severity') == 'medium']
        
        if high_priority:
            print("\n🔴 HIGH PRIORITY ALERTS:")
            for alert in high_priority:
                if alert['type'] == 'excessive_failed_logins':
                    print(f"   • User '{alert['username']}' has {alert['count']} failed login attempts")
                    print(f"     → ACTION: Review account activity, consider temporary suspension")
        
        if medium_priority:
            print("\n🟡 MEDIUM PRIORITY ALERTS:")
            for alert in medium_priority:
                if alert['type'] == 'repeated_lockouts':
                    print(f"   • User '{alert['username']}' locked out {alert['count']} times")
                    print(f"     → ACTION: Contact user to verify legitimate access attempts")
                elif alert['type'] == 'excessive_file_rejections':
                    print(f"   • {alert['count']} file uploads rejected")
                    print(f"     → ACTION: Review file upload patterns for potential attacks")
        
        print("\n📧 In a production environment, these alerts would be:")
        print("   • Sent via email to security team")
        print("   • Logged to security monitoring dashboard")
        print("   • Forwarded to incident response system")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Security Event Monitor for Price Scout',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/security_monitor.py                    # Analyze last 7 days
  python scripts/security_monitor.py --days 30          # Analyze last 30 days
  python scripts/security_monitor.py --days 1 --alert   # Daily analysis with alerts
        """
    )
    parser.add_argument('--days', type=int, default=7,
                       help='Number of days to analyze (default: 7)')
    parser.add_argument('--alert', action='store_true',
                       help='Send alerts for critical security events')
    
    args = parser.parse_args()
    
    monitor = SecurityMonitor()
    alerts = monitor.run_analysis(days=args.days)
    
    if args.alert:
        monitor.send_alerts(alerts)
    
    print("✅ Analysis complete!\n")


if __name__ == "__main__":
    main()

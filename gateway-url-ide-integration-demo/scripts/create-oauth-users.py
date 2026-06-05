#!/usr/bin/env python3
"""
Create two test Cognito users with different team claims for the RBAC demo.
  alice@example.com → team: Engineering (gets products + orders)
  bob@example.com   → team: Support     (gets customers + jira)
"""
import argparse
import boto3
import sys

USERS = [
    {"email": "alice@example.com", "team": "Engineering"},
    {"email": "bob@example.com",   "team": "Support"},
]
PASSWORD = "DemoPass123!"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--region', required=True)
    parser.add_argument('--pool-id', required=True)
    args = parser.parse_args()

    client = boto3.client('cognito-idp', region_name=args.region)

    for user in USERS:
        email = user['email']
        team = user['team']
        try:
            client.admin_create_user(
                UserPoolId=args.pool_id,
                Username=email,
                UserAttributes=[
                    {'Name': 'email', 'Value': email},
                    {'Name': 'email_verified', 'Value': 'true'},
                    {'Name': 'custom:team', 'Value': team},
                ],
                MessageAction='SUPPRESS'  # Don't send welcome email
            )
            # Set permanent password (skip force-change)
            client.admin_set_user_password(
                UserPoolId=args.pool_id,
                Username=email,
                Password=PASSWORD,
                Permanent=True
            )
            print(f"  ✅ Created: {email} (team: {team})")
        except client.exceptions.UsernameExistsException:
            # Update team attribute if user already exists
            client.admin_update_user_attributes(
                UserPoolId=args.pool_id,
                Username=email,
                UserAttributes=[{'Name': 'custom:team', 'Value': team}]
            )
            print(f"  ⏭️  Exists (updated team): {email} (team: {team})")
        except Exception as e:
            print(f"  ⚠️  {email}: {e}", file=sys.stderr)

    print(f"\n  Credentials for both: password = {PASSWORD}")
    print(f"  alice → Engineering: products + orders")
    print(f"  bob   → Support: customers + jira")


if __name__ == '__main__':
    main()

"""Test bulk user import"""
from app import users
import json

with open('example_users.json') as f:
    data = json.load(f)

success, errors = users.bulk_import_users(data)
print(f'Imported {success} users')
if errors:
    print(f'Errors: {errors}')
else:
    print('No errors!')

# Show all users
print('\nAll users:')
all_users = users.get_all_users()
for user in all_users:
    role = user['role'] if 'role' in user.keys() else 'unknown'
    modes = users.get_user_allowed_modes(user['username'])
    print(f"  {user['username']} ({role}): {len(modes)} modes")

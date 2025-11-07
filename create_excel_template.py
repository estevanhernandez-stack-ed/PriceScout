#!/usr/bin/env python3
"""
Script to create the Excel template for bulk user upload
"""
import xlsxwriter

# Create workbook
workbook = xlsxwriter.Workbook('bulk_user_upload_template.xlsx')
worksheet = workbook.add_worksheet('Users')

# Define formats
header_format = workbook.add_format({
    'bold': True,
    'bg_color': '#4472C4',
    'font_color': 'white',
    'border': 1
})

example_format = workbook.add_format({
    'bg_color': '#E7E6E6',
    'border': 1
})

# Set column widths
worksheet.set_column('A:A', 15)  # username
worksheet.set_column('B:B', 20)  # password
worksheet.set_column('C:C', 12)  # role
worksheet.set_column('D:D', 18)  # company
worksheet.set_column('E:E', 18)  # default_company
worksheet.set_column('F:F', 20)  # home_location_type
worksheet.set_column('G:G', 40)  # home_location_value

# Headers
headers = [
    'username',
    'password',
    'role',
    'company',
    'default_company',
    'home_location_type',
    'home_location_value'
]

for col, header in enumerate(headers):
    worksheet.write(0, col, header, header_format)

# Example data
examples = [
    ['jsmith', 'SecurePass123!', 'manager', 'AMC', 'AMC', 'market', 'Dallas > Dallas Metro'],
    ['bdoe', 'AnotherPass456!', 'user', 'Marcus', 'Marcus', 'theater', 'Milwaukee > Milwaukee Metro > Marcus Cinema'],
    ['admin2', 'AdminPass789!', 'admin', '', '', 'none', ''],
    ['testuser', 'TestPass999!', 'user', 'AMC', 'AMC', 'director', 'Dallas'],
]

for row, data in enumerate(examples, start=1):
    for col, value in enumerate(data):
        worksheet.write(row, col, value, example_format)

# Add instructions sheet
instructions = workbook.add_worksheet('Instructions')
instructions.set_column('A:A', 80)

instructions_text = [
    'BULK USER UPLOAD TEMPLATE - INSTRUCTIONS',
    '',
    'HOW TO USE:',
    '1. Switch to the "Users" tab',
    '2. Delete the example rows (rows 2-5)',
    '3. Add your user data starting from row 2',
    '4. Save the file',
    '5. Upload via Admin > Bulk Import Users',
    '',
    'COLUMN DESCRIPTIONS:',
    '',
    'username (REQUIRED)',
    '  - Must be unique',
    '  - No spaces recommended',
    '  - Example: jsmith, user123, admin',
    '',
    'password (REQUIRED)',
    '  - Minimum 8 characters',
    '  - Must contain: uppercase, lowercase, number, special character',
    '  - Example: SecurePass123!',
    '',
    'role (REQUIRED)',
    '  - Valid values: admin, manager, user',
    '  - Case insensitive',
    '  - Determines access level',
    '',
    'company (OPTIONAL)',
    '  - Must match existing company in database',
    '  - Leave blank for admin users',
    '  - Example: AMC, Marcus, Marcus Theatres',
    '',
    'default_company (OPTIONAL)',
    '  - Company to show on login',
    '  - Usually same as company',
    '  - Example: AMC, Marcus',
    '',
    'home_location_type (OPTIONAL)',
    '  - Valid values: none, director, market, theater',
    '  - Sets default filter for user',
    '  - Leave blank or use "none" for no filter',
    '',
    'home_location_value (OPTIONAL)',
    '  - Location path based on type',
    '  - Director: "Dallas"',
    '  - Market: "Dallas > Dallas Metro"',
    '  - Theater: "Dallas > Dallas Metro > AMC NorthPark"',
    '  - Leave blank if type is "none"',
    '',
    'TIPS:',
    '- Required columns must have values',
    '- Delete example data before uploading',
    '- Test with 1-2 users first',
    '- Company names are case-sensitive',
    '- See BULK_USER_UPLOAD_GUIDE.md for full documentation',
]

for row, text in enumerate(instructions_text):
    if text.startswith('BULK USER') or text.startswith('HOW TO') or text.startswith('COLUMN') or text.startswith('TIPS'):
        fmt = workbook.add_format({'bold': True, 'font_size': 12})
        instructions.write(row, 0, text, fmt)
    else:
        instructions.write(row, 0, text)

workbook.close()
print("[OK] Excel template created: bulk_user_upload_template.xlsx")

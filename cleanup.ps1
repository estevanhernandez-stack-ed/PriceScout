# Price Scout - Cleanup Script for Pre-Deployment
# Run this script to remove test artifacts and redundant files

Write-Host "🧹 Price Scout - Pre-Deployment Cleanup" -ForegroundColor Cyan
Write-Host "=========================================" -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Create archive directory
Write-Host "📁 Creating archive directory..." -ForegroundColor Yellow
New-Item -ItemType Directory -Force -Path "archive" | Out-Null
New-Item -ItemType Directory -Force -Path "scripts" | Out-Null
New-Item -ItemType Directory -Force -Path "tests\manual_tests" | Out-Null

# Archive documentation files
Write-Host "📚 Archiving old documentation..." -ForegroundColor Yellow
$docsToArchive = @(
    "AIplan.bak",
    "Gemini.md",
    "testfix_10_25.md",
    "test_failure_report.md",
    "omdb_plan.md",
    "app\Scout_Review.md"
)

foreach ($doc in $docsToArchive) {
    if (Test-Path $doc) {
        Move-Item -Path $doc -Destination "archive\" -Force
        Write-Host "  ✓ Archived: $doc" -ForegroundColor Green
    }
}

# Move utility scripts
Write-Host "🔧 Moving utility scripts..." -ForegroundColor Yellow
$scriptsToMove = @(
    @{Source = "create_themes_file.py"; Dest = "scripts\"},
    @{Source = "fix_json.py"; Dest = "scripts\"},
    @{Source = "test_bom_scraper.py"; Dest = "tests\manual_tests\"}
)

foreach ($script in $scriptsToMove) {
    if (Test-Path $script.Source) {
        Move-Item -Path $script.Source -Destination $script.Dest -Force
        Write-Host "  ✓ Moved: $($script.Source) → $($script.Dest)" -ForegroundColor Green
    }
}

# Delete temporary/test files
Write-Host "🗑️  Deleting temporary and test files..." -ForegroundColor Yellow
$filesToDelete = @(
    "2025-10-01T21-51_export.csv",
    "2025-10-01T22-35_export.csv",
    "dummy_runtime_log.csv",
    "error.txt",
    "cache_data.json",
    "updated_markets.json",
    "fix_test_users.py"
)

foreach ($file in $filesToDelete) {
    if (Test-Path $file) {
        Remove-Item -Path $file -Force
        Write-Host "  ✓ Deleted: $file" -ForegroundColor Green
    }
}

# Delete backup files
Write-Host "🗑️  Deleting backup files..." -ForegroundColor Yellow
$backupPatterns = @(
    "app\theater_cache*.bak*",
    "app\*.rebuild_bak"
)

foreach ($pattern in $backupPatterns) {
    Get-ChildItem -Path $pattern -ErrorAction SilentlyContinue | ForEach-Object {
        Remove-Item -Path $_.FullName -Force
        Write-Host "  ✓ Deleted: $($_.Name)" -ForegroundColor Green
    }
}

# Delete test directories
Write-Host "🗑️  Deleting test directories..." -ForegroundColor Yellow
$dirsToDelete = @(
    "dummy_reports_dir",
    "data\MagicMock",
    "tmp"
)

foreach ($dir in $dirsToDelete) {
    if (Test-Path $dir) {
        Remove-Item -Path $dir -Recurse -Force
        Write-Host "  ✓ Deleted directory: $dir" -ForegroundColor Green
    }
}

# Clean __pycache__ directories
Write-Host "🗑️  Cleaning Python cache files..." -ForegroundColor Yellow
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | ForEach-Object {
    Remove-Item -Path $_.FullName -Recurse -Force
    Write-Host "  ✓ Deleted: $($_.FullName)" -ForegroundColor Green
}

# Clean .pyc files
Get-ChildItem -Path . -Recurse -Filter "*.pyc" | ForEach-Object {
    Remove-Item -Path $_.FullName -Force
}

# Clean pytest cache
if (Test-Path ".pytest_cache") {
    Remove-Item -Path ".pytest_cache" -Recurse -Force
    Write-Host "  ✓ Deleted: .pytest_cache" -ForegroundColor Green
}

# Summary
Write-Host ""
Write-Host "✅ Cleanup Complete!" -ForegroundColor Green
Write-Host ""
Write-Host "📊 Summary:" -ForegroundColor Cyan
Write-Host "  - Archived: $($(Get-ChildItem 'archive' -ErrorAction SilentlyContinue).Count) files"
Write-Host "  - Moved to scripts: $($(Get-ChildItem 'scripts' -ErrorAction SilentlyContinue).Count) files"
Write-Host ""
Write-Host "📝 Next Steps:" -ForegroundColor Yellow
Write-Host "  1. Review CODE_REVIEW_2025.md for remaining issues"
Write-Host "  2. Create .env file from .env.example"
Write-Host "  3. Run: pytest --cov=app --cov-report=html"
Write-Host "  4. Review README.md deployment checklist"
Write-Host ""
Write-Host "⚠️  Remember to:" -ForegroundColor Red
Write-Host "  - Change default admin password (admin/admin)"
Write-Host "  - Configure .env with your API keys"
Write-Host "  - Test in staging before production"
Write-Host ""

# Pause to see results
Read-Host "Press Enter to exit"

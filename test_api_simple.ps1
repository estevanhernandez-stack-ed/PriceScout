# Quick API Test - Manual Steps
# 1. Start server in separate terminal: uvicorn api.main:app --reload --port 8080
# 2. Run this script: .\test_api_simple.ps1

Write-Host "Testing API endpoints (assumes server is running on port 8080)..." -ForegroundColor Cyan

try {
    # Test 1: Health Check
    Write-Host "`n=== Test 1: Health Check ===" -ForegroundColor Green
    $health = Invoke-RestMethod -Uri "http://localhost:8080/healthz" -Method Get
    Write-Host "✓ Health check passed: $($health | ConvertTo-Json)" -ForegroundColor Green

    # Test 2: Selection Analysis (JSON)
    Write-Host "`n=== Test 2: Selection Analysis (JSON) ===" -ForegroundColor Green
    $jsonBody = @'
{
  "selected_showtimes": {
    "2025-11-30": {
      "Marcus Ridge Cinema": {
        "Wicked": {
          "7:00PM": [{"format": "IMAX", "daypart": "Prime"}],
          "9:30PM": [{"format": "Standard", "daypart": "Prime"}]
        },
        "Gladiator II": {
          "8:00PM": [{"format": "Dolby Cinema", "daypart": "Prime"}]
        }
      }
    }
  }
}
'@
    
    $result = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/reports/selection-analysis?format=json" `
        -Method Post `
        -ContentType "application/json" `
        -Body $jsonBody
    
    Write-Host "✓ Rows returned: $($result.rows.Count)" -ForegroundColor Green
    if ($result.rows.Count -gt 0) {
        Write-Host "  Sample: Date=$($result.rows[0].Date), Theater=$($result.rows[0].'Theater Name')"
    }

    # Test 3: Selection Analysis (CSV)
    Write-Host "`n=== Test 3: Selection Analysis (CSV) ===" -ForegroundColor Green
    $csvResult = Invoke-WebRequest -Uri "http://localhost:8080/api/v1/reports/selection-analysis?format=csv" `
        -Method Post `
        -ContentType "application/json" `
        -Body $jsonBody
    
    Write-Host "✓ CSV received ($($csvResult.Content.Length) bytes)" -ForegroundColor Green
    Write-Host "  First line: $(($csvResult.Content -split "`n")[0])"

    # Test 4: Showtime View HTML
    Write-Host "`n=== Test 4: Showtime View (HTML) ===" -ForegroundColor Green
    $htmlBody = @'
{
  "all_showings": {
    "2025-11-30": {
      "Marcus Ridge Cinema": [
        {"film_title": "Wicked", "showtime": "7:00PM", "format": "IMAX"},
        {"film_title": "Wicked", "showtime": "9:30PM", "format": "Standard"},
        {"film_title": "Gladiator II", "showtime": "8:00PM", "format": "Dolby Cinema"}
      ]
    }
  },
  "selected_films": ["Wicked", "Gladiator II"],
  "theaters": [{"name": "Marcus Ridge Cinema"}],
  "date_start": "2025-11-30",
  "date_end": "2025-11-30",
  "context_title": "Test Market"
}
'@

    $htmlResult = Invoke-WebRequest -Uri "http://localhost:8080/api/v1/reports/showtime-view/html" `
        -Method Post `
        -ContentType "application/json" `
        -Body $htmlBody
    
    $hasTitle = $htmlResult.Content -like '*Test Market*'
    $hasWicked = $htmlResult.Content -like '*Wicked*'
    
    Write-Host "✓ HTML received ($($htmlResult.Content.Length) bytes)" -ForegroundColor Green
    Write-Host "  Contains 'Test Market': $hasTitle"
    Write-Host "  Contains 'Wicked': $hasWicked"

    Write-Host "`n=== ✓ All Tests Passed! ===" -ForegroundColor Green

} catch {
    Write-Host "`n✗ Error: $_" -ForegroundColor Red
    Write-Host "Make sure the server is running: uvicorn api.main:app --reload --port 8080" -ForegroundColor Yellow
}

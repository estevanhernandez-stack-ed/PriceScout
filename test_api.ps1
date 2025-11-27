# Test FastAPI endpoints
# Run: .\test_api.ps1

Write-Host "Starting FastAPI server..." -ForegroundColor Cyan
$serverJob = Start-Job -ScriptBlock {
    Set-Location 'C:\Users\estev\Desktop\Price Scout'
    & .\.venv\Scripts\python.exe -m uvicorn api.main:app --port 8080
}

Write-Host "Waiting for server startup (8 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 8

try {
    # Test 1: Health Check
    Write-Host "`n=== Test 1: Health Check ===" -ForegroundColor Green
    $health = Invoke-RestMethod -Uri "http://localhost:8080/healthz" -Method Get
    Write-Host "Response: $($health | ConvertTo-Json)"

    # Test 2: Selection Analysis (JSON format)
    Write-Host "`n=== Test 2: Selection Analysis (JSON) ===" -ForegroundColor Green
    $payload = @{
        selected_showtimes = @{
            "2025-11-30" = @{
                "Marcus Ridge Cinema" = @{
                    "Wicked" = @{
                        "7:00PM" = @(
                            @{ format = "IMAX"; daypart = "Prime"; ticket_url = "https://example.com" }
                        )
                        "9:30PM" = @(
                            @{ format = "Standard"; daypart = "Prime"; ticket_url = "https://example.com" }
                        )
                    }
                    "Gladiator II" = @{
                        "8:00PM" = @(
                            @{ format = "Dolby Cinema"; daypart = "Prime"; ticket_url = "https://example.com" }
                        )
                    }
                }
            }
        }
    }
    
    $jsonPayload = $payload | ConvertTo-Json -Depth 10
    $result = Invoke-RestMethod -Uri "http://localhost:8080/api/v1/reports/selection-analysis?format=json" `
        -Method Post `
        -ContentType "application/json" `
        -Body $jsonPayload
    
    Write-Host "Response rows count: $($result.rows.Count)"
    Write-Host "Sample row: $($result.rows[0] | ConvertTo-Json)"

    # Test 3: Selection Analysis (CSV format)
    Write-Host "`n=== Test 3: Selection Analysis (CSV) ===" -ForegroundColor Green
    $csvResult = Invoke-WebRequest -Uri "http://localhost:8080/api/v1/reports/selection-analysis?format=csv" `
        -Method Post `
        -ContentType "application/json" `
        -Body $jsonPayload
    
    Write-Host "CSV Content (first 500 chars):"
    Write-Host ($csvResult.Content.Substring(0, [Math]::Min(500, $csvResult.Content.Length)))

    # Test 4: Showtime View HTML
    Write-Host "`n=== Test 4: Showtime View (HTML) ===" -ForegroundColor Green
    $htmlPayload = @{
        all_showings = @{
            "2025-11-30" = @{
                "Marcus Ridge Cinema" = @(
                    @{ film_title = "Wicked"; showtime = "7:00PM"; format = "IMAX"; daypart = "Prime" }
                    @{ film_title = "Wicked"; showtime = "9:30PM"; format = "Standard"; daypart = "Prime" }
                    @{ film_title = "Gladiator II"; showtime = "8:00PM"; format = "Dolby Cinema"; daypart = "Prime" }
                )
            }
        }
        selected_films = @("Wicked", "Gladiator II")
        theaters = @(
            @{ name = "Marcus Ridge Cinema" }
        )
        date_start = "2025-11-30"
        date_end = "2025-11-30"
        context_title = "Test Market"
    } | ConvertTo-Json -Depth 10

    $htmlResult = Invoke-WebRequest -Uri "http://localhost:8080/api/v1/reports/showtime-view/html" `
        -Method Post `
        -ContentType "application/json" `
        -Body $htmlPayload
    
    Write-Host "HTML size: $($htmlResult.Content.Length) bytes"
    Write-Host "Contains expected title: $(($htmlResult.Content -like '*Test Market*'))"

    Write-Host "`n=== All Tests Passed! ===" -ForegroundColor Green

} catch {
    Write-Host "`nError: $_" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
} finally {
    Write-Host "`nStopping server..." -ForegroundColor Cyan
    Stop-Job -Job $serverJob
    Remove-Job -Job $serverJob
    Write-Host "Done." -ForegroundColor Cyan
}

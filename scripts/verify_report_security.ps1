param(
    [string]$BaseUrl = "http://127.0.0.1:8000"
)

$ErrorActionPreference = "Stop"

function Get-StaffJwt {
    param(
        [string]$Email,
        [string]$Password
    )

    $body = @{
        email = $Email
        password = $Password
    } | ConvertTo-Json

    $response = Invoke-RestMethod `
        -Method Post `
        -Uri "$BaseUrl/api/auth/login" `
        -ContentType "application/json" `
        -Body $body

    return $response.session_token
}

function Get-EndpointStatus {
    param(
        [string]$Url,
        [string]$Token
    )

    try {
        $response = Invoke-WebRequest `
            -Method Get `
            -Uri $Url `
            -Headers @{ Authorization = "Bearer $Token" } `
            -MaximumRedirection 0 `
            -UseBasicParsing
        return [int]$response.StatusCode
    }
    catch {
        if ($null -ne $_.Exception.Response) {
            return [int]$_.Exception.Response.StatusCode
        }
        throw
    }
}

$accounts = @(
    @{
        Role = "admin"
        Email = "admin@clinic.com"
        Password = "admin123"
        Expected = 200
    },
    @{
        Role = "doctor"
        Email = "alan.chua@clinic.com"
        Password = "alan123"
        Expected = 403
    },
    @{
        Role = "receptionist"
        Email = "amy.wong@clinic.com"
        Password = "amy123"
        Expected = 403
    }
)

$endpoints = @(
    "/reports",
    "/api/reports/appointments/daily",
    "/api/reports/appointments/daily/export.pdf",
    "/api/reports/patients/registrations/monthly?year=2025",
    "/api/reports/patients/registrations/monthly/export.pdf?year=2025"
)

$results = foreach ($account in $accounts) {
    $token = Get-StaffJwt `
        -Email $account.Email `
        -Password $account.Password

    foreach ($endpoint in $endpoints) {
        $actual = Get-EndpointStatus `
            -Url "$BaseUrl$endpoint" `
            -Token $token
        [PSCustomObject]@{
            Role = $account.Role
            Endpoint = $endpoint
            Expected = $account.Expected
            Actual = $actual
            Result = if ($actual -eq $account.Expected) { "PASS" } else { "FAIL" }
        }
    }
}

$results | Format-Table -AutoSize

if ($results.Result -contains "FAIL") {
    Write-Error "US-46 verification failed."
    exit 1
}

Write-Host "US-46 verified: admin JWTs succeed and non-admin JWTs receive 403."

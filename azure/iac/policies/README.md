# Azure API Management Policy Configuration

This directory contains XML policy files for Azure API Management (APIM).

## Policy Files

### 1. `api-policy.xml`
**Scope:** All API operations (except explicitly overridden)

**Features:**
- **CORS**: Configured for Azure App Service and local development origins
- **Rate Limiting**: 100 calls/minute per subscription
- **Quota**: 10,000 calls/week per subscription
- **JWT Validation**: Validates Bearer tokens for protected endpoints
  - Public endpoints (auth, docs, healthz) are exempted
  - Uses Microsoft Entra ID for token validation
- **Security Headers**: X-Content-Type-Options, X-Frame-Options, X-XSS-Protection
- **Error Handling**: Returns JSON error responses

### 2. `public-endpoints-policy.xml`
**Scope:** Public endpoints (/docs, /openapi.json, /healthz)

**Features:**
- **CORS**: Permissive configuration for documentation access
- **Rate Limiting**: 200 calls/minute (more permissive)
- **Caching**: 1-hour cache for documentation endpoints
- **Security Headers**: Basic security hardening

## Configuration Variables

Before deploying these policies, replace the following placeholders:

- `{{TENANT_ID}}`: Your Microsoft Entra ID tenant ID
- `{{CLIENT_ID}}`: Your application's client ID (app registration)

## Deployment

### Option 1: Azure Portal
1. Navigate to your API Management instance
2. Go to "APIs" → Select your API
3. Click "All operations" or specific operation
4. Click "Policy code editor" in the Inbound/Outbound/On-error section
5. Paste the policy XML

### Option 2: Azure CLI

```powershell
# Set policy at API level
az apim api policy create `
    --resource-group <resource-group> `
    --service-name <apim-service-name> `
    --api-id price-scout-api `
    --xml-policy "@policies/api-policy.xml"

# Set policy for specific operation
az apim api operation policy create `
    --resource-group <resource-group> `
    --service-name <apim-service-name> `
    --api-id price-scout-api `
    --operation-id get-docs `
    --xml-policy "@policies/public-endpoints-policy.xml"
```

### Option 3: Bicep/ARM Template

Update `apim.bicep` to include policy references:

```bicep
resource apiPolicy 'Microsoft.ApiManagement/service/apis/policies@2021-08-01' = {
  name: 'policy'
  parent: api
  properties: {
    value: loadTextContent('policies/api-policy.xml')
    format: 'xml'
  }
}
```

## Testing

After deployment, test the policies:

```powershell
# Test rate limiting
for ($i=1; $i -le 105; $i++) {
    Invoke-RestMethod -Uri "https://<apim-gateway>/api/v1/healthz" -Method Get
}
# Should receive HTTP 429 after 100 requests

# Test JWT validation
Invoke-RestMethod -Uri "https://<apim-gateway>/api/v1/markets" -Method Get
# Should receive HTTP 401 without valid token

# Test with token
$token = "your-jwt-token"
Invoke-RestMethod -Uri "https://<apim-gateway>/api/v1/markets" `
    -Method Get `
    -Headers @{ Authorization = "Bearer $token" }
# Should succeed with valid token
```

## Customization

### Adjust Rate Limits

Modify the `<rate-limit>` values:
- `calls`: Number of allowed calls
- `renewal-period`: Time window in seconds

### Add IP Whitelisting

Add inside `<inbound>` section:

```xml
<ip-filter action="allow">
    <address>13.66.xxx.xxx</address>
    <address-range from="13.66.xxx.xxx" to="13.66.xxx.xxx" />
</ip-filter>
```

### Enable Request Logging

Add inside `<inbound>` section:

```xml
<log-to-eventhub logger-id="my-logger" partition-id="0">
    @{
        return new JObject(
            new JProperty("request-id", context.RequestId),
            new JProperty("method", context.Request.Method),
            new JProperty("url", context.Request.Url.ToString())
        ).ToString();
    }
</log-to-eventhub>
```

## References

- [APIM Policy Reference](https://learn.microsoft.com/en-us/azure/api-management/api-management-policies)
- [APIM Policy Expressions](https://learn.microsoft.com/en-us/azure/api-management/api-management-policy-expressions)
- [JWT Validation Policy](https://learn.microsoft.com/en-us/azure/api-management/validate-jwt-policy)

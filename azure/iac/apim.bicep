param location string
param apimServiceName string
param appServiceName string
param publisherEmail string = 'admin@pricescout.example.com'
param publisherName string = 'PriceScout'

resource apimService 'Microsoft.ApiManagement/service@2021-08-01' = {
  name: apimServiceName
  location: location
  sku: {
    name: 'Consumption'
    capacity: 0
  }
  properties: {
    publisherEmail: publisherEmail
    publisherName: publisherName
  }
}

resource api 'Microsoft.ApiManagement/service/apis@2021-08-01' = {
  name: 'price-scout-api'
  parent: apimService
  properties: {
    displayName: 'PriceScout API'
    path: 'api'
    protocols: [
      'https'
    ]
    format: 'openapi-link'
    value: 'https://${appServiceName}.azurewebsites.net/api/v1/openapi.json'
    subscriptionRequired: false
  }
}

// Note: Policies are deployed separately using deploy-apim-policies.ps1
// This is because Bicep does not support loadTextContent() with external files in all scenarios
// and policy content with variables requires runtime substitution

output apimGatewayUrl string = apimService.properties.gatewayUrl
output apimServiceId string = apimService.id

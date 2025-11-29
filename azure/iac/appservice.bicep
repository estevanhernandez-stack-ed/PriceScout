param location string
param appServiceName string
param appServicePlanId string

resource appService 'Microsoft.Web/sites@2022-03-01' = {
  name: appServiceName
  location: location
  properties: {
    serverFarmId: appServicePlanId
    httpsOnly: true
  }
  identity: {
    type: 'SystemAssigned'
  }
}

output principalId string = appService.identity.principalId

param location string = resourceGroup().location
param appServicePlanName string = 'price-scout-plan'
param appServiceName string = 'price-scout-app'
param sqlServerName string = 'pricescout-sql'
param sqlDatabaseName string = 'pricescout'
@secure()
param sqlAdminPassword string
param keyVaultName string = 'price-scout-kv'
param apimServiceName string = 'price-scout-apim'
param serviceBusNamespaceName string = 'price-scout-sb'

// Other modules defined below

module serviceBus 'servicebus.bicep' = {
  name: 'serviceBus'
  params: {
    location: location
    serviceBusNamespaceName: serviceBusNamespaceName
  }
}
module appServicePlan 'appserviceplan.bicep' = {
  name: 'appServicePlan'
  params: {
    location: location
    appServicePlanName: appServicePlanName
  }
}

module appService 'appservice.bicep' = {
  name: 'appService'
  params: {
    location: location
    appServiceName: appServiceName
    appServicePlanId: appServicePlan.outputs.id
  }
}

module sql 'sql.bicep' = {
  name: 'sql'
  params: {
    location: location
    sqlServerName: sqlServerName
    sqlDatabaseName: sqlDatabaseName
    sqlAdminPassword: sqlAdminPassword
  }
}

module keyVault 'keyvault.bicep' = {
  name: 'keyVault'
  params: {
    location: location
    keyVaultName: keyVaultName
    appServicePrincipalId: appService.outputs.principalId
  }
}

module apim 'apim.bicep' = {
  name: 'apim'
  params: {
    location: location
    apimServiceName: apimServiceName
    appServiceName: appServiceName
  }
}

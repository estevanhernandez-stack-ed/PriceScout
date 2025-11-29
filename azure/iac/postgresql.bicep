param location string
param postgreSqlServerName string
param administratorLogin string = 'psqladmin'
@secure()
param administratorLoginPassword string = 'ThisShouldBeAStrongPassword123!'

resource postgreSqlServer 'Microsoft.DBforPostgreSQL/servers@2021-06-01' = {
  name: postgreSqlServerName
  location: location
  sku: {
    name: 'B_Gen5_1'
    tier: 'Basic'
    capacity: 1
  }
  properties: {
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    version: '14'
    sslEnforcement: 'Enabled'
  }
}

resource firewallRule 'Microsoft.DBforPostgreSQL/servers/firewallRules@2021-06-01' = {
  name: 'AllowAllWindowsAzureIps'
  parent: postgreSqlServer
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

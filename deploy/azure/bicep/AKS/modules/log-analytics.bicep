// ================================================================
// log-analytics.bicep - Log Analytics Workspace
// ================================================================

@description('Azure location')
param location string

@description('Log Analytics Workspace name')
param lawName string

@description('Resource tags')
param tags object = {}

// ================================================================
// Log Analytics Workspace
// ================================================================

resource law 'Microsoft.OperationalInsights/workspaces@2021-12-01-preview' = {
  name: lawName
  location: location
  tags: tags
  properties: {
    sku: {
      name: 'PerGB2018'
    }
    retentionInDays: 30
    features: {
      enableLogAccessUsingOnlyResourcePermissions: true
    }
  }
}

// ================================================================
// Outputs
// ================================================================

output lawId string = law.id
output lawCustomerId string = law.properties.customerId

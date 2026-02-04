// main.bicep - AKS deployment with managed NGINX ingress
targetScope = 'subscription'

@description('Resource group name')
param rgName string

@description('Deployment location')
param location string = 'eastus'

@description('AKS cluster name')
param aksClusterName string

@description('DNS prefix for the AKS cluster')
param dnsPrefix string = aksClusterName

@description('Kubernetes version')
param kubernetesVersion string = '1.29.0'

@description('Node pool VM size')
param nodeVmSize string = 'Standard_D2s_v3'

@description('Number of nodes in the default node pool')
@minValue(1)
@maxValue(100)
param nodeCount int = 2

@description('Minimum number of nodes for autoscaling')
@minValue(1)
param minNodeCount int = 1

@description('Maximum number of nodes for autoscaling')
@minValue(1)
param maxNodeCount int = 5

@description('Enable NGINX ingress controller addon')
param enableNginxIngress bool = true

@description('Resource tags')
param tags object = {}

// -----------------------------------------------------------------------------
// Resource Group
// -----------------------------------------------------------------------------
resource rg 'Microsoft.Resources/resourceGroups@2021-04-01' = {
  name: rgName
  location: location
  tags: tags
}

// -----------------------------------------------------------------------------
// Log Analytics Workspace Module
// -----------------------------------------------------------------------------
module law 'modules/log-analytics.bicep' = {
  name: '${aksClusterName}-law'
  scope: rg
  params: {
    location: location
    lawName: '${aksClusterName}-law'
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// AKS Cluster Module
// -----------------------------------------------------------------------------
module aks 'modules/aks-cluster.bicep' = {
  name: '${aksClusterName}-cluster'
  scope: rg
  params: {
    location: location
    clusterName: aksClusterName
    dnsPrefix: dnsPrefix
    kubernetesVersion: kubernetesVersion
    nodeVmSize: nodeVmSize
    nodeCount: nodeCount
    minNodeCount: minNodeCount
    maxNodeCount: maxNodeCount
    enableNginxIngress: enableNginxIngress
    lawId: law.outputs.lawId
    tags: tags
  }
}

// -----------------------------------------------------------------------------
// Outputs
// -----------------------------------------------------------------------------
@description('AKS cluster name')
output aksClusterName string = aks.outputs.clusterName

@description('AKS cluster FQDN')
output aksClusterFqdn string = aks.outputs.clusterFqdn

@description('AKS cluster resource ID')
output aksClusterId string = aks.outputs.clusterId

@description('Node resource group')
output nodeResourceGroup string = aks.outputs.nodeResourceGroup

@description('Log Analytics Workspace ID')
output lawId string = law.outputs.lawId

@description('Get credentials command')
output getCredentialsCommand string = 'az aks get-credentials --resource-group ${rgName} --name ${aksClusterName}'

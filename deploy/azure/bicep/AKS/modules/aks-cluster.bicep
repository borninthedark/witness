// ================================================================
// aks-cluster.bicep - AKS Cluster with managed NGINX ingress
// ================================================================

@description('Azure location')
param location string

@description('AKS cluster name')
param clusterName string

@description('DNS prefix for AKS cluster')
param dnsPrefix string

@description('Kubernetes version')
param kubernetesVersion string = '1.29.0'

@description('Node VM size')
param nodeVmSize string = 'Standard_D2s_v3'

@description('Initial node count')
param nodeCount int = 2

@description('Minimum node count for autoscaling')
param minNodeCount int = 1

@description('Maximum node count for autoscaling')
param maxNodeCount int = 5

@description('Enable NGINX ingress controller')
param enableNginxIngress bool = true

@description('Log Analytics Workspace ID')
param lawId string

@description('Resource tags')
param tags object = {}

// ================================================================
// AKS Cluster
// ================================================================

resource aksCluster 'Microsoft.ContainerService/managedClusters@2024-01-01' = {
  name: clusterName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    dnsPrefix: dnsPrefix
    kubernetesVersion: kubernetesVersion

    // Agent Pool Profile
    agentPoolProfiles: [
      {
        name: 'systempool'
        count: nodeCount
        vmSize: nodeVmSize
        osType: 'Linux'
        mode: 'System'
        enableAutoScaling: true
        minCount: minNodeCount
        maxCount: maxNodeCount
        type: 'VirtualMachineScaleSets'
        availabilityZones: []
        enableNodePublicIP: false
      }
    ]

    // Network Profile
    networkProfile: {
      networkPlugin: 'azure'
      networkPolicy: 'azure'
      loadBalancerSku: 'standard'
      serviceCidr: '10.0.0.0/16'
      dnsServiceIP: '10.0.0.10'
    }

    // Add-ons
    addonProfiles: {
      omsagent: {
        enabled: true
        config: {
          logAnalyticsWorkspaceResourceID: lawId
        }
      }
      azureKeyvaultSecretsProvider: {
        enabled: false
      }
    }

    // Ingress Application Gateway addon (NGINX managed)
    ingressProfile: enableNginxIngress ? {
      webAppRouting: {
        enabled: true
      }
    } : null

    // Security
    enableRBAC: true
    aadProfile: {
      managed: true
      enableAzureRBAC: true
    }

    // Auto-upgrade
    autoUpgradeProfile: {
      upgradeChannel: 'stable'
    }

    // API Server Access
    apiServerAccessProfile: {
      enablePrivateCluster: false
    }
  }
}

// ================================================================
// Outputs
// ================================================================

output clusterName string = aksCluster.name
output clusterId string = aksCluster.id
output clusterFqdn string = aksCluster.properties.fqdn
output nodeResourceGroup string = aksCluster.properties.nodeResourceGroup

// Production parameters for AKS deployment
using './main.bicep'

param rgName              = 'utopia-rg'
param location            = 'eastus'
param aksClusterName      = 'fitness-aks'
param dnsPrefix           = 'fitness'

param kubernetesVersion   = '1.33.4'
param nodeVmSize          = 'Standard_D2s_v3'
param nodeCount           = 2
param minNodeCount        = 1
param maxNodeCount        = 5

param enableNginxIngress  = true

# Set variables
$ResourceGroup = "mcp-registry"
$Location = "westeurope"
$StaticSiteName = "mcp-registry"
$GitHubRepo = "clemensv/xregistry-mcp"
$GitHubToken = "<your-github-personal-access-token>"

# Create resource group if it doesn't exist
az group create --name $ResourceGroup --location $Location

# Create the static web app if it doesn't exist
az staticwebapp create `
  --name $StaticSiteName `
  --resource-group $ResourceGroup `
  --location $Location `
  --source "https://github.com/$GitHubRepo" `
  --branch "static-site" `
  --output-location "/live" `
  --login-with-github

<# 
# Uncomment to get the deployment token if needed
$DeploymentToken = az staticwebapp secrets list `
  --name $StaticSiteName `
  --resource-group $ResourceGroup `
  --query "properties.apiKey" -o tsv

Write-Output "Deployment Token: $DeploymentToken"

# Set the GitHub secret for the deployment token
gh secret set AZURE_STATIC_WEB_APPS_API_TOKEN -b "$DeploymentToken" -R $GitHubRepo

Write-Output "Deployment token has been set as a GitHub secret."
#>

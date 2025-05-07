<#
.SYNOPSIS
    Deploy Azure Storage static website and assign RBAC roles.
.DESCRIPTION
    Equivalent PowerShell script for deploy-azstg.sh; supports commands: deploy, assign-root, assign-group.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true, Position=0)]
    [ValidateSet("deploy","assign-root","assign-group")]
    [string]$Command,
    [string]$SubscriptionId,
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    [Parameter(Mandatory=$true)]
    [string]$Location,
    [Parameter(Mandatory=$true)]
    [string]$StorageAccount,
    [string]$ContentDir,
    [string]$RoleRoot,
    [string]$RootPrincipalId,
    [string]$RoleProvider,
    [string]$ProviderGroup
)

$ErrorActionPreference = 'Stop'

function Show-Usage {
    Write-Host "Usage: .\deploy-azstg.ps1 <deploy|assign-root|assign-group> -ResourceGroup <rg> -Location <loc> -StorageAccount <sa> [-SubscriptionId <sub>] [-ContentDir <dir>] [-RoleRoot <role>] [-RootPrincipalId <id>] [-RoleProvider <role>] [-ProviderGroup <group>]"
    exit 1
}

switch ($Command) {
    'deploy' {
        if (-not $ContentDir) { Write-Error "ContentDir is required for deploy"; Show-Usage }
        if ($SubscriptionId) { az account set --subscription $SubscriptionId } else { Write-Host "No subscription specified; using current subscription." }
        try { az group show -n $ResourceGroup | Out-Null } catch { az group create --name $ResourceGroup --location $Location | Out-Null }
        try { az storage account show -n $StorageAccount -g $ResourceGroup | Out-Null } catch { az storage account create --name $StorageAccount --resource-group $ResourceGroup --location $Location --sku Standard_LRS --kind StorageV2 --enable-hierarchical-namespace false | Out-Null }
        az storage blob service-properties update --account-name $StorageAccount --static-website --index-document index.html --404-document 404.html | Out-Null
        $StorageKey = az storage account keys list --account-name $StorageAccount --resource-group $ResourceGroup --query '[0].value' -o tsv
        $TempPath = Join-Path ([System.IO.Path]::GetTempPath()) ("xregistry_mcp_{0}" -f [System.Guid]::NewGuid())
        New-Item -ItemType Directory -Path $TempPath | Out-Null
        Write-Host "Staging content in $TempPath"
        Copy-Item -Path (Join-Path $ContentDir '*') -Destination $TempPath -Recurse -Force
        $StaticWebEndpoint = az storage account show --name $StorageAccount --resource-group $ResourceGroup --query "primaryEndpoints.web" -o tsv
        Get-ChildItem -Path $TempPath -Recurse -Include *.html,*.htm | ForEach-Object {
            (Get-Content $_.FullName) -replace 'https://clemensv.github.io/xregistry-mcp/', $StaticWebEndpoint | Set-Content $_.FullName
        }
        Get-ChildItem -Path $TempPath -Recurse -File | ForEach-Object {
            $rel = $_.FullName.Substring($TempPath.Length + 1)
            switch ($_.Extension.ToLower()) {
                '.html' { $ct = 'application/json' }
                '.css'  { $ct = 'text/css' }
                '.js'   { $ct = 'application/javascript' }
                '.svg'  { $ct = 'image/svg+xml' }
                '.png'  { $ct = 'image/png' }
                '.jpg'  { $ct = 'image/jpeg' }
                '.jpeg' { $ct = 'image/jpeg' }
                default { $ct = 'application/octet-stream' }
            }
            Write-Host "Uploading $($_.FullName) as $rel with content-type $ct"
            az storage blob upload --account-name $StorageAccount --account-key $StorageKey --container-name '$web' --name $rel --file $_.FullName --content-type $ct --overwrite | Out-Null
        }
    }
    'assign-root' {
        if (-not $RoleRoot -or -not $RootPrincipalId) { Write-Error "RoleRoot and RootPrincipalId are required for assign-root"; Show-Usage }
        $StorageId = az storage account show --name $StorageAccount --resource-group $ResourceGroup --query id -o tsv
        $WebScope = "$StorageId/blobServices/default/containers/`$web"
        az role assignment create --role $RoleRoot --assignee-object-id $RootPrincipalId --scope $WebScope | Out-Null
    }
    'assign-group' {
        if (-not $RoleProvider -or -not $ProviderGroup) { Write-Error "RoleProvider and ProviderGroup are required for assign-group"; Show-Usage }
        $GroupObjId = az ad group show --group $ProviderGroup --query objectId -o tsv
        $StorageId = az storage account show --name $StorageAccount --resource-group $ResourceGroup --query id -o tsv
        $WebScope = "$StorageId/blobServices/default/containers/`$web"
        az role assignment create --role $RoleProvider --assignee-object-id $GroupObjId --scope $WebScope | Out-Null
    }
    Default { Show-Usage }
}

Write-Host "✅ Deployment complete."
Write-Host "Static website URL: https://$StorageAccount.z$Location.web.core.windows.net/"
if ($RoleRoot -and $RootPrincipalId) { Write-Host "• $RoleRoot → Principal $RootPrincipalId" }
if ($RoleProvider -and $ProviderGroup) { Write-Host "• $RoleProvider → Group $ProviderGroup" }
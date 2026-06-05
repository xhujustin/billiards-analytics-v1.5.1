param(
    [Parameter(Mandatory = $true)]
    [string]$ProjectId,

    [string]$Region = "asia-east1",

    [string]$ServiceName = "cuevex-mobile-api",

    [string]$ImageName = "cuevex-mobile-api",

    [string]$SupabaseUrl = $env:SUPABASE_URL,

    [string]$SupabaseServiceRoleKey = $env:SUPABASE_SERVICE_ROLE_KEY,

    [string]$SupabaseStorageBucket = "community-uploads",

    [string]$MobilePublicBaseUrl = "",

    [string]$ServiceRoleSecretName = "cuevex-supabase-service-role-key",

    [switch]$AllowUnauthenticated = $true
)

$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$Tag = Get-Date -Format "yyyyMMddHHmmss"
$Image = "gcr.io/$ProjectId/$ImageName`:$Tag"
$Gcloud = "gcloud.cmd"

function Invoke-Gcloud {
    & $Gcloud @args
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed with exit code $LASTEXITCODE`: $($args -join ' ')"
    }
}

if (-not $SupabaseUrl) {
    throw "SUPABASE_URL is required. Pass -SupabaseUrl or set `$env:SUPABASE_URL."
}

Write-Host "Building image: $Image"
Invoke-Gcloud builds submit $Root --project $ProjectId --config (Join-Path $Root "cloudbuild.mobile.yaml") --substitutions "_IMAGE=$Image" --timeout "1200s"

if ($SupabaseServiceRoleKey) {
    Write-Host "Updating Secret Manager secret: $ServiceRoleSecretName"
    $secretExists = $true
    try {
        Invoke-Gcloud secrets describe $ServiceRoleSecretName --project $ProjectId | Out-Null
    } catch {
        $secretExists = $false
    }
    if (-not $secretExists) {
        Invoke-Gcloud secrets create $ServiceRoleSecretName --project $ProjectId --replication-policy automatic | Out-Null
    }
    $SupabaseServiceRoleKey | & $Gcloud secrets versions add $ServiceRoleSecretName --project $ProjectId --data-file=- | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "gcloud command failed with exit code $LASTEXITCODE`: secrets versions add $ServiceRoleSecretName"
    }
} else {
    Write-Host "No SupabaseServiceRoleKey was provided; deploy will use existing secret: $ServiceRoleSecretName"
}

$ProjectNumber = & $Gcloud projects describe $ProjectId --format "value(projectNumber)"
if ($LASTEXITCODE -ne 0 -or -not $ProjectNumber) {
    throw "Could not resolve project number for $ProjectId."
}
$CloudRunRuntimeServiceAccount = "$ProjectNumber-compute@developer.gserviceaccount.com"
Write-Host "Granting Secret Manager access to Cloud Run runtime service account: $CloudRunRuntimeServiceAccount"
Invoke-Gcloud secrets add-iam-policy-binding $ServiceRoleSecretName `
    --project $ProjectId `
    --member "serviceAccount:$CloudRunRuntimeServiceAccount" `
    --role "roles/secretmanager.secretAccessor" | Out-Null

$authFlag = if ($AllowUnauthenticated) { "--allow-unauthenticated" } else { "--no-allow-unauthenticated" }
$envVars = @(
    "ACCOUNT_STORE_BACKEND=supabase",
    "SUPABASE_URL=$SupabaseUrl",
    "SUPABASE_STORAGE_BUCKET=$SupabaseStorageBucket",
    "MOBILE_REQUIRE_HTTPS_QR=true"
)

if ($MobilePublicBaseUrl) {
    $envVars += "MOBILE_PUBLIC_BASE_URL=$MobilePublicBaseUrl"
}

$envVarsValue = $envVars -join ","

Write-Host "Deploying Cloud Run service: $ServiceName"
Invoke-Gcloud run deploy $ServiceName `
    --project $ProjectId `
    --region $Region `
    --image $Image `
    --platform managed `
    --memory 512Mi `
    --cpu 1 `
    --concurrency 40 `
    --timeout 60 `
    --min-instances 1 `
    --set-env-vars $envVarsValue `
    --set-secrets "SUPABASE_SERVICE_ROLE_KEY=$ServiceRoleSecretName`:latest" `
    $authFlag

$ServiceUrl = & $Gcloud run services describe $ServiceName --project $ProjectId --region $Region --format "value(status.url)"
if ($LASTEXITCODE -ne 0) {
    throw "gcloud command failed with exit code $LASTEXITCODE`: run services describe $ServiceName"
}
if (-not $ServiceUrl) {
    throw "Cloud Run service URL is empty. Check deployment logs before using the service."
}
Write-Host "Cloud Run URL: $ServiceUrl"
Write-Host "Set MOBILE_PUBLIC_BASE_URL to this URL after the first deploy if QR invites should use Cloud Run."

param([Parameter(Mandatory=$true)][string]$Path)
$ErrorActionPreference = 'Stop'
# Use the module belonging to this PowerShell, not an inherited PSModulePath
# from a different host/version used by the release builder.
Import-Module (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security') -ErrorAction Stop
$signature = Get-AuthenticodeSignature -LiteralPath $Path
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'The WebView2 bootstrapper must have a valid Microsoft Authenticode signature.'
}

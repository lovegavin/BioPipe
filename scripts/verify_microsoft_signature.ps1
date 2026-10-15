param([Parameter(Mandatory=$true)][string]$Path)
$ErrorActionPreference = 'Stop'
$signature = Get-AuthenticodeSignature -LiteralPath $Path
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Microsoft Corporation') {
    throw 'The WebView2 bootstrapper must have a valid Microsoft Authenticode signature.'
}

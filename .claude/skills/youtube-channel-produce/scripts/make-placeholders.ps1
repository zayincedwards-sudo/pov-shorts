# Generates black-rectangle placeholders with white text for PHOTO shots only.
# Reads shots.txt lines of the form "photo | <description>" or "drawing | <description>".
# "drawing" lines are skipped (generate-drawings.mjs handles them). Filenames keep video order.
# Usage: powershell -NoProfile -File make-placeholders.ps1 -Shots shots.txt -Out shots
param(
  [Parameter(Mandatory = $true)][string]$Shots,
  [string]$Out = "shots",
  [int]$Width = 1920,
  [int]$Height = 1080
)

Add-Type -AssemblyName System.Drawing

$lines = Get-Content -LiteralPath $Shots | Where-Object { $_.Trim() -ne "" }
if ($lines.Count -eq 0) { Write-Error "No shots found in $Shots"; exit 1 }
if (-not (Test-Path -LiteralPath $Out)) { New-Item -ItemType Directory -Path $Out | Out-Null }

$font  = New-Object System.Drawing.Font("Arial", [single]46, [System.Drawing.FontStyle]::Bold)
$brush = [System.Drawing.Brushes]::White
$fmt   = New-Object System.Drawing.StringFormat
$fmt.Alignment     = [System.Drawing.StringAlignment]::Center
$fmt.LineAlignment = [System.Drawing.StringAlignment]::Center

$i = 0
$photoCount = 0
foreach ($line in $lines) {
  $i++
  $parts = $line -split "\|\|"
  $type = $parts[0].Trim().ToLower()
  if ($parts.Count -gt 1) { $desc = $parts[1].Trim() } else { $desc = $line.Trim() }
  $num = "{0:D2}" -f $i
  if ($type -eq "drawing") {
    Write-Output ("Skip shot-" + $num + " (drawing)")
    continue
  }
  $bmp = New-Object System.Drawing.Bitmap($Width, $Height)
  $g = [System.Drawing.Graphics]::FromImage($bmp)
  $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias
  $g.Clear([System.Drawing.Color]::Black)
  $rect = New-Object System.Drawing.RectangleF([single]100, [single]100, [single]($Width - 200), [single]($Height - 200))
  $g.DrawString($desc, $font, $brush, $rect, $fmt)
  $outPath = Join-Path $Out ("shot-" + $num + ".png")
  $bmp.Save($outPath, [System.Drawing.Imaging.ImageFormat]::Png)
  $g.Dispose()
  $bmp.Dispose()
  Write-Output ("Wrote " + $outPath + "  (photo)")
  $photoCount++
}
Write-Output ("Done: " + $photoCount + " photo placeholder(s) in " + $Out + " (drawings skipped)")

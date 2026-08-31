# Merge duplicate labels (A), build Datasets/leaf_type (F), relocate leaf_gate.
# Called by: powershell -File scripts/build_leaf_type.ps1
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Datasets = Join-Path $Root "Datasets"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class WinLink2 {
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern bool CreateHardLink(string lpFileName, string lpExistingFileName, IntPtr lpSecurityAttributes);
}
"@

$ImgExt = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
@(".jpg",".jpeg",".jpe",".jfif",".png",".bmp",".webp",".gif",".tif",".tiff") | ForEach-Object { [void]$ImgExt.Add($_) }

$Merge = [ordered]@{
  "Apple rust leaf" = "Apple___Cedar_apple_rust"
  "Corn___Blight" = "Corn_(maize)___Northern_Leaf_Blight"
  "Corn___Common_Rust" = "Corn_(maize)___Common_rust_"
  "Corn___Gray_Leaf_Spot" = "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot"
  "Corn___healthy" = "Corn_(maize)___healthy"
  "Rice___Brownspot" = "Rice___Brown_spot"
  "Rice___Leaf_blast" = "Rice___Blast"
  "Tomato___Spider_Mites_Two-spotted_Spider_Mite" = "Tomato___Spider_mites Two-spotted_spider_mite"
  "Potato___Healthy_Potatoes" = "Potato___healthy"
}

function Get-CropName([string]$name) {
  if ($Merge.Contains($name)) { $name = [string]$Merge[$name] }
  $crop = if ($name.Contains("___")) { $name.Split("___", 2)[0] } else { $name }
  $crop = $crop.Replace("_(maize)", "").Replace("(maize)", "")
  $crop = $crop.Replace("_(including_sour)", "").Replace(",_bell", "")
  $low = $crop.ToLower().Replace("_", " ").Trim()
  if ($low.StartsWith("corn")) { return "Corn" }
  if ($low.StartsWith("pepper")) { return "Pepper" }
  if ($low.StartsWith("cherry")) { return "Cherry" }
  if ($low.Contains("amaranth")) { return "Red Amaranth" }
  $out = $crop.Replace("_", " ").Trim()
  if ($out) { return $out }
  return $name
}

function Get-UniqueDest([string]$folder, [string]$fileName) {
  $dest = Join-Path $folder $fileName
  if (-not (Test-Path -LiteralPath $dest)) { return $dest }
  $stem = [System.IO.Path]::GetFileNameWithoutExtension($fileName)
  $suf = [System.IO.Path]::GetExtension($fileName)
  $i = 1
  while ($true) {
    $cand = Join-Path $folder ("{0}__m{1}{2}" -f $stem, $i, $suf)
    if (-not (Test-Path -LiteralPath $cand)) { return $cand }
    $i++
  }
}

function Get-SafePrefix([string]$text) {
  $sb = New-Object System.Text.StringBuilder
  foreach ($c in $text.ToCharArray()) {
    if ([char]::IsLetterOrDigit($c) -or $c -eq '-' -or $c -eq '_' -or $c -eq '.') {
      [void]$sb.Append($c)
    } else {
      [void]$sb.Append('_')
    }
  }
  $s = $sb.ToString()
  if ($s.Length -gt 80) { return $s.Substring(0, 80) }
  return $s
}

Write-Host "=== A: merge duplicate disease labels ==="
$moved = 0
foreach ($split in @("train", "valid", "test")) {
  $root = Join-Path $Datasets $split
  foreach ($alias in $Merge.Keys) {
    $canonical = [string]$Merge[$alias]
    $src = Join-Path $root $alias
    $dst = Join-Path $root $canonical
    if (-not (Test-Path -LiteralPath $src)) { continue }
    New-Item -ItemType Directory -Force -Path $dst | Out-Null
    $files = [System.IO.Directory]::EnumerateFiles($src, "*.*", [System.IO.SearchOption]::AllDirectories)
    foreach ($f in $files) {
      $ext = [System.IO.Path]::GetExtension($f)
      if (-not $ImgExt.Contains($ext)) { continue }
      $dest = Get-UniqueDest $dst ([System.IO.Path]::GetFileName($f))
      [System.IO.File]::Move($f, $dest)
      $moved++
    }
    Remove-Item -LiteralPath $src -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "  merged $split/$alias -> $canonical"
  }
}
Write-Host "Moved $moved files into canonical class folders."

Write-Host "`n=== F: build Datasets/leaf_type ==="
$linked = 0
$leafType = Join-Path $Datasets "leaf_type"
if (Test-Path -LiteralPath $leafType) {
  $existing = @(Get-ChildItem -LiteralPath (Join-Path $leafType "train") -Directory -ErrorAction SilentlyContinue)
  if ($existing.Count -gt 0) {
    Write-Host "  leaf_type already present ($($existing.Count) crops); skipping rebuild"
    $linked = -1
  }
}
if ($linked -ge 0) {
  foreach ($split in @("train", "valid", "test")) {
    $srcRoot = Join-Path $Datasets $split
    $nSplit = 0
    $classDirs = @(Get-ChildItem -LiteralPath $srcRoot -Directory -Force)
    $ci = 0
    foreach ($classDir in $classDirs) {
      $ci++
      $crop = Get-CropName $classDir.Name
      $out = Join-Path (Join-Path $leafType $split) $crop
      if (-not (Test-Path -LiteralPath $out)) {
        New-Item -ItemType Directory -Force -Path $out | Out-Null
      }
      $idx = 0
      $files = [System.IO.Directory]::EnumerateFiles($classDir.FullName, "*.*", [System.IO.SearchOption]::AllDirectories)
      foreach ($f in $files) {
        $ext = [System.IO.Path]::GetExtension($f)
        if (-not $ImgExt.Contains($ext)) { continue }
        $idx++
        $dest = Join-Path $out ("{0:D3}_{1:D8}{2}" -f $ci, $idx, $ext.ToLower())
        if (Test-Path -LiteralPath $dest) { continue }
        $ok = [WinLink2]::CreateHardLink($dest, $f, [IntPtr]::Zero)
        if (-not $ok) {
          [System.IO.File]::Copy($f, $dest, $true)
        }
        $linked++
        $nSplit++
      }
      if (($ci % 20) -eq 0) {
        Write-Host ("  [{0}/{1}] {2}  linked {3:N0}" -f $ci, $classDirs.Count, $classDir.Name, $linked)
      }
    }
    Write-Host ("  leaf_type/{0}: {1:N0} images" -f $split, $nSplit)
  }
  Write-Host ("Hard-linked {0:N0} images into leaf_type." -f $linked)
}

Write-Host "`n=== Drop mango variety folders from Level-3 splits ==="
$removed = 0
foreach ($split in @("train", "valid", "test")) {
  $root = Join-Path $Datasets $split
  $classDirs = @(Get-ChildItem -LiteralPath $root -Directory -Force)
  foreach ($classDir in $classDirs) {
    if ($classDir.Name.ToLower() -notlike "*variety*") { continue }
    $n = @([System.IO.Directory]::EnumerateFiles($classDir.FullName, "*.*", [System.IO.SearchOption]::AllDirectories)).Count
    Remove-Item -LiteralPath $classDir.FullName -Recurse -Force
    $removed += $n
    Write-Host "  dropped Level-3 variety $split/$($classDir.Name) ($n files)"
  }
}
Write-Host "Removed $removed variety files from disease splits."

Write-Host "`n=== Relocate leaf_gate to Datasets/leaf_gate ==="
$srcGate = Join-Path $Datasets "vision\leaf_gate"
$dstGate = Join-Path $Datasets "leaf_gate"
if (Test-Path -LiteralPath $dstGate) {
  Write-Host "  leaf_gate already at $dstGate"
} elseif (Test-Path -LiteralPath $srcGate) {
  Move-Item -LiteralPath $srcGate -Destination $dstGate
  Write-Host "  moved $srcGate -> $dstGate"
} else {
  Write-Host "  no leaf_gate at $srcGate"
}
Write-Host "Done."

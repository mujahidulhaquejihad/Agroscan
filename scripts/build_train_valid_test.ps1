# Build Datasets/train, Datasets/valid, Datasets/test
# with every disease class in each split (hard links, no extra disk).
# Also builds Datasets/vision/leaf_gate/{train,valid,test} for leaf vs non-leaf.
$ErrorActionPreference = "Stop"
$Root = Split-Path $PSScriptRoot -Parent
$Datasets = Join-Path $Root "Datasets"
$Disease = Join-Path $Datasets "vision\disease"
$LeafGate = Join-Path $Datasets "vision\leaf_gate"
$TrainRoot = Join-Path $Datasets "train"
$ValidRoot = Join-Path $Datasets "valid"
$TestRoot = Join-Path $Datasets "test"
$LeafTrain = Join-Path $LeafGate "train"
$LeafValid = Join-Path $LeafGate "valid"
$LeafTest = Join-Path $LeafGate "test"
$Log = Join-Path $Datasets "split_build_log.txt"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class WinLink {
  [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern bool CreateHardLink(string lpFileName, string lpExistingFileName, IntPtr lpSecurityAttributes);
}
"@

$ImgExt = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
@(".jpg",".jpeg",".jpe",".jfif",".png",".bmp",".webp",".gif",".tif",".tiff") | ForEach-Object { [void]$ImgExt.Add($_) }

$PlantDoc = @{
  "Apple Scab Leaf" = "Apple___Apple_scab"
  "Apple leaf" = "Apple___healthy"
  "Bell_pepper leaf spot" = "Pepper,_bell___Bacterial_spot"
  "Bell_pepper leaf" = "Pepper,_bell___healthy"
  "Blueberry leaf" = "Blueberry___healthy"
  "Cherry leaf" = "Cherry_(including_sour)___healthy"
  "Corn Gray leaf spot" = "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot"
  "Corn leaf blight" = "Corn_(maize)___Northern_Leaf_Blight"
  "Corn rust leaf" = "Corn_(maize)___Common_rust_"
  "Grape leaf" = "Grape___healthy"
  "Grape leaf black rot" = "Grape___Black_rot"
  "Peach leaf" = "Peach___healthy"
  "Potato leaf early blight" = "Potato___Early_blight"
  "Potato leaf late blight" = "Potato___Late_blight"
  "Potato leaf" = "Potato___healthy"
  "Raspberry leaf" = "Raspberry___healthy"
  "Soyabean leaf" = "Soybean___healthy"
  "Soybean leaf" = "Soybean___healthy"
  "Squash Powdery mildew leaf" = "Squash___Powdery_mildew"
  "Strawberry leaf" = "Strawberry___healthy"
  "Tomato Early blight leaf" = "Tomato___Early_blight"
  "Tomato Septoria leaf spot" = "Tomato___Septoria_leaf_spot"
  "Tomato leaf" = "Tomato___healthy"
  "Tomato leaf bacterial spot" = "Tomato___Bacterial_spot"
  "Tomato leaf late blight" = "Tomato___Late_blight"
  "Tomato leaf mosaic virus" = "Tomato___Tomato_mosaic_virus"
  "Tomato leaf yellow virus" = "Tomato___Tomato_Yellow_Leaf_Curl_Virus"
  "Tomato mold leaf" = "Tomato___Late_blight"
  "Tomato two spotted spider mites leaf" = "Tomato___Spider_mites Two-spotted_spider_mite"
}

$Archive = @{
  "Corn___Common_Rust" = "Corn_(maize)___Common_rust_"
  "Corn___Gray_Leaf_Spot" = "Corn_(maize)___Cercospora_leaf_spot Gray_leaf_spot"
  "Corn___Healthy" = "Corn_(maize)___healthy"
  "Corn___Leaf_Blight" = "Corn_(maize)___Northern_Leaf_Blight"
  "Potato___Early_Blight" = "Potato___Early_blight"
  "Potato___Healthy" = "Potato___healthy"
  "Potato___Late_Blight" = "Potato___Late_blight"
  "Rice___Brown_Spot" = "Rice___Brown_spot"
  "Rice___Healthy" = "Rice___healthy"
  "Rice___Hispa" = "Rice___Hispa"
  "Rice___Leaf_Blast" = "Rice___Leaf_blast"
  "Wheat___Brown_Rust" = "Wheat___Brown_rust"
  "Wheat___Healthy" = "Wheat___healthy"
  "Wheat___Yellow_Rust" = "Wheat___Yellow_rust"
}

function Write-Log([string]$msg) {
  $line = "$(Get-Date -Format 'HH:mm:ss')  $msg"
  Write-Host $line
  Add-Content -LiteralPath $Log -Value $line -Encoding UTF8
}

function Get-BdCanonical([string]$raw) {
  if ($raw.Contains("___")) { return $raw }
  $parts = $raw.Split("_", 2)
  if ($parts.Count -eq 2) {
    $crop = $parts[0]; $cond = $parts[1]
    if ($cond.ToLower() -in @("normal", "healthy")) { return "$crop`___healthy" }
    return "$crop`___$cond"
  }
  if ($raw.Contains("_")) { return $raw.Replace("_", "___", 1) }
  return $raw
}

function Get-Canonical([string]$raw, [string]$source) {
  $raw = $raw.Trim()
  if (-not $raw -or $raw.ToLower() -eq "invalid") { return "" }
    switch ($source) {
    "keep"     { return $raw }
    "plantdoc" { if ($PlantDoc.ContainsKey($raw)) { return $PlantDoc[$raw] } }
    "archive"  { if ($Archive.ContainsKey($raw)) { return $Archive[$raw] } }
    "bd"       { return Get-BdCanonical $raw }
    "mangifera" {
      $base = [regex]::Replace($raw, "-\d+$", "").Replace("-", " ").Trim()
      $slug = $base.Replace(" ", "_")
      return "Mango___Variety_$slug"
    }
    "bd_leaf" {
      $crop = $raw.Replace("-", "_").Replace(" ", "_").Trim()
      if ($crop.ToLower() -eq "corn") { $crop = "Corn_(maize)" }
      return "$crop`___BD_Leaf_Disease"
    }
  }
  if ($raw.Contains("___")) { return $raw }
  return Get-BdCanonical $raw
}

function Add-ClassImages {
  param([string]$RootDir, [string]$Source, [hashtable]$Bucket, [string]$Label = "")
  $exists = Test-Path -LiteralPath $RootDir
  if (-not $exists) {
    Write-Log "  MISS $RootDir"
    return 0
  }
  $n = 0
  $classDirs = @(Get-ChildItem -LiteralPath $RootDir -Directory -Force)
  foreach ($classDir in $classDirs) {
    $raw = $classDir.Name
    $cls = if ($Label) { $Label } else { Get-Canonical $raw $Source }
    if (-not $cls) {
      Write-Log "  skip class '$raw' source=$Source"
      continue
    }
    if (-not $Bucket.ContainsKey($cls)) {
      $Bucket[$cls] = [System.Collections.Generic.List[string]]::new()
    }
    $files = [System.IO.Directory]::EnumerateFiles($classDir.FullName, "*.*", [System.IO.SearchOption]::AllDirectories)
    foreach ($f in $files) {
      $ext = [System.IO.Path]::GetExtension($f)
      if (-not $ImgExt.Contains($ext)) { continue }
      $Bucket[$cls].Add($f)
      $n++
    }
  }
  Write-Log "  hit $RootDir  classes=$($classDirs.Count) images=$n"
  return $n
}

function Add-FlatImages {
  param([string]$RootDir, [string]$Cls, [hashtable]$Bucket)
  if (-not (Test-Path -LiteralPath $RootDir)) { return 0 }
  if (-not $Bucket.ContainsKey($Cls)) {
    $Bucket[$Cls] = [System.Collections.Generic.List[string]]::new()
  }
  $n = 0
  $files = [System.IO.Directory]::EnumerateFiles($RootDir, "*.*", [System.IO.SearchOption]::AllDirectories)
  foreach ($f in $files) {
    $ext = [System.IO.Path]::GetExtension($f)
    if (-not $ImgExt.Contains($ext)) { continue }
    $Bucket[$Cls].Add($f)
    $n++
  }
  return $n
}

function Get-ImageKey([string]$f) {
  $name = [System.IO.Path]::GetFileName($f).ToLowerInvariant()
  $sep = $name.IndexOf("___")
  if ($sep -ge 0) {
    $tail = $name.Substring($sep + 3)
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($tail).Trim()
    if ($stem) { return "pv:$stem" }
  }
  return "fn:$name"
}

function Dedup-Bucket([hashtable]$Bucket) {
  $skipped = 0
  foreach ($cls in @($Bucket.Keys)) {
    $seen = [System.Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $kept = [System.Collections.Generic.List[string]]::new()
    $skip = 0
    foreach ($f in $Bucket[$cls]) {
      $key = Get-ImageKey $f
      if ($seen.Add($key)) { [void]$kept.Add($f) } else { $skip++ }
    }
    $Bucket[$cls] = $kept
    $skipped += $skip
    if ($skip -gt 0) { Write-Log ("  dedup {0} skipped {1} duplicate/aug copies" -f $cls, $skip) }
  }
  Write-Log "Dedup total skipped $skipped (same filename or PlantVillage source id)"
}

function Split-Class([System.Collections.Generic.List[string]]$paths) {
  $arr = $paths.ToArray()
  $rng = [System.Random]::new(42)
  for ($i = $arr.Length - 1; $i -gt 0; $i--) {
    $j = $rng.Next($i + 1)
    $tmp = $arr[$i]; $arr[$i] = $arr[$j]; $arr[$j] = $tmp
  }
  $n = $arr.Length
  $train = New-Object System.Collections.Generic.List[string]
  $valid = New-Object System.Collections.Generic.List[string]
  $test  = New-Object System.Collections.Generic.List[string]
  if ($n -ge 3) {
    $nTest = [Math]::Max(1, [int][Math]::Floor($n * 0.10))
    $nValid = [Math]::Max(1, [int][Math]::Floor($n * 0.10))
    if (($nTest + $nValid) -ge $n) { $nTest = 1; $nValid = 1 }
    for ($i = 0; $i -lt $nTest; $i++) { $test.Add($arr[$i]) }
    for ($i = $nTest; $i -lt ($nTest + $nValid); $i++) { $valid.Add($arr[$i]) }
    for ($i = ($nTest + $nValid); $i -lt $n; $i++) { $train.Add($arr[$i]) }
  } elseif ($n -eq 2) {
    $train.Add($arr[0])
    $test.Add($arr[1])
  } else {
    $train.Add($arr[0])
  }
  return @{ train = $train; valid = $valid; test = $test }
}

function Link-File([string]$src, [string]$dstDir, [int]$index) {
  if (-not (Test-Path -LiteralPath $dstDir)) {
    New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
  }
  $name = [System.IO.Path]::GetFileName($src)
  $dst = Join-Path $dstDir ("{0:D8}_{1}" -f $index, $name)
  if (Test-Path -LiteralPath $dst) { return "skip" }
  $ok = [WinLink]::CreateHardLink($dst, $src, [IntPtr]::Zero)
  if ($ok) { return "link" }
  Copy-Item -LiteralPath $src -Destination $dst -Force
  return "copy"
}

function Build-Splits {
  param([hashtable]$Bucket, [string]$Train, [string]$Valid, [string]$Test, [string]$Kind)
  New-Item -ItemType Directory -Force -Path $Train, $Valid, $Test | Out-Null
  $classes = $Bucket.Keys | Sort-Object
  Write-Log "$Kind classes: $($classes.Count)"
  $stats = New-Object System.Collections.Generic.List[string]
  $i = 0
  $linked = 0
  foreach ($cls in $classes) {
    $i++
    $parts = Split-Class $Bucket[$cls]
    $safe = $cls
    $trDir = Join-Path $Train $safe
    $vaDir = Join-Path $Valid $safe
    $teDir = Join-Path $Test $safe
    $idx = 0
    foreach ($p in $parts.train) { [void](Link-File $p $trDir (++$idx)); $linked++ }
    foreach ($p in $parts.valid) { [void](Link-File $p $vaDir (++$idx)); $linked++ }
    foreach ($p in $parts.test)  { [void](Link-File $p $teDir (++$idx)); $linked++ }
    $line = ("{0,-55} train={1,6} valid={2,5} test={3,5}" -f $cls, $parts.train.Count, $parts.valid.Count, $parts.test.Count)
    $stats.Add($line)
    if (($i % 5) -eq 0 -or $i -eq $classes.Count) {
      Write-Log ("  [{0}/{1}] {2}  (files placed {3:N0})" -f $i, $classes.Count, $cls, $linked)
    }
  }
  $statsPath = Join-Path $Datasets ("split_counts_{0}.txt" -f $Kind)
  Set-Content -LiteralPath $statsPath -Value $stats -Encoding UTF8
  Write-Log "Wrote $statsPath"
}

# ---------------------------------------------------------------------------
if (Test-Path -LiteralPath $Log) { Remove-Item -LiteralPath $Log -Force }
Write-Log "Scanning disease sources..."

$diseaseMap = @{}
$pvAug = Join-Path $Disease "plantvillage_augmented\New Plant Diseases Dataset(Augmented)\New Plant Diseases Dataset(Augmented)"
$n = 0
$n += Add-ClassImages (Join-Path $Disease "plantvillage_augmented\New Plant Diseases Dataset(Augmented)\New Plant Diseases Dataset(Augmented)\train") "plantvillage" $diseaseMap
$n += Add-ClassImages (Join-Path $Disease "plantvillage_augmented\New Plant Diseases Dataset(Augmented)\New Plant Diseases Dataset(Augmented)\valid") "plantvillage" $diseaseMap
Write-Log "plantvillage_augmented: $n"
$n = Add-ClassImages (Join-Path $Disease "plantvillage_raw") "plantvillage" $diseaseMap
Write-Log "plantvillage_raw: $n"
$n = 0
$n += Add-ClassImages (Join-Path $Disease "bd_crop_disease\train") "bd" $diseaseMap
$n += Add-ClassImages (Join-Path $Disease "bd_crop_disease\valid") "bd" $diseaseMap
$n += Add-ClassImages (Join-Path $Disease "bd_crop_disease\test") "bd" $diseaseMap
Write-Log "bd_crop_disease: $n"
$n = 0
$n += Add-ClassImages (Join-Path $Disease "plantdoc\train") "plantdoc" $diseaseMap
$n += Add-ClassImages (Join-Path $Disease "plantdoc\test") "plantdoc" $diseaseMap
Write-Log "plantdoc: $n"
$n = Add-ClassImages (Join-Path $Disease "archive_crop_disease\CropDisease\Crop___DIsease") "archive" $diseaseMap
Write-Log "archive: $n"
$n = Add-ClassImages (Join-Path $Disease "mangifera2012\Mango_Dataset_2012") "mangifera" $diseaseMap
Write-Log "mangifera: $n"
$n = Add-ClassImages (Join-Path $Disease "bd_leaf_disease") "bd_leaf" $diseaseMap
Write-Log "bd_leaf_disease: $n"

Write-Log "Deduping disease images by filename / PlantVillage source id ..."
Dedup-Bucket $diseaseMap
Write-Log "Building Datasets/train|valid|test ..."
Build-Splits $diseaseMap $TrainRoot $ValidRoot $TestRoot "disease"

Write-Log "Scanning leaf-gate sources..."
$leaf = @{}
$n = Add-ClassImages (Join-Path $LeafGate "leaf-vs-non-leaf-images-002") "keep" $leaf
Write-Log "leaf-vs-non-leaf: $n"
$n = Add-FlatImages (Join-Path $LeafGate "natural-images\natural_images") "non_leaf" $leaf
Write-Log "natural-images -> non_leaf: $n"
$n = Add-FlatImages (Join-Path $LeafGate "fashion-product-images-small\images") "non_leaf" $leaf
Write-Log "fashion -> non_leaf: $n"
$n = Add-FlatImages (Join-Path $Disease "archive_crop_disease\CropDisease\Crop___DIsease\Invalid") "non_leaf" $leaf
Write-Log "archive Invalid -> non_leaf: $n"

# Cap non_leaf to 1.5x leaf so the gate is not swamped (same as training config).
if ($leaf.ContainsKey("leaf") -and $leaf.ContainsKey("non_leaf")) {
  $leafN = $leaf["leaf"].Count
  $cap = [int]($leafN * 1.5)
  if ($leaf["non_leaf"].Count -gt $cap) {
    $rng = [System.Random]::new(42)
    $all = $leaf["non_leaf"]
    $picked = [System.Collections.Generic.List[string]]::new()
    $order = 0..($all.Count - 1)
    for ($i = $order.Length - 1; $i -gt 0; $i--) {
      $j = $rng.Next($i + 1)
      $tmp = $order[$i]; $order[$i] = $order[$j]; $order[$j] = $tmp
    }
    for ($k = 0; $k -lt $cap; $k++) { $picked.Add($all[$order[$k]]) }
    $leaf["non_leaf"] = $picked
    Write-Log "Capped non_leaf to $cap (leaf=$leafN)"
  }
}

$leafTrainLeaf = Join-Path $LeafTrain "leaf"
if (Test-Path -LiteralPath $leafTrainLeaf) {
  $already = @(Get-ChildItem -LiteralPath $leafTrainLeaf -File -Force -ErrorAction SilentlyContinue).Count
  if ($already -gt 0) {
    Write-Log "leaf_gate splits already present ($already train/leaf files), skipping rebuild"
  } else {
    Write-Log "Building leaf_gate train|valid|test ..."
    Build-Splits $leaf $LeafTrain $LeafValid $LeafTest "leaf_gate"
  }
} else {
  Write-Log "Building leaf_gate train|valid|test ..."
  Build-Splits $leaf $LeafTrain $LeafValid $LeafTest "leaf_gate"
}

Write-Log "DONE"
Write-Log "Disease: $TrainRoot"
Write-Log "Leaf:    $LeafTrain"

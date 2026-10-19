param([string]$Cikti)
$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$ext = [System.WindowsRuntimeSystemExtensions].GetMethods()
$asTask1 = ($ext | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
$asTaskA = ($ext | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' })[0]
$asTaskAP = ($ext | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperationWithProgress`2' })[0]
function Bekle($op, [Type]$t) { $task = $asTask1.MakeGenericMethod($t).Invoke($null, @($op)); $task.Wait() | Out-Null; $task.Result }

[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.StorageFolder, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Editing.MediaComposition, Windows.Media.Editing, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Editing.MediaClip, Windows.Media.Editing, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Editing.BackgroundAudioTrack, Windows.Media.Editing, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.MediaProperties.MediaEncodingProfile, Windows.Media.MediaProperties, ContentType = WindowsRuntime] | Out-Null
[Windows.Media.Transcoding.TranscodeFailureReason, Windows.Media.Transcoding, ContentType = WindowsRuntime] | Out-Null

$kurgu = Get-Content -Raw -Encoding UTF8 (Join-Path $dir 'kurgu.json') | ConvertFrom-Json
$comp = New-Object Windows.Media.Editing.MediaComposition
foreach ($k in $kurgu) {
    $f = Bekle ([Windows.Storage.StorageFile]::GetFileFromPathAsync($k.png)) ([Windows.Storage.StorageFile])
    $clip = Bekle ([Windows.Media.Editing.MediaClip]::CreateFromImageFileAsync($f, [TimeSpan]::FromSeconds([double]$k.sure))) ([Windows.Media.Editing.MediaClip])
    [System.Collections.Generic.ICollection[Windows.Media.Editing.MediaClip]].GetMethod('Add').Invoke($comp.Clips, @($clip)) | Out-Null
}
$af = Bekle ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Join-Path $dir 'anlatim.wav'))) ([Windows.Storage.StorageFile])
$bat = Bekle ([Windows.Media.Editing.BackgroundAudioTrack]::CreateFromFileAsync($af)) ([Windows.Media.Editing.BackgroundAudioTrack])
[System.Collections.Generic.ICollection[Windows.Media.Editing.BackgroundAudioTrack]].GetMethod('Add').Invoke($comp.BackgroundAudioTracks, @($bat)) | Out-Null

$hedefDir = Split-Path -Parent $Cikti
$folder = Bekle ([Windows.Storage.StorageFolder]::GetFolderFromPathAsync($hedefDir)) ([Windows.Storage.StorageFolder])
$out = Bekle ($folder.CreateFileAsync((Split-Path -Leaf $Cikti), [Windows.Storage.CreationCollisionOption]::ReplaceExisting)) ([Windows.Storage.StorageFile])
$profil = [Windows.Media.MediaProperties.MediaEncodingProfile]::CreateMp4([Windows.Media.MediaProperties.VideoEncodingQuality]::HD1080p)
$profil.Video.FrameRate.Numerator = 30; $profil.Video.FrameRate.Denominator = 1
$profil.Video.Bitrate = 1500000
$op = $comp.RenderToFileAsync($out, [Windows.Media.Editing.MediaTrimmingPreference]::Precise, $profil)
$task = $asTaskAP.MakeGenericMethod([Windows.Media.Transcoding.TranscodeFailureReason], [double]).Invoke($null, @($op))
$task.Wait() | Out-Null
"sonuc: $($task.Result)  sure: $($comp.Duration)"




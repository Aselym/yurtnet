$ErrorActionPreference = 'Stop'
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$asTask = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Bekle($op, [Type]$t) {
    $task = $asTask.MakeGenericMethod($t).Invoke($null, @($op))
    $task.Wait() | Out-Null
    $task.Result
}
[Windows.Media.SpeechSynthesis.SpeechSynthesizer, Windows.Media.SpeechSynthesis, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.DataReader, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null

$syn = New-Object Windows.Media.SpeechSynthesis.SpeechSynthesizer
$ses = [Windows.Media.SpeechSynthesis.SpeechSynthesizer]::AllVoices | Where-Object { $_.Language -eq 'tr-TR' } | Select-Object -First 1
if (-not $ses) { throw 'Turkce ses yok' }
$syn.Voice = $ses
$syn.Options.SpeakingRate = 1.05

$json = Get-Content -Raw -Encoding UTF8 (Join-Path $dir 'sahneler.json') | ConvertFrom-Json
New-Item -ItemType Directory -Force (Join-Path $dir 'ses') | Out-Null
$i = 0
foreach ($s in $json) {
    $i++
    $stream = Bekle ($syn.SynthesizeTextToStreamAsync($s.metin)) ([Windows.Media.SpeechSynthesis.SpeechSynthesisStream])
    $boy = [uint32]$stream.Size
    $reader = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
    Bekle ($reader.LoadAsync($boy)) ([uint32]) | Out-Null
    $bytes = New-Object byte[] $boy
    $reader.ReadBytes($bytes)
    [IO.File]::WriteAllBytes((Join-Path $dir ('ses\{0:D2}.wav' -f $i)), $bytes)
    $reader.Dispose(); $stream.Dispose()
}
"$i ses dosyasi, ses: $($ses.DisplayName)"

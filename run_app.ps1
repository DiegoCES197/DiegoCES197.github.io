$python  = "D:\rocm711\Scripts\python.exe"
$workdir = "D:\RadiAPP"
$stdout  = "D:\RadiAPP\logs\app_out.log"
$stderr  = "D:\RadiAPP\logs\app_err.log"

"=== START APP TASK: $(Get-Date) ===" | Out-File $stdout -Append
"=== START APP TASK: $(Get-Date) ===" | Out-File $stderr -Append

Set-Location $workdir

# Ejecuta y captura salida/errores en logs
$p = Start-Process -FilePath $python -ArgumentList "D:\RadiAPP\app.py" -WorkingDirectory $workdir `
  -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru

Wait-Process -Id $p.Id
"=== APP EXITED (PID $($p.Id)) $(Get-Date) ===" | Out-File $stderr -Append

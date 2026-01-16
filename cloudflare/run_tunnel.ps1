$cloudflared = "C:\Program Files (x86)\cloudflared\cloudflared.exe"
$stdout = "D:\RadiAPP\logs\tunnel_out.log"
$stderr = "D:\RadiAPP\logs\tunnel_err.log"

$tok = "eyJhIjoiOTU2ZTQxYmEwZTA3ZjM4MTgyMThkOWY5NDBmYTk3MGYiLCJzIjoiTkROa016WXhPR0l0TnpFd05DMDBabUkwTFRnNU4ySXROVEF4WVdRMU9HTmpPRGMwIiwidCI6IjEzN2Q4OTE3LTVjZmEtNGVhMy1iNGE5LTkxZDQ2MDg2M2FjZCJ9"

$p = Start-Process -FilePath $cloudflared -ArgumentList "tunnel run --token $tok" `
  -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru

Wait-Process -Id $p.Id

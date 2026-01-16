# Detiene App
schtasks /end /tn "RadiAPP-App"

# Detiene Tunnel
schtasks /end /tn "RadiAPP-Tunnel"

# Matar procesos residuales (por si acaso)
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force

@echo off
cd /d D:\RadiAPP
start cmd /k D:\rocm711\Scripts\python.exe app.py
timeout /t 5
start cmd /k cloudflared tunnel run --token %CF_TUNNEL_TOKEN%

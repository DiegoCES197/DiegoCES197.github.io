# 🐛 Solución rápida (CPU)

## ✅ Problemas resueltos (15 enero 2026)

### 1) Error: "Prompt contained 0 image tokens but received 1 images"
**Causa**: El texto no incluye el token de imagen esperado por el tokenizer.
**Solución**: Usar `apply_chat_template` con contenido multimodal (imagen + texto).

**Verificación**:
- En logs debe aparecer: "Prompt construido con apply_chat_template".

---

### 2) Rendimiento lento en CPU
**Causas comunes**: demasiados tokens, imágenes grandes o pocos threads.

**Soluciones rápidas**:
1. Ajusta threads en `.env`:
   - `CPU_NUM_THREADS=16`
   - `CPU_INTEROP_THREADS=4`
2. Reduce `max_new_tokens` en la UI (ej. 384).
3. Baja el tamaño de imagen (ej. 768×768).

---

## 🧪 Testing rápido

```powershell
# Verificar imports
python -c "from model_loader import load_model; print('OK')"

# Verificar prompt
python tests/test_prompt.py
```

---

## 🔧 Si aún falla

### Problema: la app se queda esperando
- Reduce `max_new_tokens`
- Verifica uso de CPU en el Administrador de tareas
- Revisa `radiapp.log`

---

## ✅ Estado actual

**Backend**: ROCm (torch 2.9.0+rocmsdk20251116)
**Estado**: Estable

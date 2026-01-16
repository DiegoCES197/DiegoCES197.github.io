# 🔧 Guía de Debugging - RadiAPP

Cuando RadiAPP genera un error, se crean automáticamente archivos de log detallados para ayudarte a identificar y corregir el problema.

## 📋 Archivos de Log

### 1. **radiapp.log** (Log general)
- Eventos de la aplicación, carga de modelo, validaciones
- Nivel: INFO + DEBUG
- **Uso:** Ver el flujo general de ejecución

```bash
# Ver últimas 50 líneas
tail -50 radiapp.log

# Buscar errores específicos
grep -i "error\|warning" radiapp.log
```

### 2. **error_debug.log** (Solo errores)
- Errores detallados con traceback completo
- Stack trace de cada excepción
- Línea y archivo donde ocurrió
- **Uso:** Entender dónde exactamente falló el código

```bash
# Ver el error más reciente
type error_debug.log | tail -100
```

### 3. **error_context.json** (Contexto de error JSON)
- **Información más importante para debugging**
- Timestamp del error
- Tipo y mensaje de error
- Estado del dispositivo (GPU/CPU disponibles)
- Memoria RAM y VRAM usada
- Parámetros de entrada (modalidad, región, tokens, etc.)

```json
{
  "timestamp": "2026-01-15T13:36:24.029",
  "error_type": "ValueError",
  "error_message": "Image features and image tokens do not match",
  "device_info": {
    "cuda_available": true,
    "hip_version": "7.1.52802-561cc400e1",
    "device_count": 2,
    "torch_version": "2.9.0+rocmsdk20251116"
  },
  "memory_info": {
    "process_rss_mb": 8234.5,
    "gpu_0_allocated_mb": 4096.2,
    "gpu_0_reserved_mb": 5120.0
  },
  "context": {
    "modalidad": "TC",
    "region": "Cráneo",
    "template_file": "TC_craneo_simple.json",
    "max_new_tokens": 384
  }
}
```

## 🔍 Errores Comunes y Soluciones

### Error: "Image features and image tokens do not match"
**Causa:** Los tokens de imagen no se insertan correctamente en el prompt
**Solución:** Verificar que `expected_token` está en `prompt_text` antes de procesar
**En log:** Buscar `"Token de imagen insertado"` o `"Inputs construidos"`

### Error: "GPU OOM" (Out of Memory)
**Causa:** VRAM insuficiente para el modelo + imagen
**Solución:** 
- Reduce `DEFAULT_MAX_TOKENS` en `config.py` (512 → 300)
- Reduce `MAX_IMAGE_SIZE` (896 → 512)
- Usa `device_map="auto"` (ya está activado)
**En log:** Buscar `"GPU {i}: Allocated="`

### Error: "Validation error: No se pudo procesar imagen"
**Causa:** Imagen corrupta o formato inválido
**Solución:** 
- Verificar que es JPG/PNG válido
- Comprobar que no es imagen en blanco/negro extrema
**En log:** Buscar `"validate_image_quality"`

### Error: "HF_TOKEN no encontrado"
**Causa:** Variable de entorno `.env` no configurada
**Solución:** 
- Crear `.env` en raíz de RadiAPP
- Agregar: `HF_TOKEN=hf_tu_token_aqui`
**En log:** Buscar `"HF_TOKEN detectado"`

## 📊 Pasos de Debugging

1. **Lee el UI error message** → Te dice qué pasó
2. **Abre `error_context.json`** → Ve qué parámetros causaron el error
3. **Busca en `radiapp.log`** → Sigue el flujo hasta donde falló
4. **Verifica `error_debug.log`** → Lee el traceback completo
5. **Identifica patrón** → ¿Solo con ciertos parámetros? ¿Siempre?

## 💡 Tips Prácticos

- **Para debugging rápido:** Abre `error_context.json` en VS Code, verás JSON con colores
- **Para ver en tiempo real:** `tail -f radiapp.log` en terminal
- **Para buscar patrón:** `grep "model_loader" radiapp.log | grep -i "error"`
- **Para ver resumen:** Abre 3 pestañas en terminal:
  ```powershell
  # Terminal 1: seguir logs generales
  tail -f radiapp.log
  
  # Terminal 2: seguir solo errores
  tail -f error_debug.log
  
  # Terminal 3: ver contexto (se actualiza cuando hay error)
  cat error_context.json
  ```

## 🎯 Información Más Útil

Si necesitas reportar un bug:
1. Copia **error_context.json** (tiene todo lo necesario)
2. Copia **últimas 100 líneas de error_debug.log**
3. Describe qué parámetros usaste (modalidad, región, imagen)

Con estos 3 datos, es muy fácil identificar y corregir el problema.

---

**Nota:** Los archivos de log se crean automáticamente. No necesitas hacer nada especial. Solo asegúrate de que RadiAPP tiene permiso de escritura en su carpeta.

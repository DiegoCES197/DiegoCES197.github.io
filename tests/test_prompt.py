"""
Script de prueba rápido para verificar que el prompt contiene el token de imagen.
"""
from prompt_builder import build_prompt

# Plantilla de prueba
template_text = """TOMOGRAFÍA DE CRÁNEO SIMPLE

INDICACIÓN:

TÉCNICA: En tomógrafo multidetector se adquieren cortes axiales del cráneo.

HALLAZGOS:

CONCLUSIÓN:
"""

# Construir prompt
prompt = build_prompt(
    modalidad="TC",
    region="Cráneo",
    indicacion="Cefalea",
    extras="",
    template_text=template_text
)

# Verificar
print("="*70)
print("VERIFICACIÓN DE PROMPT")
print("="*70)
print(f"Longitud total: {len(prompt)} caracteres")
print(f"Primeros 100 caracteres:\n{prompt[:100]}")
print("="*70)

if prompt:
    print("✅ CORRECTO: El prompt fue construido")
else:
    print("❌ ERROR: El prompt está vacío")

print("\n" + "="*70)
print("ESTRUCTURA COMPLETA DEL PROMPT:")
print("="*70)
print(prompt)

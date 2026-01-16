"""
Constructor de prompts para MedGemma
Maneja few-shot learning, ejemplos buenos del usuario, y contexto por modalidad
"""
import json
import os
from typing import List, Dict
from config import FEWSHOT_EXAMPLES, MODALIDAD_PROMPTS, GOOD_EXAMPLES_FILE, IMAGE_TOKEN


def _normalize_examples(examples: List[Dict]) -> List[Dict]:
    """
    Normaliza ejemplos para que tengan el esquema {"label": ..., "example": {...}}.
    Mantiene compatibilidad con ejemplos antiguos guardados sin la key "example".
    """
    normalized: List[Dict] = []
    for ex in examples:
        if not isinstance(ex, dict):
            continue
        if "example" in ex and isinstance(ex.get("example"), dict):
            normalized.append(ex)
            continue
        label = ex.get("label", "Ejemplo")
        example_data = {k: v for k, v in ex.items() if k != "label"}
        normalized.append({"label": label, "example": example_data})
    return normalized


def load_good_examples() -> List[Dict]:
    """Carga ejemplos aprobados por el usuario."""
    if os.path.exists(GOOD_EXAMPLES_FILE):
        with open(GOOD_EXAMPLES_FILE, "r", encoding="utf-8") as f:
            return _normalize_examples(json.load(f))
    return _normalize_examples(FEWSHOT_EXAMPLES)


def save_good_example(example: Dict):
    """Guarda un nuevo ejemplo aprobado."""
    examples = load_good_examples()
    normalized = _normalize_examples([example])
    if normalized:
        examples.append(normalized[0])
    with open(GOOD_EXAMPLES_FILE, "w", encoding="utf-8") as f:
        json.dump(examples, f, ensure_ascii=False, indent=2)


def get_prompt_by_modalidad(modalidad: str) -> str:
    """Retorna instrucciones específicas según modalidad."""
    return MODALIDAD_PROMPTS.get(modalidad, MODALIDAD_PROMPTS["Otro"])


def format_fewshot_prompt(examples: List[Dict]) -> str:
    """
    Formatea ejemplos few-shot para incluir en el prompt.
    Prioriza ejemplos del usuario (los últimos agregados) para máximo aprendizaje.
    """
    text = "\n📚 EJEMPLOS (MedGemma aprende de estos patrones):\n"
    text += "="*70 + "\n"
    
    # Mostrar últimos 2 ejemplos (más relevantes = user examples más recientes)
    best_examples = examples[-2:] if len(examples) > 2 else examples
    
    for i, ex in enumerate(best_examples, 1):
        label = ex.get('label', f'Ejemplo {i}')
        example_data = ex.get('example', ex)
        text += f"\nEJEMPLO {i}: {label}\n"
        text += json.dumps(example_data, ensure_ascii=False, indent=2)
        text += "\n" + "-"*70
    
    return text


def build_prompt(modalidad: str, region: str, indicacion: str, extras: str, template_text: str, image_token: str = IMAGE_TOKEN) -> str:
    """
    Construye prompt SIMPLIFICADO pero efectivo para MedGemma 4B.
    Menos texto innecesario, más enfoque en JSON directo.
    
    Args:
        modalidad: Tipo de estudio (TC, RM, RX, US, Otro)
        region: Región anatómica
        indicacion: Indicación clínica
        extras: Notas adicionales
        template_text: Plantilla a editar
    
    Returns:
        str: Prompt completo para el modelo
    """
    good_examples = load_good_examples()
    fewshot_section = format_fewshot_prompt(good_examples)
    modalidad_guide = get_prompt_by_modalidad(modalidad)
    
    # Si image_token es None, usar IMAGE_TOKEN por defecto.
    # Si image_token es "" (cadena vacía), no insertar token en el prompt.
    token = IMAGE_TOKEN if image_token is None else image_token
    token_prefix = f"{token}\n\n" if token else ""

    return f"""{token_prefix}

TAREA: Eres radiólogo. Edita esta plantilla basándote en la imagen. Devuelve SOLO JSON válido dentro de un bloque ```json```.

PLANTILLA A EDITAR:
--- PLANTILLA ---
{template_text}
--- FIN PLANTILLA ---

INSTRUCCIONES CRÍTICAS:
- Elimina líneas que contradicen la imagen (remove)
- Reemplaza lo incorrecto (replace)
- Agrega hallazgos anormales nuevos (add_findings)
- Si no ves algo → regístralo en "lesiometro_missing"
- Conclusión: solo positivo/anormal, NUNCA diagnóstico definitivo
- NO inventes medidas, edad, contraste, etc.

CONTEXTO:
- Modalidad: {modalidad}
- Región: {region}
- Indicación: {indicacion}
- Extras: {extras}

{modalidad_guide}

EJEMPLOS A SEGUIR:
{fewshot_section}

DEVUELVE JSON EXACTO (SIN EXPLICACIONES) y formátalo como bloque de código:
```json
{{"remove":[],"replace":[],"add_findings":[],"lesiometro_missing":[],"confidence_scores":{{}},"conclusion":{{"positives":[],"impression":[],"ddx":[],"recommendations":[]}}}}
```

ESQUEMA JSON COMPLETO (referencia):
```json
{{
    "remove": ["línea exacta a eliminar"],
    "replace": [{{"from": "incorrecto", "to": "correcto"}}],
    "add_findings": ["hallazgo 1", "hallazgo 2"],
    "lesiometro_missing": ["componente no evaluable"],
    "confidence_scores": {{"finding1": 0.95, "finding2": 0.6}},
    "conclusion": {{
        "positives": ["solo anormales"],
        "impression": ["probabilístico"],
        "ddx": ["dx1", "dx2"],
        "recommendations": ["correlación clínica"]
    }}
}}
```
"""


def build_repair_prompt(generated_text: str, template_text: str) -> str:
    """
    Construye un prompt para convertir una salida no-JSON en JSON válido de ediciones.
    """
    return f"""
TAREA: Convierte el borrador de informe en un JSON de ediciones sobre la plantilla.
Devuelve SOLO JSON válido, sin explicaciones, formateado como bloque ```json```.
Si no puedes, devuelve EXACTAMENTE este JSON mínimo:
```json
{{"remove":[],"replace":[],"add_findings":[],"lesiometro_missing":[],"confidence_scores":{{}},"conclusion":{{"positives":[],"impression":[],"ddx":[],"recommendations":[]}}}}
```

PLANTILLA A EDITAR:
--- PLANTILLA ---
{template_text}
--- FIN PLANTILLA ---

BORRADOR DEL MODELO (PARA CONVERTIR):
--- BORRADOR ---
{generated_text}
--- FIN BORRADOR ---

DEVUELVE JSON EXACTO (SIN EXPLICACIONES):
```json
{{
    "remove": ["línea exacta a eliminar"],
    "replace": [{{"from": "incorrecto", "to": "correcto"}}],
    "add_findings": ["hallazgo 1", "hallazgo 2"],
    "lesiometro_missing": ["componente no evaluable"],
    "confidence_scores": {{"finding1": 0.95, "finding2": 0.6}},
    "conclusion": {{
        "positives": ["solo anormales"],
        "impression": ["probabilístico"],
        "ddx": ["dx1", "dx2"],
        "recommendations": ["correlación clínica"]
    }}
}}
```
"""

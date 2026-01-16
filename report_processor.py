"""
Procesamiento de reportes radiológicos
Validación de imágenes, parsing JSON, edición de plantillas, auditoría
"""
import re
import json
import numpy as np
from typing import Dict, Any, List, Tuple
from PIL import Image


# ============================================================================
# VALIDACIÓN DE IMAGEN
# ============================================================================

def validate_image_quality(img: Image.Image) -> Tuple[bool, str]:
    """
    Valida calidad de imagen antes de procesar.
    Detecta imágenes corruptas, muy oscuras, o sobreexpuestas.
    """
    array = np.array(img)
    
    # Check 1: Imagen no principalmente negra
    mean = np.mean(array)
    if mean < 20:
        return False, "⚠️ Imagen demasiado oscura"

    # Check 2: Imagen no principalmente blanca
    if mean > 240:
        return False, "⚠️ Imagen demasiado clara/sobreexpuesta"

    # Check 3: Imagen no totalmente uniforme
    std = np.std(array)
    if std < 5:
        return False, "⚠️ Imagen muy uniforme o corrupta (sin contraste)"
    
    return True, ""


# ============================================================================
# PARSING Y EXTRACCIÓN JSON
# ============================================================================

def extract_json_block(text: str) -> str:
    """
    Extrae el primer bloque JSON {...} del texto.
    Útil cuando el modelo añade texto extra antes/después del JSON.
    """
    # 1) Intentar bloque en markdown ```json ... ```
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)

    # 2) Intentar encontrar un JSON con balanceo de llaves
    start = text.find("{")
    if start == -1:
        raise ValueError("No se encontró un JSON en la salida del modelo.")

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue

        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]

    raise ValueError("No se encontró un JSON balanceado en la salida del modelo.")


# ============================================================================
# APLICACIÓN DE EDICIONES JSON
# ============================================================================

def apply_edits(template_text: str, edits_json: str) -> str:
    """
    Aplica ediciones JSON sobre plantilla.
    Soporta: remove, replace, add_findings, confidence_scores, conclusion.
    """
    data = json.loads(edits_json)
    lines = template_text.splitlines()

    # 1) REMOVE exact lines
    remove_set = set((s or "").strip() for s in data.get("remove", []) if isinstance(s, str))
    if remove_set:
        lines = [ln for ln in lines if ln.strip() not in remove_set]

    # 2) REPLACE exact lines
    for rep in data.get("replace", []):
        if not isinstance(rep, dict):
            continue
        frm = (rep.get("from") or "").strip()
        to = (rep.get("to") or "").strip()
        if not frm or not to:
            continue
        lines = [to if ln.strip() == frm else ln for ln in lines]

    # 3) ADD findings after HALLAZGOS: (con confidence annotation si aplica)
    adds = [(a or "").strip() for a in data.get("add_findings", []) if isinstance(a, str) and (a or "").strip()]
    confidence_scores = data.get("confidence_scores", {})
    
    if adds:
        inserted = False
        for i, ln in enumerate(lines):
            if ln.strip().upper().startswith("HALLAZGOS"):
                # Anotar hallazgos con confianza baja
                annotated_adds = []
                for finding in adds:
                    # Buscar key en confidence_scores
                    conf = 1.0
                    for key, val in confidence_scores.items():
                        if key.lower() in finding.lower():
                            conf = val
                            break
                    
                    if conf < 0.5:
                        annotated_adds.append(f"{finding} [⚠️ BAJA CONFIANZA: {conf:.0%}]")
                    else:
                        annotated_adds.append(finding)
                
                lines = lines[:i+1] + annotated_adds + lines[i+1:]
                inserted = True
                break
        if not inserted:
            lines += [""] + adds

    # 4) CONCLUSION
    concl_obj = data.get("conclusion")
    global_missing = data.get("lesiometro_missing")
    if isinstance(concl_obj, dict) and isinstance(global_missing, list) and "lesiometro_missing" not in concl_obj:
        concl_obj["lesiometro_missing"] = global_missing

    if isinstance(concl_obj, dict):
        concl_text = format_conclusion_block(concl_obj)
    elif isinstance(concl_obj, str):
        concl_text = concl_obj.strip()
    else:
        concl_text = ""

    if concl_text:
        out_lines = []
        in_conclusion = False
        for ln in lines:
            if ln.strip().upper().startswith("CONCLUSIÓN"):
                in_conclusion = True
                out_lines.append(ln)
                out_lines.append(concl_text)
                continue
            if in_conclusion:
                if ln.strip().endswith(":") and not ln.strip().upper().startswith("CONCLUSIÓN"):
                    in_conclusion = False
                    out_lines.append(ln)
                else:
                    continue
            else:
                out_lines.append(ln)
        lines = out_lines

    return "\n".join(lines)


def format_conclusion_block(concl_obj: Dict[str, Any]) -> str:
    """
    Formatea conclusión clínica: SOLO positivo/anormal + impresión + ddx + sugerencias.
    """
    positives = concl_obj.get("positives") or []
    impression = concl_obj.get("impression") or []
    ddx = concl_obj.get("ddx") or []
    recs = concl_obj.get("recommendations") or []
    missing = concl_obj.get("lesiometro_missing") or []

    out: List[str] = []

    # SOLO positivos/anormales
    positives = [p.strip() for p in positives if isinstance(p, str) and p.strip()]
    if positives:
        out.append("Hallazgos positivos:")
        out += [f"- {p}" for p in positives]

    impression = [p.strip() for p in impression if isinstance(p, str) and p.strip()]
    if impression:
        out.append("Impresión:")
        out += [f"- {p}" for p in impression]

    ddx = [p.strip() for p in ddx if isinstance(p, str) and p.strip()]
    if ddx:
        out.append("Diagnósticos probables (diferencial):")
        out += [f"- {p}" for p in ddx]

    recs = [p.strip() for p in recs if isinstance(p, str) and p.strip()]
    if recs:
        out.append("Sugerencias:")
        out += [f"- {p}" for p in recs]

    missing = [p.strip() for p in missing if isinstance(p, str) and p.strip()]
    if missing:
        out.append("Elementos del LESIÓMETRO no caracterizables en la imagen aportada:")
        out += [f"- {p}" for p in missing]

    return "\n".join(out).strip()


# ============================================================================
# ANÁLISIS DE INCERTIDUMBRE
# ============================================================================

def analyze_uncertainty_tokens(text: str, json_output: Dict) -> Dict[str, float]:
    """
    Análisis de tokens de incertidumbre en hallazgos.
    Marcas probabilísticas indican baja confianza.
    """
    uncertainty_markers = [
        ("podría", 0.6),
        ("posible", 0.65),
        ("probable", 0.7),
        ("sugiere", 0.75),
        ("compatible", 0.8),
        ("compatible con", 0.8),
        ("parece", 0.65),
        ("posiblemente", 0.60),
        ("al parecer", 0.65),
    ]
    
    uncertainty_scores = {}
    
    # Analizar cada hallazgo
    findings = json_output.get("add_findings", [])
    for finding in findings:
        score = 0.95  # default confianza alta
        for marker, val in uncertainty_markers:
            if marker.lower() in finding.lower():
                score = min(score, val)
        
        # Usar primeras 3 palabras como key
        key = " ".join(finding.split()[0:3])
        uncertainty_scores[key] = score
    
    # Actualizar o crear confidence_scores
    if "confidence_scores" not in json_output:
        json_output["confidence_scores"] = {}
    
    json_output["confidence_scores"].update(uncertainty_scores)
    return json_output


# ============================================================================
# AUDITORÍA Y VALIDACIÓN
# ============================================================================

def audit_report_internal(final_report: str, template_text: str, hallazgos_added: bool) -> str:
    """
    Auditoría ACTIVA: analiza coherencia, omisiones, lenguaje.
    Se ejecuta automáticamente antes de devolver al usuario.
    """
    audit_flags = []
    
    # 1) COHERENCIA: ¿Hay hallazgos pero conclusión vacía?
    has_findings = "HALLAZGOS:" in final_report and len(final_report.split("HALLAZGOS:")[1].split("CONCLUSIÓN")[0].strip()) > 10
    conclusion_section = final_report.split("CONCLUSIÓN:")[-1].strip() if "CONCLUSIÓN:" in final_report else ""
    
    if has_findings and (not conclusion_section or len(conclusion_section) < 20):
        audit_flags.append("⚠️ AUDITORÍA: Hallazgos descritos pero conclusión muy breve")
    
    # 2) OMISIONES: comparación con previos
    if has_findings and "previo" not in final_report.lower() and "prior" not in final_report.lower():
        audit_flags.append("⚠️ AUDITORÍA: Menciona 'comparación con previos' si aplica")
    
    # 3) LENGUAJE: ¿muy definitivo?
    definitive_patterns = [
        r"\bes\b\s+\w+\s+(tumor|cáncer|neoplasia|malignidad)",
        r"\bdiagnóstico de\b",
        r"\bse diagnostica\b",
        r"\bconfirmado\b"
    ]
    definitive_count = sum(1 for pat in definitive_patterns if re.search(pat, final_report, re.IGNORECASE))
    if definitive_count > 0:
        audit_flags.append("⚠️ AUDITORÍA: Lenguaje muy definitivo. Usa: 'compatible con', 'sugiere', 'probable'")
    
    # 4) MEDIDAS: ¿tamaños específicos?
    if has_findings and not re.search(r"\d+\s*(mm|cm|x)", final_report):
        audit_flags.append("💡 AUDITORÍA: Incluye medidas específicas (mm/cm) si aplica")
    
    # 5) TRATAMIENTO: NO permitido
    treatment_patterns = [r"\btratar\b", r"\bcirugía\b", r"\bretinol\b", r"\bquimio", r"\bbiopsia"]
    if any(re.search(pat, final_report, re.IGNORECASE) for pat in treatment_patterns):
        audit_flags.append("❌ AUDITORÍA: Detectado lenguaje de tratamiento (fuera de alcance)")
    
    # 6) DDX: ¿incluye diferencial?
    if has_findings and "diagnóstico" not in conclusion_section.lower() and "probable" not in conclusion_section.lower():
        audit_flags.append("💡 AUDITORÍA: Incluye un diferencial diagnóstico breve")
    
    # 7) LIMITACIONES: ¿técnicas?
    if has_findings and "limitación" not in final_report.lower() and "calidad" not in final_report.lower():
        audit_flags.append("💡 AUDITORÍA: Menciona limitaciones técnicas si las hay")
    
    # 8) HALLAZGOS de baja confianza: ¿marcados?
    if "baja confianza" in final_report:
        audit_flags.append("⚠️ AUDITORÍA: Hallazgos de baja confianza marcados - revisar criterios de inclusión")
    
    # Formato salida
    if audit_flags:
        audit_section = "\n\n" + "="*70 + "\n🔍 AUDITORÍA INTERNA (AUTO-VALIDACIÓN)\n" + "="*70 + "\n"
        audit_section += "\n".join(audit_flags) + "\n" + "="*70
        return final_report + audit_section
    else:
        return final_report + "\n\n✅ AUDITORÍA: Sin flags detectados."


def multi_turn_refinement(final_report: str, json_output: Dict[str, Any], template_text: str, img: Image.Image) -> Tuple[str, Dict]:
    """
    Multi-turn: análisis de completitud.
    Detecta si el análisis parece incompleto o con baja confianza.
    """
    flags = []
    
    # Check 1: ¿LESIÓMETRO muy incompleto?
    missing = json_output.get("lesiometro_missing", [])
    if len(missing) > 3:
        flags.append("⚠️ Muchos componentes del LESIÓMETRO no evaluables - imagen limitante")
    
    # Check 2: ¿Confianza muy baja?
    confidence = json_output.get("confidence_scores", {})
    low_conf = sum(1 for v in confidence.values() if v < 0.5)
    if low_conf > 2:
        flags.append("⚠️ Múltiples hallazgos con baja confianza (<50%)")
    
    # Check 3: ¿DDX vacío o genérico?
    ddx = json_output.get("conclusion", {}).get("ddx", [])
    if not ddx or len(ddx) == 1:
        flags.append("💡 Diferencial muy breve - considera más opciones")
    
    if flags:
        info_section = "\n\n" + "="*70 + "\n📊 ANÁLISIS DE COMPLETITUD\n" + "="*70 + "\n"
        info_section += "\n".join(flags) + "\n" + "="*70
        return final_report + info_section, json_output
    
    return final_report, json_output

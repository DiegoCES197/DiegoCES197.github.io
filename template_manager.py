"""
Gestión de plantillas radiológicas
CRUD: crear, leer, actualizar, importar (TXT/DOCX/JSON)
"""
import os
import json
from typing import List, Dict, Any, Tuple
from docx import Document
from config import TEMPLATES_DIR


def list_templates() -> List[str]:
    """Lista todas las plantillas JSON disponibles."""
    return sorted([f for f in os.listdir(TEMPLATES_DIR) if f.lower().endswith(".json")])


def read_template(filename: str) -> Dict[str, Any]:
    """Lee una plantilla JSON."""
    with open(os.path.join(TEMPLATES_DIR, filename), "r", encoding="utf-8") as f:
        return json.load(f)


def write_template(filename: str, data: Dict[str, Any]) -> str:
    """Escribe una plantilla JSON."""
    if not filename.lower().endswith(".json"):
        filename += ".json"
    with open(os.path.join(TEMPLATES_DIR, filename), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return filename


def text_from_docx(path: str) -> str:
    """Extrae texto de un archivo DOCX."""
    doc = Document(path)
    lines = []
    for p in doc.paragraphs:
        t = p.text.strip()
        if t:
            lines.append(t)
    return "\n".join(lines).strip()


def import_template(file_obj: Any) -> Tuple[str, str]:
    """
    Importa plantilla desde TXT, DOCX o JSON.
    
    Returns:
        tuple: (name, template_text)
    """
    path = file_obj.name
    ext = os.path.splitext(path)[1].lower()

    if ext == ".txt":
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            txt = f.read().strip()
        name = os.path.basename(path).replace(".txt", "")
        return name, txt

    if ext == ".docx":
        txt = text_from_docx(path)
        name = os.path.basename(path).replace(".docx", "")
        return name, txt

    if ext == ".json":
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("name", os.path.basename(path).replace(".json", "")), data.get("template_text", "")

    raise ValueError("Formato no soportado. Usa .txt, .docx o .json")


def create_default_template():
    """Crea plantilla por defecto si no existe ninguna."""
    if not list_templates():
        default_tc = """TOMOGRAFÍA DE CRÁNEO SIMPLE

INDICACIÓN:

TÉCNICA: En tomógrafo multidetector se adquieren cortes axiales del cráneo, se incluyen reconstrucciones multiplanares.

DOSIS DE RADIACIÓN: mSv.

HALLAZGOS:

CONCLUSIÓN:
"""
        write_template("TC_craneo_simple.json", {"name":"TC_craneo_simple", "template_text": default_tc})

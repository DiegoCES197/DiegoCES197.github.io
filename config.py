"""
Configuración global de RadiAPP
Constantes, paths, ejemplos few-shot, criterios diagnósticos
Soporte de variables de entorno mediante .env
"""
import os
from pathlib import Path

# ============================================================================
# CARGA DE VARIABLES DE ENTORNO (.env)
# ============================================================================

def _load_dotenv_file(env_path: Path) -> str:
    """Carga un archivo .env simple sin dependencias externas."""
    if not env_path.exists():
        return "Archivo .env no encontrado. Usando valores por defecto."

    try:
        with env_path.open("r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        return "Variables de entorno cargadas desde .env"
    except Exception:
        return "No se pudo cargar .env. Usando valores por defecto."


def get_env(name, default=None, cast=None):
    """Obtiene variable de entorno o retorna default; castea si se indica."""
    value = os.getenv(name)
    if value in (None, ""):
        return default
    if cast:
        try:
            return cast(value)
        except Exception:
            return default
    return value


# ============================================================================
# RUTAS BASE
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
logger_env_msg = _load_dotenv_file(BASE_DIR / ".env")
TEMPLATES_DIR = BASE_DIR / "templates"
FEEDBACK_DIR = BASE_DIR / "feedback"
GOOD_EXAMPLES_FILE = FEEDBACK_DIR / "good_examples.json"
FEEDBACK_CSV = FEEDBACK_DIR / "feedback.csv"

# Crear directorios si no existen
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(FEEDBACK_DIR, exist_ok=True)


# ============================================================================
# MODELO
# ============================================================================

MODEL_ID = get_env("MODEL_ID", "google/medgemma-1.5-4b-it")
HF_TOKEN = get_env("HF_TOKEN", get_env("HUGGINGFACE_HUB_TOKEN", None))
IMAGE_TOKEN = get_env("IMAGE_TOKEN", "<image>")
VALID_IMAGE_TOKENS = ("<image>", "<start_of_image>", "<image_soft_token>")
MODEL_DTYPE = get_env("MODEL_DTYPE", "float16")
CPU_DTYPE = get_env("CPU_DTYPE", "float32")
CPU_NUM_THREADS = get_env("CPU_NUM_THREADS", os.cpu_count() or 1, lambda v: int(v))
CPU_INTEROP_THREADS = get_env("CPU_INTEROP_THREADS", max(1, min(4, (os.cpu_count() or 1) // 2)), lambda v: int(v))


# ============================================================================
# CONFIGURACIÓN DE GENERACIÓN
# ============================================================================

# Máximo tamaño de imagen (pixels)
MAX_IMAGE_WIDTH = get_env("MAX_IMAGE_WIDTH", 896, int)
MAX_IMAGE_HEIGHT = get_env("MAX_IMAGE_HEIGHT", 896, int)
MAX_IMAGE_SIZE = (MAX_IMAGE_WIDTH, MAX_IMAGE_HEIGHT)

# Tokens por defecto y límites
DEFAULT_MAX_TOKENS = get_env("DEFAULT_MAX_TOKENS", 512, int)
MIN_MAX_TOKENS = get_env("MIN_MAX_TOKENS", 300, int)
MAX_MAX_TOKENS = get_env("MAX_MAX_TOKENS", 600, int)
MAX_MAX_TOKENS_UNLIMITED = get_env("MAX_MAX_TOKENS_UNLIMITED", 2048, int)
MAX_TIME_SECONDS = get_env("MAX_TIME_SECONDS", 180, int)
TOKEN_STEP = get_env("TOKEN_STEP", 32, int)

# Modalidades soportadas
SUPPORTED_MODALITIES = ["RX", "TC", "RM", "US", "Otro"]

# Validación
MIN_REGION_LENGTH = get_env("MIN_REGION_LENGTH", 2, int)
VALID_TEMPLATE_EXTENSIONS = [".json"]

# Debug mode
DEBUG_MODE = get_env("DEBUG_MODE", False, lambda v: str(v).lower() in ("1", "true", "yes", "on"))


# ============================================================================
# REGLAS PARA EL MODELO
# ============================================================================

RULES = """Eres un asistente de radiología.
Reglas:
- Describe hallazgos y redacta borradores estructurados.
- NO des diagnóstico definitivo.
- Puedes sugerir correlación clínica o comparación con previos cuando sea razonable.
- Si algo es incierto, dilo con lenguaje probabilístico.
- NO recomiendes tratamiento.
- NO inventes datos no proporcionados (edad, contraste, dosis, etc.).
Salida en español, respetando el formato de la plantilla.
"""


# ============================================================================
# BASE DE DATOS DE HALLAZGOS POR MODALIDAD Y REGIÓN
# ============================================================================

COMMON_FINDINGS = {
    "TC_craneo": [
        "edema cerebral", "hemorragia intracraneal", "fractura",
        "lesión expansiva", "infarto isquémico", "aneurisma", "trombosis venosa"
    ],
    "TC_torax": [
        "consolidación", "derrame pleural", "neumotórax", "nódulo pulmonar",
        "empiema", "atelectasia", "enfisema subcutáneo"
    ],
    "RX_torax": [
        "consolidación", "derrame pleural", "neumotórax", "nódulo",
        "cardiomegalia", "atelectasia", "patrón reticular"
    ],
    "RX_abdomen": [
        "niveles hidroaéreos", "libre", "obstrucción", "megacolon",
        "neumoperitoneo", "ascitis", "calcificaciones"
    ],
    "RM_cerebro": [
        "lesión T2/FLAIR hiperintensa", "restricción DWI", "edema vasogénico",
        "realce con gadolinio", "atrofia", "gliosis"
    ]
}


# ============================================================================
# CRITERIOS DIAGNÓSTICOS (Fleischner, RECIST, ACR)
# ============================================================================

DIAGNOSTIC_CRITERIA = {
    "fleischner_nodule_size": {
        "categoria_1": ("< 6mm", "Sin seguimiento"),
        "categoria_2": ("6-8mm", "TC 12 meses; si > 1: 6-8 sem"),
        "categoria_3": ("8-30mm", "TC 6 meses; si crece: biopsia/resección"),
        "categoria_4": ("> 30mm", "Biopsia o resección"),
    },
    "recist_target": {
        "baseline": "Suma diámetros largos ≤ 10 lesiones",
        "response": "Reducción ≥ 30% = respuesta parcial",
        "progression": "Aumento ≥ 20% o nueva lesión = progresión",
    },
    "acr_thyroid": {
        "TR_1": "No requiere seguimiento",
        "TR_2": "< 6 meses si hay factores de riesgo",
        "TR_3": "Ecografía en 6-12 meses o PAAF",
        "TR_4": "Considerar PAAF",
        "TR_5": "PAAF recomendado",
    }
}


# ============================================================================
# FEW-SHOT EXAMPLES (ejemplos base)
# ============================================================================

FEWSHOT_EXAMPLES = [
    {
        "label": "TC craneal con hematoma epidural agudo",
        "example": {
            "remove": ["Sin hallazgos relevantes"],
            "replace": [{"from": "Ventrículos normales", "to": "Ventrículos ligeramente comprimidos por efecto de masa"}],
            "add_findings": ["Hematoma epidural derecho temporoparietal de 12 mm de espesor máximo con efecto de masa", "Desviación de línea media de ~3 mm"],
            "lesiometro_missing": ["Comportamiento exacto respecto a duramadre (TC sin contraste limitante)"],
            "conclusion": {
                "positives": ["Hematoma epidural agudo derecho temporoparietal"],
                "impression": ["Hallazgo compatible con trauma craneoencefálico"],
                "ddx": ["Hematoma epidural (diagnóstico con criterios radiológicos)"],
                "recommendations": ["Correlacionar clínica con escala Glasgow", "Considerar RM para definir mejor interfaz duramadre-hematoma"]
            }
        }
    },
    {
        "label": "RX tórax con consolidación basal",
        "example": {
            "remove": [],
            "replace": [],
            "add_findings": ["Consolidación alveolar en base pulmonar izquierda de distribución segmentaria"],
            "lesiometro_missing": ["Comportamiento post-contraste", "Presencia de broncograma aéreo"],
            "conclusion": {
                "positives": ["Consolidación basal izquierda"],
                "impression": ["Patrón compatible con neumonía adquirida en la comunidad o proceso inflamatorio agudo"],
                "ddx": ["Neumonía bacteriana", "Neumonitis viral", "Infarto pulmonar"],
                "recommendations": ["Correlacionar con sintomatología clínica y marcadores de inflamación"]
            }
        }
    }
]


# ============================================================================
# DESCRIPTORES POR MODALIDAD
# ============================================================================

MODALIDAD_PROMPTS = {
    "TC": """DESCRIPTORES CRÍTICOS PARA TC:
- Densidad en Unidades Hounsfield (UH) si es relevante
- Realce post-contraste (si aplica: arterial, portal, portal tardío)
- Patrón de distribución (segmentario, lobar, difuso)
- Efecto de masa y desplazamiento de estructuras adyacentes
- Bordes (bien definidos vs infiltrantes)
""",
    "RM": """DESCRIPTORES CRÍTICOS PARA RM:
- Señal T1 (hipointensa, isointensa, hiperintensa)
- Señal T2/FLAIR (hiper/hipointensa)
- Restricción en DWI (si hay)
- Realce con gadolinio (patrón: periférico, homogéneo, progresivo)
- Cambios en espectroscopia si está disponible
""",
    "RX": """DESCRIPTORES CRÍTICOS PARA RX:
- Densidad radiológica (vidrio esmerilado, consolidación, cavitación)
- Distribución (segmentaria, lobar, difusa)
- Presencia de broncograma aéreo
- Bordes (nítidos vs mal definidos)
- Localización precisa (lóbulo, segmento, región)
""",
    "US": """DESCRIPTORES CRÍTICOS PARA ECOGRAFÍA:
- Ecogenicidad (hipoecogénico, isoecogénico, hiperecoico)
- Compresibilidad y elastografía si aplica
- Vascularidad en Doppler (si disponible)
- Cambios dinámicos con maniobras
""",
    "Otro": """DESCRIPTORES ESTÁNDAR:
- Localización precisa
- Morfología y tamaño
- Densidad/señal/ecogenicidad
- Bordes y relaciones
- Cambios respecto a estudios previos
"""
}

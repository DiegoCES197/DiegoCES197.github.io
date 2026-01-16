"""
Carga del modelo MedGemma en CPU optimizada
"""
import logging
from typing import Tuple, Dict, Any
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from config import MODEL_ID, MODEL_DTYPE, CPU_DTYPE, HF_TOKEN

# Configurar logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Variable global que indica si el modelo está en GPU
USE_DML = False

# Device global
DEVICE = "cpu"

# Información del modelo cargado
MODEL_INFO = {
    "backend": "uninitialized",
    "device_name": "",
    "dtype": None,
}

# ============================================================================
# CARGA DEL MODELO
# ============================================================================

def load_model() -> Tuple[Any, AutoProcessor, bool]:
    """Carga MedGemma en GPU (ROCm) si está disponible; fallback a CPU."""
    global USE_DML, DEVICE

    logger.info("Iniciando carga de modelo MedGemma...")
    if HF_TOKEN:
        logger.info("HF_TOKEN detectado: usando autenticación para Hugging Face")

    def _raise_auth_help(err: Exception) -> None:
        msg = str(err)
        if any(key in msg for key in ["gated repo", "gated", "401", "restricted", "Access to model", "Please log in"]):
            raise RuntimeError(
                "No se pudo acceder al modelo restringido. "
                "Solicita acceso en https://huggingface.co/google/medgemma-1.5-4b-it y "
                "configura el token con HF_TOKEN (o HUGGINGFACE_HUB_TOKEN) en .env."
            ) from err
        raise RuntimeError(f"No se pudo cargar el processor: {err}") from err

    def _raise_model_help(err: Exception) -> None:
        msg = str(err)
        if any(key in msg for key in ["gated repo", "gated", "401", "restricted", "Access to model", "Please log in"]):
            raise RuntimeError(
                "No se pudo acceder al modelo restringido. "
                "Solicita acceso en https://huggingface.co/google/medgemma-1.5-4b-it y "
                "configura el token con HF_TOKEN (o HUGGINGFACE_HUB_TOKEN) en .env."
            ) from err
        raise RuntimeError(f"No se pudo cargar el modelo en ninguna configuración: {err}") from err
    
    # Cargar processor (independiente del device)
    try:
        processor_kwargs = {"use_fast": False}
        if HF_TOKEN:
            processor_kwargs["token"] = HF_TOKEN
        processor = AutoProcessor.from_pretrained(MODEL_ID, **processor_kwargs)
        logger.debug("Processor cargado correctamente")
    except Exception as e:
        logger.error(f"Error al cargar processor: {e}")
        _raise_auth_help(e)
    
    dtype_map = {
        "float16": torch.float16,
        "fp16": torch.float16,
        "float32": torch.float32,
        "fp32": torch.float32,
    }

    use_gpu = torch.cuda.is_available()
    if use_gpu:
        preferred = dtype_map.get(str(MODEL_DTYPE).lower(), torch.float16)
    else:
        preferred = dtype_map.get(str(CPU_DTYPE).lower(), dtype_map.get(str(MODEL_DTYPE).lower(), torch.float32))
        if preferred == torch.float16:
            preferred = torch.float32

    # Intento principal: GPU (ROCm) si está disponible
    if use_gpu:
        try:
            # device_map='auto' distribuye capas entre GPU+CPU automáticamente (hibrido, más rápido)
            model_kwargs = {
                "dtype": preferred,
                "low_cpu_mem_usage": True,
                "device_map": "auto",  # Hibrido GPU+CPU: distribuye automáticamente
            }
            if HF_TOKEN:
                model_kwargs["token"] = HF_TOKEN
            model = AutoModelForImageTextToText.from_pretrained(
                MODEL_ID,
                **model_kwargs
            )
            model.eval()
            USE_DML = True
            DEVICE = "cuda"
            MODEL_INFO["backend"] = "rocm_hybrid"
            MODEL_INFO["dtype"] = preferred
            MODEL_INFO["device_name"] = torch.cuda.get_device_name(0)
            logger.info(f"Modelo cargado en GPU+CPU hibrido (ROCm): {MODEL_INFO['device_name']}")
            return model, processor, USE_DML
        except Exception as e_gpu:
            logger.warning(f"Fallo al cargar en GPU, usando CPU: {e_gpu}")

    # Fallback: CPU puro
    try:
        cpu_preferred = dtype_map.get(str(CPU_DTYPE).lower(), dtype_map.get(str(MODEL_DTYPE).lower(), torch.float32))
        if cpu_preferred == torch.float16:
            cpu_preferred = torch.float32
        model_kwargs = {
            "dtype": cpu_preferred,
            "low_cpu_mem_usage": True,
            "device_map": None,
        }
        if HF_TOKEN:
            model_kwargs["token"] = HF_TOKEN
        model = AutoModelForImageTextToText.from_pretrained(
            MODEL_ID,
            **model_kwargs
        )
        model.eval()
        model = model.to("cpu")
        USE_DML = False
        DEVICE = "cpu"
        MODEL_INFO["backend"] = "cpu"
        MODEL_INFO["dtype"] = cpu_preferred
        MODEL_INFO["device_name"] = "CPU"
        logger.info("Modelo cargado en CPU")
        return model, processor, USE_DML
    except Exception as e3:
        logger.critical(f"Fallo total al cargar modelo: {e3}")
        _raise_model_help(e3)


def get_device() -> Any:
    """Retorna el device actual."""
    return DEVICE


def prepare_inputs(inputs: Dict[str, Any], model: Any, dtype: Any = None) -> Dict[str, Any]:
    """
    Mueve inputs al device correcto según configuración del modelo y castea dtype si aplica.
    
    Args:
        inputs: Dict de tensores del processor
        model: Modelo cargado
        dtype: dtype objetivo para tensores float (opcional)
    
    Returns:
        Dict con inputs en el device correcto
    """
    # Liberar caché antes de procesar
    import gc
    gc.collect()
    
    if hasattr(model, 'hf_device_map') and model.hf_device_map:
        # Modo híbrido (no usado actualmente, pero por si acaso)
        first_device = list(model.hf_device_map.values())[0]
        return {
            k: (
                v.to(first_device, dtype=dtype) if hasattr(v, "to") and dtype is not None and hasattr(v, "dtype") and v.is_floating_point()
                else v.to(first_device) if hasattr(v, "to")
                else v
            )
            for k, v in inputs.items()
        }
    else:
        # Modo tradicional: usar device del modelo
        try:
            target_device = model.device
        except Exception:
            try:
                target_device = next(model.parameters()).device
            except Exception:
                target_device = "cpu"

        if not isinstance(target_device, (str, torch.device)):
            target_device = "cpu"

        return {
            k: (
                v.to(target_device, dtype=dtype) if hasattr(v, "to") and dtype is not None and hasattr(v, "dtype") and v.is_floating_point()
                else v.to(target_device) if hasattr(v, "to")
                else v
            )
            for k, v in inputs.items()
        }

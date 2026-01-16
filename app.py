"""
RadiAPP - Generación asistida de informes radiológicos con MedGemma
UI Gradio + orquestación de módulos
"""
import os
import json
import csv
import time
import logging
import signal
import sys
from datetime import datetime
from typing import Optional, Tuple, Dict, Any
import torch
import gradio as gr
from PIL import Image

# Configurar logger
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,  # Cambiar a DEBUG para capturar todo
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('radiapp.log'),
        logging.StreamHandler()
    ]
)

# Handler adicional para errores detallados
error_handler = logging.FileHandler('error_debug.log')
error_handler.setLevel(logging.ERROR)
error_formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s\n%(exc_info)s'
)
error_handler.setFormatter(error_formatter)
logger.addHandler(error_handler)

# ============================================================================
# CAPTURA Y REGISTRO DETALLADO DE ERRORES
# ============================================================================

def save_error_context(error_type: str, error_msg: str, context: Dict[str, Any]) -> str:
    """Guarda contexto detallado del error en JSON para debugging."""
    import traceback
    error_file = "error_context.json"
    
    error_context = {
        "timestamp": datetime.now().isoformat(),
        "error_type": error_type,
        "error_message": str(error_msg),
        "traceback": traceback.format_exc(),
        "device_info": {
            "cuda_available": torch.cuda.is_available(),
            "hip_version": getattr(torch.version, "hip", None),
            "device_count": torch.cuda.device_count() if torch.cuda.is_available() else 0,
            "torch_version": torch.__version__,
        },
        "memory_info": {
            "process_rss_mb": None,
            "gpu_allocated_mb": None,
            "gpu_reserved_mb": None,
        },
        "context": context,
    }
    
    # Intentar capturar info de memoria
    try:
        import psutil
        process = psutil.Process()
        error_context["memory_info"]["process_rss_mb"] = process.memory_info().rss / 1024 / 1024
        
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                error_context["memory_info"][f"gpu_{i}_allocated_mb"] = torch.cuda.memory_allocated(i) / 1024 / 1024
                error_context["memory_info"][f"gpu_{i}_reserved_mb"] = torch.cuda.memory_reserved(i) / 1024 / 1024
    except Exception as mem_err:
        logger.debug(f"No se pudo capturar info de memoria: {mem_err}")
    
    try:
        with open(error_file, "w", encoding="utf-8") as f:
            json.dump(error_context, f, ensure_ascii=False, indent=2)
        logger.error(f"Contexto de error guardado en {error_file}")
        return error_file
    except Exception as save_err:
        logger.error(f"Fallo al guardar contexto de error: {save_err}")
        return ""

# ============================================================================
# SIGNAL HANDLERS (Cleanup graceful en Ctrl+C)
# ============================================================================

def signal_handler(sig, frame):
    """
    Maneja Ctrl+C y otras señales de terminación.
    Libera memoria antes de salir.
    """
    logger.info("Señal de interrupción recibida (Ctrl+C). Limpiando memoria...")
    
    try:
        import gc
        gc.collect()
        
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("Caché CUDA limpiada")
        
        logger.info("Cleanup completado. Saliendo...")
    except Exception as e:
        logger.error(f"Error durante cleanup: {e}")
    
    sys.exit(0)

# Registrar signal handlers
signal.signal(signal.SIGINT, signal_handler)   # Ctrl+C
signal.signal(signal.SIGTERM, signal_handler)  # kill command
logger.info("Signal handlers registrados (Ctrl+C habilitado)")
logger.info(f"Torch version: {torch.__version__}")

# Información de entorno de ejecución (GPU/CPU)
def _log_runtime_env():
    try:
        hip_ver = getattr(torch.version, "hip", None)
        cuda_avail = torch.cuda.is_available()
        device_count = torch.cuda.device_count() if cuda_avail else 0
        logger.info(
            f"CUDA/HIP disponible: {cuda_avail} | HIP: {hip_ver} | GPUs detectadas: {device_count}"
        )
        if cuda_avail:
            try:
                names = [torch.cuda.get_device_name(i) for i in range(device_count)]
                logger.info(f"GPUs: {names}")
            except Exception as e:
                logger.warning(f"No se pudieron listar nombres de GPU: {e}")
        else:
            logger.info("Ejecutando en CPU (sin GPU disponible por Torch)")
    except Exception as e:
        logger.warning(f"No se pudo registrar entorno de ejecución: {e}")

_log_runtime_env()

# Módulos propios
from config import (
    FEEDBACK_CSV,
    MAX_IMAGE_SIZE,
    DEFAULT_MAX_TOKENS,
    MIN_MAX_TOKENS,
    MAX_MAX_TOKENS,
    MAX_MAX_TOKENS_UNLIMITED,
    MAX_TIME_SECONDS,
    TOKEN_STEP,
    SUPPORTED_MODALITIES,
    MIN_REGION_LENGTH,
    VALID_TEMPLATE_EXTENSIONS,
    IMAGE_TOKEN,
    VALID_IMAGE_TOKENS,
    CPU_NUM_THREADS,
    CPU_INTEROP_THREADS
)

# Optimización CPU
try:
    if CPU_NUM_THREADS:
        torch.set_num_threads(int(CPU_NUM_THREADS))
    if CPU_INTEROP_THREADS:
        torch.set_num_interop_threads(int(CPU_INTEROP_THREADS))
    if hasattr(torch, "set_float32_matmul_precision"):
        torch.set_float32_matmul_precision("high")
    logger.info(
        f"CPU threads: {torch.get_num_threads()} | interop: {torch.get_num_interop_threads()}"
    )
except Exception as e:
    logger.warning(f"No se pudo ajustar threads CPU: {e}")
from model_loader import load_model, prepare_inputs
from prompt_builder import build_prompt, save_good_example, build_repair_prompt
from report_processor import (
    validate_image_quality,
    extract_json_block,
    apply_edits,
    analyze_uncertainty_tokens,
    audit_report_internal,
    multi_turn_refinement
)
from template_manager import (
    list_templates,
    read_template,
    write_template,
    import_template,
    create_default_template
)

# Cargar modelo bajo demanda (evita side-effects en imports/tests)
model, processor, USE_DML = None, None, False


def ensure_model_loaded():
    """Carga el modelo solo cuando se necesita (lazy load)."""
    global model, processor, USE_DML
    if model is None or processor is None:
        model, processor, USE_DML = load_model()
        # Alinear el token de imagen entre tokenizer y modelo
        try:
            tokenizer = getattr(processor, "tokenizer", None)
            image_token_id = None
            image_token_name = None
            if tokenizer is not None and hasattr(tokenizer, "convert_tokens_to_ids"):
                # Priorizar el token que representa los 256 patches
                for candidate in ("<image_soft_token>", "<image>", "<start_of_image>"):
                    tok_id = tokenizer.convert_tokens_to_ids(candidate)
                    if tok_id is not None and tok_id != tokenizer.unk_token_id:
                        image_token_id = tok_id
                        image_token_name = candidate
                        break
            if image_token_id is None and tokenizer is not None:
                image_token_id = getattr(tokenizer, "image_token_id", None)
                image_token_name = "tokenizer.image_token_id"
            if image_token_id is not None and hasattr(model, "config"):
                model.config.image_token_id = int(image_token_id)
                model.config.image_token_index = int(image_token_id)
                logger.info(
                    "image_token_id configurado a "
                    f"{model.config.image_token_id} (token={image_token_name})"
                )
                # Log extra para confirmar IDs del tokenizer
                if tokenizer is not None:
                    logger.debug(
                        "Tokenizer image_token_id="
                        f"{getattr(tokenizer, 'image_token_id', None)}"
                    )
                    logger.debug(
                        "Tokenizer ids: <image_soft_token>="
                        f"{tokenizer.convert_tokens_to_ids('<image_soft_token>')} | "
                        "<start_of_image>="
                        f"{tokenizer.convert_tokens_to_ids('<start_of_image>')}"
                    )
        except Exception as e:
            logger.warning(f"No se pudo configurar image_token_index: {e}")
        # Registrar device/dtype efectivos del modelo
        try:
            dev = getattr(model, "device", None)
            if dev is None:
                dev = next(model.parameters()).device
            logger.info(f"Modelo activo en device: {dev} | dtype: {getattr(model, 'dtype', None)}")
        except Exception as e:
            logger.warning(f"No se pudo obtener device/dtype del modelo: {e}")

# ============================================================================
# MONITOREO DE MEMORIA GPU/VRAM
# ============================================================================

def log_memory_stats(stage: str) -> None:
    """
    Registra estadísticas de memoria RAM (y GPU si existe).
    
    Args:
        stage: Etapa del proceso ("before_generation", "after_generation", etc.)
    """
    try:
        import psutil
        process = psutil.Process()
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024
        
        logger.debug(f"[{stage}] RAM proceso: {mem_mb:.1f} MB")
        
        # Si hay CUDA disponible (por si acaso)
        if torch.cuda.is_available():
            for i in range(torch.cuda.device_count()):
                allocated = torch.cuda.memory_allocated(i) / 1024 / 1024
                reserved = torch.cuda.memory_reserved(i) / 1024 / 1024
                logger.debug(f"[{stage}] GPU {i}: Allocated={allocated:.1f}MB, Reserved={reserved:.1f}MB")
        else:
            logger.debug(f"[{stage}] CPU activo")
    
    except ImportError:
        logger.debug(f"[{stage}] psutil no disponible para monitoreo de RAM")
    except Exception as e:
        logger.debug(f"[{stage}] Error en monitoreo: {e}")

# ============================================================================
# VALIDACIÓN DE INPUTS
# ============================================================================

def validate_inputs(img: Optional[Image.Image], modalidad: str, region: str, template_file: str, max_new_tokens: int, max_tokens_limit: int) -> Tuple[bool, str]:
    """
    Validación exhaustiva de inputs antes de generación.
    
    Returns:
        tuple: (is_valid, error_message)
    """
    # Validar imagen
    if img is None:
        return False, "⚠️ Sube una imagen anonimizada."
    
    # Validar modalidad
    if modalidad not in SUPPORTED_MODALITIES:
        return False, f"❌ Modalidad inválida: {modalidad}. Debe ser una de {SUPPORTED_MODALITIES}"
    
    # Validar región
    if not region or len(region.strip()) < MIN_REGION_LENGTH:
        return False, f"❌ Región debe tener al menos {MIN_REGION_LENGTH} caracteres"
    
    # Validar plantilla
    if not template_file:
        return False, "⚠️ Selecciona una plantilla."
    
    # Validar extensión de plantilla
    import os
    ext = os.path.splitext(template_file)[1].lower()
    if ext not in VALID_TEMPLATE_EXTENSIONS:
        return False, f"❌ Archivo de plantilla debe ser {VALID_TEMPLATE_EXTENSIONS}, recibido: {ext}"
    
    # Validar max_new_tokens
    if not isinstance(max_new_tokens, (int, float)):
        return False, f"❌ max_new_tokens debe ser número, recibido: {type(max_new_tokens).__name__}"
    
    max_new_tokens = int(max_new_tokens)
    if max_new_tokens < MIN_MAX_TOKENS or max_new_tokens > max_tokens_limit:
        return False, f"❌ max_new_tokens debe estar entre {MIN_MAX_TOKENS} y {max_tokens_limit}, recibido: {max_new_tokens}"
    
    return True, ""

# ============================================================================
# GENERACIÓN DE INFORMES (función principal)
# ============================================================================


def _normalize_eos_token_id(token_id: Any) -> Optional[int]:
    """Normaliza eos_token_id a int o None."""
    if token_id is None:
        return None
    if isinstance(token_id, int):
        return token_id
    if isinstance(token_id, (list, tuple)) and token_id:
        first = token_id[0]
        return int(first) if isinstance(first, (int, float)) else None
    try:
        import torch as _torch
        if isinstance(token_id, _torch.Tensor):
            if token_id.numel() > 0:
                return int(token_id.flatten()[0].item())
    except Exception:
        pass
    return None


def generate_with_beam_search(inputs: Dict[str, Any], model: Any, processor: Any, max_new_tokens: int, num_beams: int = 1) -> Any:
    """Genera con beam search (simplificado)."""
    # Filtrar inputs: solo pasar parámetros válidos para model.generate()
    # Remover claves del processor que no son de generate
    # No pasar token_type_ids a generate(): Gemma/MedGemma no lo espera aquí
    valid_keys = {'input_ids', 'attention_mask', 'pixel_values', 'image_sizes'}
    filtered_inputs = {k: v for k, v in inputs.items() if k in valid_keys}
    
    logger.debug(f"Inputs originales: {list(inputs.keys())}")
    logger.debug(f"Inputs filtrados para generate: {list(filtered_inputs.keys())}")
    
    # Validar que tenemos al menos las claves mínimas
    required_for_vision = {'input_ids', 'attention_mask', 'pixel_values'}
    missing = required_for_vision - set(filtered_inputs.keys())
    if missing:
        raise ValueError(f"Faltan claves críticas para generación con imagen: {missing}. Presentes: {list(filtered_inputs.keys())}")
    
    eos_token_id = None
    pad_token_id = None
    if hasattr(processor, "tokenizer"):
        eos_token_id = _normalize_eos_token_id(getattr(processor.tokenizer, "eos_token_id", None))
        pad_token_id = _normalize_eos_token_id(getattr(processor.tokenizer, "pad_token_id", None))
        if pad_token_id is None:
            pad_token_id = eos_token_id

    logger.debug(f"eos_token_id={eos_token_id}, pad_token_id={pad_token_id}")
    
    # Usar inference_mode para CPU/GPU
    try:
        with torch.inference_mode():
            return model.generate(
                **filtered_inputs,
                max_new_tokens=int(max_new_tokens),
                max_time=MAX_TIME_SECONDS,
                do_sample=False,
                num_beams=num_beams,
                no_repeat_ngram_size=2,
                eos_token_id=eos_token_id,
                pad_token_id=pad_token_id,
            )
    except Exception as e:
        logger.error(f"Error durante model.generate(): {e}")
        logger.error(f"Input shapes: {[(k, v.shape if hasattr(v, 'shape') else type(v)) for k, v in filtered_inputs.items()]}")
        raise


def generate(img: Optional[Image.Image], modalidad: str, region: str, indicacion: str, extras: str, template_file: str, max_new_tokens: int, max_tokens_limit: int) -> str:
    """Función principal de generación de informes."""
    try:
        # Validación exhaustiva de inputs
        is_valid, error_msg = validate_inputs(img, modalidad, region, template_file, max_new_tokens, max_tokens_limit)
        if not is_valid:
            logger.warning(f"Validación fallida: {error_msg}")
            return error_msg

        # Leer plantilla
        tpl = read_template(template_file)
        template_text = (tpl.get("template_text") or "").strip()
        if not template_text:
            return "⚠️ Plantilla vacía."

        # Preparar imagen
        img = img.convert("RGB")
        is_valid, validation_msg = validate_image_quality(img)
        if not is_valid:
            return f"❌ Validación fallida: {validation_msg}"
        
        img.thumbnail(MAX_IMAGE_SIZE)

        # Procesar con modelo
        ensure_model_loaded()

        # Construir texto del prompt (sin tokens especiales - solo para referencia humana)
        # El processor.apply_chat_template insertará automáticamente los tokens <image>
        prompt_text = build_prompt(modalidad, region, indicacion, extras, template_text, image_token="")
        
        log_memory_stats("before_generation")
        t0 = time.time()

        # Usar apply_chat_template con estructura de mensajes (forma correcta para MedGemma)
        try:
            logger.debug(f"Prompt texto: {len(prompt_text)} chars")
            
            # Construir mensaje multimodal con imagen + texto
            messages = [{
                "role": "user",
                "content": [
                    {"type": "image", "image": img},
                    {"type": "text", "text": prompt_text}
                ]
            }]
            
            # Generar tokens con apply_chat_template (inserta <image> automáticamente)
            inputs = processor.apply_chat_template(
                messages,
                add_generation_prompt=True,
                tokenize=True,
                return_dict=True,
                return_tensors="pt"
            )
            
            # Validar que inputs no sea None y tenga las claves requeridas
            if inputs is None:
                raise ValueError("processor.apply_chat_template() devolvió None")
            
            required_keys = {'input_ids', 'attention_mask', 'pixel_values'}
            missing_keys = required_keys - set(inputs.keys())
            if missing_keys:
                raise ValueError(f"Faltan claves en inputs: {missing_keys}. Presentes: {list(inputs.keys())}")
            
            logger.info("OK: Inputs construidos con apply_chat_template")
            logger.debug(f"Input keys: {list(inputs.keys())}")
            logger.debug(f"input_ids shape: {inputs['input_ids'].shape}")
            logger.debug(f"pixel_values shape: {inputs['pixel_values'].shape}")
            logger.debug(f"attention_mask shape: {inputs['attention_mask'].shape}")

            # Verificar presencia de tokens de imagen en input_ids
            try:
                tokenizer = processor.tokenizer if hasattr(processor, "tokenizer") else None
                if tokenizer is not None:
                    image_token_counts = {}
                    for tok in VALID_IMAGE_TOKENS:
                        tok_id = tokenizer.convert_tokens_to_ids(tok)
                        if tok_id is not None and tok_id != tokenizer.unk_token_id:
                            count = int((inputs["input_ids"] == tok_id).sum().item())
                            image_token_counts[tok] = count
                    logger.info(f"Tokens de imagen en input_ids: {image_token_counts}")
                    # Conteo usando el token configurado en el modelo
                    model_image_token_id = getattr(model.config, "image_token_id", None)
                    if model_image_token_id is not None:
                        count_model_tok = int((inputs["input_ids"] == model_image_token_id).sum().item())
                        logger.info(
                            f"Tokens con model.config.image_token_id={model_image_token_id}: {count_model_tok}"
                        )
            except Exception as tok_err:
                logger.debug(f"No se pudo verificar tokens de imagen: {tok_err}")
            
        except Exception as e:
            logger.error(f"Fallo en apply_chat_template: {e}")
            logger.debug(f"Prompt length: {len(prompt_text)}, Image size: {img.size if img else 'None'}")
            raise ValueError(f"Processor Gemma3 falló: {e}")

        if prompt_text:
            logger.info(f"Prompt texto longitud: {len(prompt_text)} chars")
            logger.debug(f"Prompt (primeros 200 chars): {prompt_text[:200]}")

        logger.debug(f"Processor timing: {time.time()-t0:.2f}s")
        
        # Mover inputs al device correcto (y dtype del modelo si aplica)
        try:
            model_dtype = getattr(model, "dtype", None)
            logger.debug(f"Preparando inputs... (model_dtype={model_dtype})")
            inputs = prepare_inputs(inputs, model, dtype=model_dtype)
            logger.info("OK: Inputs movidos a device correcto")
        except Exception as prep_err:
            logger.error(f"Error en prepare_inputs: {prep_err}")
            raise ValueError(f"Fallo al preparar inputs para GPU: {prep_err}")



        # Generar
        t1 = time.time()
        logger.info("Iniciando model.generate()...")
        try:
            out = generate_with_beam_search(inputs, model, processor, int(max_new_tokens), num_beams=1)
            logger.info(f"OK: Generacion completada en {time.time()-t1:.2f}s")
        except Exception as gen_err:
            logger.error(f"Error en generate_with_beam_search: {type(gen_err).__name__}: {gen_err}")
            # Fallback: reintentar con prompt manual y processor(text, images)
            if isinstance(gen_err, ValueError) and "image tokens" in str(gen_err).lower():
                try:
                    logger.warning("Reintentando con prompt manual <image> + processor(text, images)")
                    manual_prompt = f"<image>\n{prompt_text}"
                    retry_inputs = processor(
                        text=manual_prompt,
                        images=img,
                        return_tensors="pt"
                    )
                    model_dtype = getattr(model, "dtype", None)
                    retry_inputs = prepare_inputs(retry_inputs, model, dtype=model_dtype)
                    out = generate_with_beam_search(
                        retry_inputs, model, processor, int(max_new_tokens), num_beams=1
                    )
                    inputs = retry_inputs
                    logger.info(f"OK: Generacion completada en {time.time()-t1:.2f}s (fallback)")
                except Exception as retry_err:
                    logger.error(f"Fallo en fallback de generación: {retry_err}")
                    raise
            else:
                raise
        logger.debug(f"Generation timing: {time.time()-t1:.2f}s")
        log_memory_stats("after_generation")

        # Decodificar
        t2 = time.time()
        generated_text = processor.tokenizer.batch_decode(out, skip_special_tokens=True)[0]
        logger.debug(f"Decode timing: {time.time()-t2:.2f}s")

        # Limpiar salida
        markers = ["--- PLANTILLA ---", "--- FIN PLANTILLA ---"]
        if markers[0] in generated_text and markers[1] in generated_text:
            generated_text = generated_text.split(markers[0], 1)[-1]
            generated_text = generated_text.split(markers[1], 1)[0]

        # Eliminar tokens de razonamiento interno
        bad_tokens = ["<thought>", "</thought>", "Here's a thinking process", "<unused"]
        for bt in bad_tokens:
            if bt in generated_text:
                generated_text = generated_text.split(bt)[0]

        decoded = generated_text.strip()

        # Extraer y parsear JSON
        json_fallback_used = False
        json_repaired = False
        try:
            json_text = extract_json_block(decoded)
            json_output = json.loads(json_text)
        except ValueError as e:
            logger.warning(f"No se encontró JSON en la salida: {e}")
            try:
                repair_prompt = build_repair_prompt(decoded, template_text)
                repair_inputs = None
                if hasattr(processor, "apply_chat_template"):
                    repair_messages = [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": repair_prompt}
                            ],
                        }
                    ]
                    repair_inputs = processor.apply_chat_template(
                        repair_messages,
                        add_generation_prompt=True,
                        tokenize=True,
                        return_dict=True,
                        return_tensors="pt"
                    )
                else:
                    repair_inputs = processor(text=repair_prompt, return_tensors="pt")
                model_dtype = getattr(model, "dtype", None)
                repair_inputs = prepare_inputs(repair_inputs, model, dtype=model_dtype)
                repair_out = generate_with_beam_search(repair_inputs, model, processor, int(max_new_tokens), num_beams=1)
                repair_text = processor.tokenizer.batch_decode(repair_out, skip_special_tokens=True)[0]
                json_text = extract_json_block(repair_text)
                json_output = json.loads(json_text)
                json_repaired = True
                json_fallback_used = False
                del repair_inputs, repair_out
            except Exception as repair_err:
                logger.warning(f"Falló reparación de JSON: {repair_err}")
                json_fallback_used = True
                json_output = {
                    "remove": [],
                    "replace": [],
                    "add_findings": [],
                    "lesiometro_missing": [],
                    "confidence_scores": {},
                    "conclusion": {
                        "positives": [],
                        "impression": [],
                        "ddx": [],
                        "recommendations": []
                    }
                }
                json_text = json.dumps(json_output, ensure_ascii=False, indent=2)
        
        # Análisis de incertidumbre
        json_output = analyze_uncertainty_tokens(decoded, json_output)
        json_text = json.dumps(json_output, ensure_ascii=False, indent=2)

        # Aplicar ediciones a plantilla
        final_report = apply_edits(template_text, json_text)
        if json_repaired:
            final_report = "ℹ️ JSON reconstruido automáticamente a partir del borrador del modelo.\n\n" + final_report
        elif json_fallback_used:
            final_report = "⚠️ El modelo no devolvió JSON; se muestra la plantilla sin cambios. Reintenta con otra imagen o ajusta el prompt.\n\n" + final_report
        
        # Refinamiento multi-turn
        final_report, json_output = multi_turn_refinement(final_report, json_output, template_text, img)
        
        # Auditoría final
        adds = json_output.get("add_findings", [])
        final_report = audit_report_internal(final_report, template_text, bool(adds))
        
        # Liberar memoria GPU para evitar OOM en generaciones sucesivas
        del inputs, out
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        # En CPU, del() ayuda al GC
        import gc
        gc.collect()
        logger.info("Generación completada exitosamente")

        return final_report

    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing failed: {e}")
        error_ctx = {"generated_text_sample": decoded[:500] if 'decoded' in locals() else None}
        save_error_context("JSONDecodeError", str(e), error_ctx)
        import gc
        gc.collect()
        return "❌ Error: El modelo no generó JSON válido. Por favor reintenta o ajusta el prompt. (Ver error_context.json para detalles)"
    
    except torch.cuda.OutOfMemoryError as e:
        logger.error("GPU OOM durante generación")
        error_ctx = {"max_tokens": max_new_tokens, "image_size": MAX_IMAGE_SIZE}
        save_error_context("OutOfMemoryError", str(e), error_ctx)
        import gc
        gc.collect()
        return "❌ Error: VRAM insuficiente. Reduce max_new_tokens o la resolución de la imagen. (Ver error_context.json)"
    
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        error_ctx = {
            "modalidad": modalidad,
            "region": region,
            "template_file": template_file,
            "error_location": "validation"
        }
        save_error_context("ValueError", str(e), error_ctx)
        import gc
        gc.collect()
        return f"❌ Error de validación: {e} (Ver error_context.json)"
    
    except Exception as e:
        logger.exception("Error inesperado durante generación")  # Logs traceback completo
        # Capturar contexto lo máximo posible antes de fallar
        error_ctx = {
            "modalidad": modalidad,
            "region": region,
            "template_file": template_file,
            "max_new_tokens": max_new_tokens,
            "prompt_length": len(prompt_text) if 'prompt_text' in locals() else None,
            "image_size": img.size if 'img' in locals() else None,
            "stage": "unknown",
        }
        save_error_context(type(e).__name__, str(e), error_ctx)
        import gc
        gc.collect()
        # Mensaje detallado para usuario
        error_msg = f"Error inesperado: {type(e).__name__}: {str(e)[:200]}. Detalles en error_context.json"
        logger.error(error_msg)
        return error_msg


# ============================================================================
# FEEDBACK
# ============================================================================

def ensure_feedback_header() -> None:
    """Crea header del CSV de feedback si no existe."""
    if not os.path.exists(FEEDBACK_CSV):
        with open(FEEDBACK_CSV, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp","template","modalidad","region","indicacion","output","rating","comentario","version_final"])


def save_feedback(template_file: str, modalidad: str, region: str, indicacion: str, output: str, rating: str, comentario: str, version_final: str) -> str:
    """Guarda feedback del usuario en CSV."""
    ensure_feedback_header()
    ts = datetime.now().isoformat(timespec="seconds")
    with open(FEEDBACK_CSV, "a", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow([ts, template_file, modalidad, region, indicacion, output, rating, comentario, version_final])
    return f"✅ Feedback guardado: {ts}"


def load_template_to_editor(template_file):
    """Carga plantilla en editor."""
    if not template_file:
        return "", ""
    data = read_template(template_file)
    return data.get("name",""), data.get("template_text","")


def save_template_from_editor(current_filename, name, template_text):
    """Guarda plantilla desde editor."""
    name = (name or "").strip() or "Plantilla_sin_nombre"
    data = {"name": name, "template_text": template_text or ""}
    filename = current_filename if current_filename else f"{name}.json"
    filename = write_template(filename, data)
    return f"✅ Guardada: {filename}", filename, gr.Dropdown(choices=list_templates(), value=filename)


# ============================================================================
# INTERFAZ GRADIO
# ============================================================================

# Crear plantilla por defecto
create_default_template()

with gr.Blocks(title="RadiAPP – MedGemma") as demo:
    gr.Markdown("## 🩻 RadiAPP – Informes radiológicos\nSube imágenes **anonimizadas**.")

    with gr.Tab("Generar"):
        with gr.Row():
            img = gr.Image(type="pil", label="Imagen")
            with gr.Column():
                modalidad = gr.Dropdown(SUPPORTED_MODALITIES, value="TC", label="Modalidad")
                region = gr.Textbox(value="", label="Región/estudio")
                indicacion = gr.Textbox(value="", label="Indicación (opcional)", lines=2)
                extras = gr.Textbox(value="", label="Notas (opcional)", lines=2)
                template_dd = gr.Dropdown(choices=list_templates(), label="Plantilla", value=list_templates()[0])
                with gr.Row():
                    max_new_tokens = gr.Slider(
                        MIN_MAX_TOKENS,
                        MAX_MAX_TOKENS,
                        value=DEFAULT_MAX_TOKENS,
                        step=TOKEN_STEP,
                        label="Cantidad de caracteres deseados"
                    )
                    unlimited_tokens = gr.Checkbox(value=False, label="Sin límite (más lento)")

        btn = gr.Button("Generar borrador")
        output = gr.Code(label="Salida (usa el botón Copy)", language="markdown")  # trae Copy nativo
        
        # Estados para guardar contexto de generación
        last_output_state = gr.State(value="")
        last_template_state = gr.State(value="")
        last_modalidad_state = gr.State(value="TC")
        last_region_state = gr.State(value="")
        last_indicacion_state = gr.State(value="")
        
        # Función para guardar y aprender de un borrador bueno
        def save_good_report(output_text, template_file, modalidad, region, indicacion):
            """Guarda feedback + aprende del output como ejemplo bueno"""
            try:
                if not output_text or output_text.startswith("❌") or output_text.startswith("⚠️"):
                    return "❌ No hay output válido para guardar"
                
                # Guardar feedback automático con rating máximo
                ensure_feedback_header()
                ts = datetime.now().isoformat(timespec="seconds")
                with open(FEEDBACK_CSV, "a", encoding="utf-8", newline="") as f:
                    w = csv.writer(f)
                    w.writerow([ts, template_file, modalidad, region, indicacion, output_text, "5", "Aprobado automático - borrador bueno", output_text])
                
                # Extraer JSON para guardar como ejemplo bueno
                try:
                    json_text = extract_json_block(output_text)
                    json_obj = json.loads(json_text)
                    
                    # Crear etiqueta descriptiva del ejemplo
                    label = f"{modalidad} - {region} ({ts[-8:-3]})"
                    example_with_label = {"label": label, **json_obj}
                    save_good_example(example_with_label)
                    
                    return f"✅ ¡Excelente! Borrador guardado como ejemplo bueno.\n📚 MedGemma aprenderá de este patrón en futuras generaciones."
                except (json.JSONDecodeError, ValueError):
                    # Si no hay JSON válido, solo guardar feedback
                    return f"✅ Feedback guardado (no se encontró JSON para guardar como ejemplo)."
            except Exception as e:
                return f"⚠️ Error al guardar: {str(e)}"
        
        # Agregar fila con botón "Es bueno"
        with gr.Row():
            feedback_msg = gr.Markdown("💬 ¿El borrador es bueno? Usa el botón de abajo.")
        
        with gr.Row():
            good_btn = gr.Button("👍 Este borrador es BUENO - Guardar y aprender", scale=2, variant="primary")
            clear_btn = gr.Button("🗑️ Limpiar", scale=1)
            error_btn = gr.Button("❌ Hay errores - Reportar", scale=1, variant="stop")
        
        feedback_status = gr.Markdown("")
        
        # Lógica del flujo
        def generate_and_store(img_input, mod, reg, ind, ext, tpl, tokens, is_unlimited):
            """Genera y guarda estado"""
            max_limit = MAX_MAX_TOKENS_UNLIMITED if is_unlimited else MAX_MAX_TOKENS
            result = generate(img_input, mod, reg, ind, ext, tpl, tokens, max_limit)
            return result, result, tpl, mod, reg, ind
        
        def clear_output():
            """Limpia salida"""
            return "", "", "", "TC", "", ""
        
        def go_to_feedback(output_text, tpl, mod, reg, ind):
            """Prepara datos para ir a Feedback"""
            return (output_text, tpl, mod, reg, ind, "Feedback")
        
        # Conectar generación
        btn.click(
            generate_and_store,
            inputs=[img, modalidad, region, indicacion, extras, template_dd, max_new_tokens, unlimited_tokens],
            outputs=[output, last_output_state, last_template_state, last_modalidad_state, last_region_state, last_indicacion_state]
        )

        # Toggle límite de tokens
        def toggle_unlimited(is_unlimited):
            if is_unlimited:
                return gr.Slider(maximum=MAX_MAX_TOKENS_UNLIMITED, value=min(MAX_MAX_TOKENS_UNLIMITED, 1024))
            return gr.Slider(maximum=MAX_MAX_TOKENS, value=min(DEFAULT_MAX_TOKENS, MAX_MAX_TOKENS))

        unlimited_tokens.change(
            toggle_unlimited,
            inputs=[unlimited_tokens],
            outputs=[max_new_tokens]
        )
        
        # Conectar botón "Es bueno"
        good_btn.click(
            save_good_report,
            inputs=[last_output_state, last_template_state, last_modalidad_state, last_region_state, last_indicacion_state],
            outputs=[feedback_status]
        )
        
        # Conectar botón limpiar
        clear_btn.click(
            clear_output,
            outputs=[output, last_output_state, last_template_state, last_modalidad_state, last_region_state, last_indicacion_state]
        )

    with gr.Tab("Plantillas"):
        gr.Markdown("### Importar / editar / guardar (DOCX/TXT/JSON). Se guardan como JSON en ./templates/")

        tpl_file = gr.File(label="Subir plantilla", file_types=[".docx",".txt",".json"])
        import_btn = gr.Button("Importar a editor")

        status = gr.Markdown("")
        current_filename = gr.State(value="")

        tpl_name = gr.Textbox(label="Nombre", value="")
        tpl_text = gr.Textbox(label="Contenido", value="", lines=18)

        with gr.Row():
            existing_dd = gr.Dropdown(choices=list_templates(), label="Cargar existente", value=None)
            load_btn = gr.Button("Cargar al editor")

        load_btn.click(load_template_to_editor, inputs=[existing_dd], outputs=[tpl_name, tpl_text]).then(
            lambda x: x, inputs=[existing_dd], outputs=[current_filename]
        )

        def do_import(file_obj):
            if file_obj is None:
                return "⚠️ Sube un archivo", "", ""
            n, t = import_template(file_obj)
            return "✅ Importada. Revisa y guarda.", n, t

        import_btn.click(do_import, inputs=[tpl_file], outputs=[status, tpl_name, tpl_text]).then(
            lambda: "", inputs=[], outputs=[current_filename]
        )

        save_btn = gr.Button("Guardar plantilla")
        save_status = gr.Markdown("")

        save_btn.click(
            save_template_from_editor,
            inputs=[current_filename, tpl_name, tpl_text],
            outputs=[save_status, current_filename, existing_dd]
        ).then(
            lambda: gr.Dropdown(choices=list_templates()),
            inputs=[],
            outputs=[template_dd]
        )

    with gr.Tab("Feedback"):
        gr.Markdown("### Feedback → se guarda en ./feedback/feedback.csv")

        fb_template = gr.Dropdown(choices=list_templates(), label="Plantilla usada")
        fb_modalidad = gr.Dropdown(SUPPORTED_MODALITIES, value="TC", label="Modalidad")
        fb_region = gr.Textbox(value="Cráneo", label="Región/estudio")
        fb_indicacion = gr.Textbox(value="", label="Indicación")
        fb_output = gr.Textbox(value="", label="Salida del modelo (pega aquí)", lines=5)
        fb_rating = gr.Radio(["1","2","3","4","5"], value="2", label="Rating")
        fb_comentario = gr.Textbox(value="Hay errores en el reporte - revisar", label="Comentario", lines=2)
        fb_version_final = gr.Textbox(value="", label="Tu versión final (opcional)", lines=6)
        
        gr.Markdown("### 🎯 Aprendizaje contínuo: Guardar ejemplos buenos")
        good_example_json = gr.Textbox(
            value="",
            label="JSON de ejemplo bueno (copiar JSON generado del modelo)",
            lines=8,
            placeholder='{"remove_findings": [...], "add_findings": [...], ...}'
        )
        good_example_label = gr.Textbox(
            value="",
            label="Descripción del ejemplo (ej: 'TC craneal con hematoma subdural crónico')"
        )
        save_good_btn = gr.Button("💾 Guardar como ejemplo bueno")
        good_example_status = gr.Markdown("")

        def save_good_example_ui(json_str, label):
            """Wrapper UI para guardar ejemplos buenos"""
            try:
                if not json_str.strip():
                    return "❌ JSON vacío"
                if not label.strip():
                    return "❌ Falta descripción del ejemplo"
                
                json_obj = json.loads(json_str)
                example_with_label = {"label": label.strip(), **json_obj}
                save_good_example(example_with_label)
                return f"✅ Ejemplo guardado: {label}"
            except json.JSONDecodeError:
                return f"❌ JSON inválido: {json_str[:100]}"
            except Exception as e:
                return f"❌ Error: {str(e)}"
        
        save_good_btn.click(
            save_good_example_ui,
            inputs=[good_example_json, good_example_label],
            outputs=[good_example_status]
        )

        fb_btn = gr.Button("Guardar feedback")
        fb_status = gr.Markdown("")
        fb_btn.click(save_feedback,
                    inputs=[fb_template, fb_modalidad, fb_region, fb_indicacion, fb_output, fb_rating, fb_comentario, fb_version_final],
                    outputs=[fb_status])
    
    # Conectar botón "Hay errores" DESPUÉS de definir fb_* variables
    def prepare_error_feedback(output_text, tpl, mod, reg, ind):
        """Pre-llena Feedback con los datos del reporte con errores"""
        return tpl, mod, reg, ind, output_text, "2", "Hay errores en el reporte - revisar", ""
    
    error_btn.click(
        prepare_error_feedback,
        inputs=[last_output_state, last_template_state, last_modalidad_state, last_region_state, last_indicacion_state],
        outputs=[fb_template, fb_modalidad, fb_region, fb_indicacion, fb_output, fb_rating, fb_comentario, fb_version_final]
    )

if __name__ == "__main__":
    server_name = os.getenv("GRADIO_SERVER_NAME", "127.0.0.1")
    port_env = os.getenv("GRADIO_SERVER_PORT")
    server_port = int(port_env) if port_env else None
    demo.launch(server_name=server_name, server_port=server_port, pwa=True)

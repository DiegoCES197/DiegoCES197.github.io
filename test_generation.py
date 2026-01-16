#!/usr/bin/env python3
"""
Script de prueba para verificar que la generación funciona sin error
'Prompt contained 0 image tokens but received 1 images'
"""
import os
import sys
import torch
from PIL import Image, ImageDraw
import logging

# Configurar logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Asegurarse de que estamos en el directorio correcto
os.chdir(r"D:\RadiAPP")
sys.path.insert(0, r"D:\RadiAPP")

# Importar módulos
from model_loader import load_model
from prompt_builder import build_prompt

def create_test_image():
    """Crear una imagen de prueba simple."""
    img = Image.new('RGB', (512, 512), color='white')
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 450, 450], outline='black', width=2)
    draw.text((200, 240), "TEST", fill='black')
    return img

def test_generation():
    """Prueba la generación con imagen y texto."""
    try:
        logger.info("=== Test de Generación MedGemma ===")
        
        # Cargar modelo
        logger.info("Cargando modelo...")
        model, processor, _ = load_model()
        logger.info(f"✓ Modelo cargado")
        
        # Crear imagen de prueba
        logger.info("Creando imagen de prueba...")
        img = create_test_image()
        logger.info(f"✓ Imagen creada: {img.size}")
        
        # Construir prompt
        template_text = "Hallazgos: \nImpresión: "
        prompt_text = build_prompt("TC", "Cráneo", "Dolor de cabeza", "", template_text, image_token="")
        logger.info(f"✓ Prompt construido ({len(prompt_text)} chars)")
        
        # Crear estructura de mensajes (COMO EN app.py AHORA)
        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": img},
                {"type": "text", "text": prompt_text}
            ]
        }]
        logger.info("✓ Estructura de mensajes creada")
        
        # apply_chat_template debe insertar automáticamente los tokens <image>
        logger.info("Procesando con apply_chat_template...")
        inputs = processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt"
        )
        logger.info(f"✓ Inputs procesados")
        logger.info(f"  Input keys: {list(inputs.keys())}")
        logger.info(f"  input_ids shape: {inputs['input_ids'].shape}")
        
        # Contar tokens <image> en input_ids
        if hasattr(processor, 'tokenizer'):
            # Encontrar ID del token <image>
            image_token_id = processor.tokenizer.get_vocab().get("<image>")
            if image_token_id:
                count = (inputs['input_ids'] == image_token_id).sum().item()
                logger.info(f"  Tokens <image> encontrados: {count}")
                if count == 0:
                    logger.warning("⚠️ NO se encontraron tokens <image> en input_ids")
                else:
                    logger.info("✓ Se encontraron tokens <image> en input_ids")
            else:
                logger.warning("⚠️ No se pudo obtener ID del token <image>")
        
        # Mover a device del modelo
        device = model.device if hasattr(model, 'device') else next(model.parameters()).device
        inputs = {k: v.to(device) for k, v in inputs.items() if hasattr(v, 'to')}
        logger.info(f"✓ Inputs movidos a device: {device}")
        
        # Generar (con pocos tokens para prueba rápida)
        logger.info("Generando respuesta (max 50 tokens)...")
        with torch.inference_mode():
            outputs = model.generate(
                **inputs,
                max_new_tokens=50,
                do_sample=False
            )
        logger.info(f"✓ Generación completada")
        logger.info(f"  Output shape: {outputs.shape}")
        
        # Decodificar
        logger.info("Decodificando...")
        prompt_len = inputs["input_ids"].shape[-1]
        decoded = processor.tokenizer.batch_decode(outputs[:, prompt_len:], skip_special_tokens=True)[0]
        logger.info(f"✓ Decodificación completada")
        logger.info(f"  Respuesta: {decoded[:100]}...")
        
        logger.info("\n=== ✅ TEST EXITOSO ===")
        logger.info("La generación funcionó correctamente sin errores de tokens de imagen.")
        return True
        
    except ValueError as e:
        if "image tokens" in str(e).lower():
            logger.error(f"\n❌ ERROR DE TOKENS DE IMAGEN: {e}")
            logger.error("Este es el error que estábamos intentando resolver.")
            return False
        else:
            logger.error(f"❌ Error de validación: {e}")
            return False
    except Exception as e:
        logger.error(f"❌ Error inesperado: {type(e).__name__}: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    success = test_generation()
    sys.exit(0 if success else 1)

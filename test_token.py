#!/usr/bin/env python3
"""Test del token de imagen con processor clásico"""

import torch
from transformers import AutoProcessor
from PIL import Image
import numpy as np
import os
from dotenv import load_dotenv

load_dotenv()
os.environ['TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL'] = '1'

# Crear imagen de prueba
img = Image.fromarray(np.random.randint(50, 150, (512, 512), dtype=np.uint8))

# Cargar processor
print('[1] Cargando processor...')
processor = AutoProcessor.from_pretrained('google/medgemma-1.5-4b-it', token=os.getenv('HF_TOKEN'))

# Token de imagen correcto
token = getattr(processor.tokenizer, 'image_token', '<image_soft_token>')
print(f'[2] Token detectado: {repr(token)}')

# Prompt CON token
prompt = f'{token}\nDescribe esta radiografía'
print(f'[3] Prompt (primeros 100 chars): {prompt[:100]}...')
print(f'[4] Prompt length: {len(prompt)}')

# Procesar CON el método clásico
print('[5] Procesando con processor(text, images)...')
try:
    inputs = processor(text=prompt, images=img, return_tensors='pt')
    print(f'[6] ✅ SUCCESS! Input keys: {list(inputs.keys())}')
    print(f'    - input_ids shape: {inputs["input_ids"].shape}')
    print(f'    - attention_mask shape: {inputs.get("attention_mask", "N/A").shape}')
    if 'pixel_values' in inputs:
        print(f'    - pixel_values shape: {inputs["pixel_values"].shape}')
    if 'image_sizes' in inputs:
        print(f'    - image_sizes: {inputs["image_sizes"]}')
    
    # Contar tokens de imagen en input_ids
    image_token_id = processor.tokenizer.convert_tokens_to_ids(token)
    count = (inputs['input_ids'] == image_token_id).sum().item()
    print(f'[7] Tokens de imagen en input_ids: {count}')
    
except Exception as e:
    print(f'[❌] ERROR: {e}')
    import traceback
    traceback.print_exc()

#!/usr/bin/env python3
"""Test desde dentro del contexto de app.py - reutiliza variables globales"""

import sys
import os
os.environ['TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL'] = '1'

import logging
logging.getLogger('transformers').setLevel(logging.ERROR)

import torch
from PIL import Image
import numpy as np
import time

# Importar desde app
sys.path.insert(0, '/d:/RadiAPP')
from config import HF_TOKEN

# Importar funciones de app
from model_loader import load_model
from app import generate_with_beam_search, ensure_model_loaded, model, processor

print('[1/6] Model cargado?')
try:
    ensure_model_loaded()
    print('    ✓ Model loaded')
except Exception as e:
    print(f'    ❌ Error loading model: {e}')
    sys.exit(1)

print('[2/6] Creando imagen...')
img = Image.fromarray(np.random.randint(50, 150, (256, 256), dtype=np.uint8))
print(f'    ✓ Image {img.size}')

print('[3/6] Creando mensajes...')
prompt = "Describe this medical image briefly"
messages = [
    {"role": "user", "content": [
        {"type": "image", "image": img},
        {"type": "text", "text": prompt}
    ]}
]
print('    ✓ Messages created')

print('[4/6] apply_chat_template...')
try:
    inputs = processor.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
    )
    img_token_id = processor.tokenizer.image_token_id
    img_count = (inputs['input_ids'] == img_token_id).sum().item()
    print(f'    ✓ Inputs ready, image tokens: {img_count}')
    
    if img_count == 0:
        print('    ❌ ERROR: No image tokens!')
        sys.exit(1)
except Exception as e:
    print(f'    ❌ Error: {e}')
    sys.exit(1)

print('[5/6] Generando...')
try:
    t0 = time.time()
    outputs = generate_with_beam_search(inputs, model, processor, max_new_tokens=50, num_beams=1)
    elapsed = time.time() - t0
    print(f'    ✓ Generated in {elapsed:.2f}s')
except Exception as e:
    print(f'    ❌ Error: {e}')
    sys.exit(1)

print('[6/6] Decodificando...')
try:
    response = processor.tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f'    ✓ Response: {response[:80]}...')
except Exception as e:
    print(f'    ❌ Error: {e}')
    sys.exit(1)

print('\n✅ TODO FUNCIONA')

#!/usr/bin/env python3
"""Simple test: apply_chat_template + model.generate"""

import sys
import os
os.environ['TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL'] = '1'
os.environ['HF_TOKEN'] = os.getenv('HF_TOKEN', '')

# Silenciar logs
import logging
logging.getLogger('transformers').setLevel(logging.WARNING)
logging.getLogger('torch').setLevel(logging.WARNING)

import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import numpy as np
from dotenv import load_dotenv
import time

load_dotenv()

try:
    # Test 1: Load
    print('[1/5] Cargando processor y model...')
    processor = AutoProcessor.from_pretrained('google/medgemma-1.5-4b-it', token=os.getenv('HF_TOKEN'))
    model = AutoModelForImageTextToText.from_pretrained(
        'google/medgemma-1.5-4b-it',
        torch_dtype=torch.float16,
        device_map='auto',
        token=os.getenv('HF_TOKEN')
    )
    model.eval()
    print(f'    ✓ Model en: {next(model.parameters()).device}')

    # Test 2: Create image
    print('[2/5] Creando imagen de prueba...')
    img = Image.fromarray(np.random.randint(50, 150, (256, 256), dtype=np.uint8))
    print(f'    ✓ Imagen {img.size}')

    # Test 3: apply_chat_template
    print('[3/5] Ejecutando apply_chat_template...')
    messages = [
        {"role": "user", "content": [
            {"type": "image", "image": img},
            {"type": "text", "text": "Describe this medical image"}
        ]}
    ]
    inputs = processor.apply_chat_template(
        messages, tokenize=True, add_generation_prompt=True, return_dict=True, return_tensors="pt"
    )
    print(f'    ✓ Input keys: {list(inputs.keys())}')
    
    # Count image tokens
    img_token_id = processor.tokenizer.image_token_id
    img_count = (inputs['input_ids'] == img_token_id).sum().item()
    print(f'    ✓ Image tokens: {img_count}')
    
    if img_count == 0:
        print('    ❌ ERROR: No image tokens found!')
        sys.exit(1)

    # Test 4: Filter and generate
    print('[4/5] Filtrando inputs y generando...')
    valid_keys = {'input_ids', 'attention_mask', 'pixel_values', 'image_sizes', 'token_type_ids'}
    filtered = {k: v for k, v in inputs.items() if k in valid_keys}
    
    t0 = time.time()
    with torch.inference_mode():
        outputs = model.generate(
            **filtered,
            max_new_tokens=50,
            num_beams=1
        )
    elapsed = time.time() - t0
    print(f'    ✓ Generación completada en {elapsed:.2f}s')

    # Test 5: Decode
    print('[5/5] Decodificando respuesta...')
    response = processor.tokenizer.decode(outputs[0], skip_special_tokens=True)
    print(f'    ✓ Response: {response[:100]}...')
    
    print('\n✅ TODO FUNCIONA CORRECTAMENTE')
    
except Exception as e:
    print(f'\n❌ ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)

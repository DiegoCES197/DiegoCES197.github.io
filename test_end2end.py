#!/usr/bin/env python3
"""Test end-to-end con apply_chat_template"""

import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import numpy as np
import os
from dotenv import load_dotenv
import time

load_dotenv()
os.environ['TORCH_ROCM_AOTRITON_ENABLE_EXPERIMENTAL'] = '1'

# Crear imagen de prueba
img = Image.fromarray(np.random.randint(50, 150, (512, 512), dtype=np.uint8))

# Cargar model y processor
print('[1] Cargando processor y model...')
processor = AutoProcessor.from_pretrained('google/medgemma-1.5-4b-it', token=os.getenv('HF_TOKEN'))
model = AutoModelForImageTextToText.from_pretrained(
    'google/medgemma-1.5-4b-it',
    torch_dtype=torch.float16,
    device_map='auto',
    token=os.getenv('HF_TOKEN')
)
model.eval()

print('[2] Modelo cargado en device:', next(model.parameters()).device)

# Prompt simple
prompt = "Describe briefly: What do you see in this image?"

# Usar apply_chat_template (FORMA CORRECTA)
print('[3] Preparando inputs con apply_chat_template...')
messages = [
    {"role": "user", "content": [
        {"type": "image", "image": img},
        {"type": "text", "text": prompt}
    ]}
]

inputs = processor.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_dict=True,
    return_tensors="pt"
)

print(f'[4] Input keys: {list(inputs.keys())}')
print(f'    input_ids shape: {inputs["input_ids"].shape}')
if 'pixel_values' in inputs:
    print(f'    pixel_values shape: {inputs["pixel_values"].shape}')

# Contar image tokens
image_token_id = processor.tokenizer.image_token_id
count = (inputs['input_ids'] == image_token_id).sum().item()
print(f'[5] Image tokens in input_ids: {count}')

# Filtrar inputs válidos (igual a app.py)
valid_keys = {'input_ids', 'attention_mask', 'pixel_values', 'image_sizes', 'token_type_ids'}
filtered_inputs = {k: v for k, v in inputs.items() if k in valid_keys}
print(f'[6] Filtered keys: {list(filtered_inputs.keys())}')

# Generar
print('[7] Generando...')
t0 = time.time()
with torch.inference_mode():
    outputs = model.generate(
        **filtered_inputs,
        max_new_tokens=100,
        num_beams=1
    )
elapsed = time.time() - t0
print(f'[8] ✅ Generación completada en {elapsed:.2f}s')

# Decodificar
response = processor.tokenizer.decode(outputs[0], skip_special_tokens=True)
print(f'[9] Response (primeros 200 chars):\n{response[:200]}...')

#!/usr/bin/env python3
"""Test: processor(text, images) vs apply_chat_template"""

import os
os.environ['HF_TOKEN'] = os.getenv('HF_TOKEN', '')

import torch
from transformers import AutoProcessor, AutoModelForImageTextToText
from PIL import Image
import numpy as np
from dotenv import load_dotenv

load_dotenv()

print('[1] Loading processor and model...')
processor = AutoProcessor.from_pretrained('google/medgemma-1.5-4b-it', token=os.getenv('HF_TOKEN'))
model = AutoModelForImageTextToText.from_pretrained(
    'google/medgemma-1.5-4b-it',
    torch_dtype=torch.float16,
    device_map='auto',
    token=os.getenv('HF_TOKEN')
)
model.eval()

print('[2] Creating test image...')
img = Image.fromarray(np.random.randint(50, 150, (512, 512), dtype=np.uint8))
print(f'    Image: {img.size}')

prompt = "Describe this medical image"

print('\n[3] METHOD 1: processor(text, images) with formatted text')
try:
    # Format text with apply_chat_template (without tokenize)
    messages = [
        {"role": "user", "content": [
            {"type": "image", "image": None},
            {"type": "text", "text": prompt}
        ]}
    ]
    
    templated_text = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    print(f"    Templated text length: {len(templated_text)}")
    print(f"    First 150 chars: {templated_text[:150]}")
    
    # Now process with processor()
    inputs = processor(
        text=templated_text,
        images=img,
        return_tensors="pt",
        padding=True
    )
    
    print(f"    ✓ Input keys: {list(inputs.keys())}")
    
    # Check for image tokens
    img_token_id = processor.tokenizer.image_token_id
    img_count = (inputs['input_ids'] == img_token_id).sum().item()
    print(f"    ✓ Image tokens found: {img_count}")
    
    if img_count > 0:
        print("    ✅ METHOD 1 SUCCESS!")
    else:
        print("    ❌ METHOD 1 FAILED - No image tokens")
        
except Exception as e:
    print(f"    ❌ ERROR: {e}")

print('\n[4] METHOD 2: apply_chat_template(messages with image, tokenize=True)')
try:
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
    
    print(f"    ✓ Input keys: {list(inputs.keys())}")
    
    # Check for image tokens
    img_token_id = processor.tokenizer.image_token_id
    img_count = (inputs['input_ids'] == img_token_id).sum().item()
    print(f"    ✓ Image tokens found: {img_count}")
    
    if img_count > 0:
        print("    ✅ METHOD 2 SUCCESS!")
    else:
        print("    ❌ METHOD 2 FAILED - No image tokens")
        
except Exception as e:
    print(f"    ❌ ERROR: {e}")

print('\n[5] Testing generation with METHOD 1...')
try:
    # Use METHOD 1 for generation
    messages = [
        {"role": "user", "content": [
            {"type": "image", "image": None},
            {"type": "text", "text": prompt}
        ]}
    ]
    
    templated_text = processor.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )
    
    inputs = processor(
        text=templated_text,
        images=img,
        return_tensors="pt",
        padding=True
    )
    
    # Move to model device
    for key in inputs:
        if hasattr(inputs[key], 'to'):
            inputs[key] = inputs[key].to(model.device)
    
    # Generate
    with torch.inference_mode():
        outputs = model.generate(**inputs, max_new_tokens=50)
    
    # Decode
    generated_text = processor.tokenizer.batch_decode(outputs, skip_special_tokens=True)[0]
    print(f"    ✓ Generated: {generated_text[:100]}...")
    print("    ✅ GENERATION SUCCESS!")
    
except Exception as e:
    print(f"    ❌ GENERATION ERROR: {e}")
    import traceback
    traceback.print_exc()

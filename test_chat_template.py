#!/usr/bin/env python3
"""Full chat template"""

from transformers import AutoProcessor
import os
from dotenv import load_dotenv

load_dotenv()

processor = AutoProcessor.from_pretrained('google/medgemma-1.5-4b-it', token=os.getenv('HF_TOKEN'))

print("=== FULL CHAT TEMPLATE ===")
if hasattr(processor, 'chat_template'):
    print(processor.chat_template)

print("\n=== USING apply_chat_template ===")
# Estructura correcta para Gemma3
messages = [
    {"role": "user", "content": [
        {"type": "image", "image": "IMAGE_PLACEHOLDER"},
        {"type": "text", "text": "Describe esta radiografía"}
    ]}
]

try:
    result = processor.apply_chat_template(
        messages,
        tokenize=False,  # Solo ver el texto, no tokenizar
        add_generation_prompt=True
    )
    print(f"Result type: {type(result)}")
    print(f"Result (primeros 300 chars): {str(result)[:300]}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== IMAGE TOKEN ID ===")
print(f"processor.image_token: {processor.image_token}")
print(f"processor.image_token_id: {processor.image_token_id}")

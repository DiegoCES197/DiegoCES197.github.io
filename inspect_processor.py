#!/usr/bin/env python3
"""Inspect processor tokens"""

from transformers import AutoProcessor
import os
from dotenv import load_dotenv

load_dotenv()

processor = AutoProcessor.from_pretrained('google/medgemma-1.5-4b-it', token=os.getenv('HF_TOKEN'))

print("=== PROCESSOR ATTRIBUTES ===")
print(f"Dir processor: {[x for x in dir(processor) if not x.startswith('_')][:20]}")

print("\n=== TOKENIZER INFO ===")
tokenizer = processor.tokenizer
print(f"Tokenizer class: {type(tokenizer)}")
print(f"Special tokens: {tokenizer.special_tokens_map}")

# Buscar image token
if hasattr(tokenizer, 'image_token'):
    print(f"tokenizer.image_token: {tokenizer.image_token}")
if hasattr(tokenizer, 'image_id'):
    print(f"tokenizer.image_id: {tokenizer.image_id}")

print("\n=== TRYING TO CONVERT TOKENS ===")
try:
    img_token_id = tokenizer.convert_tokens_to_ids('<image_soft_token>')
    print(f"Token ID for '<image_soft_token>': {img_token_id}")
except Exception as e:
    print(f"❌ Error: {e}")

# Probar con formato brace
try:
    img_token_id = tokenizer.convert_tokens_to_ids('<|image_soft_token|>')
    print(f"Token ID for '<|image_soft_token|>': {img_token_id}")
except Exception as e:
    print(f"❌ Error: {e}")

print("\n=== VOCAB CHECK ===")
vocab = tokenizer.get_vocab()
image_tokens = [k for k in vocab.keys() if 'image' in k.lower()]
print(f"Tokens con 'image': {image_tokens}")

print("\n=== CHAT TEMPLATE ===")
if hasattr(tokenizer, 'chat_template'):
    ct = tokenizer.chat_template
    if ct:
        print(f"Chat template (primeros 500 chars):\n{ct[:500]}")

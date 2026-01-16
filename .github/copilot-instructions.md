# RadiAPP - AI Coding Assistant Instructions

## Project Overview
RadiAPP generates medical radiology reports from radiological images using Google's MedGemma-1.5-4b-it vision-language model. All output and user-facing text must be Spanish.

**Tech Stack:** Python 3.12.9 | PyTorch 2.9.0+ROCm 7.11 | Gradio 6.3.0 | Transformers 4.57.5

## Architecture (4 Independent Modules)

- Main UI and orchestration (748 lines)
- Model loading with device detection (197 lines)
- Few-shot learning and prompt construction (178 lines)
- Image validation, JSON parsing, template editing (354 lines)
- Template management with CRUD operations (88 lines)

Each module is standalone with clear responsibilities. No circular dependencies. All configuration centralized.

## Environment Setup (ROCm + MedGemma)

### 1. Create Virtual Environment
```powershell
python -m venv llm-pyt
.\llm-pyt\Scripts\Activate.ps1
```

### 2. Install PyTorch for AMD ROCm
Download PyTorch wheels from AMD ROCm repository. For Python 3.12 + ROCm 7.11:

```powershell
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/rocm5.11
```

Required: ROCm driver compatible with GPU. Verify with rocm-smi.

### 3. Install Project Dependencies
```powershell
pip install -r requirements.txt
```

### 4. Test MedGemma Setup
```powershell
python -c "from transformers import AutoProcessor, AutoModelForImageTextToText; print('OK')"
```

### 5. Configure HF Token
Create .env file in project root:
```
HF_TOKEN=hf_your_token_here
```

## Critical Developer Workflows

### Running the Application
```powershell
python -m gradio main_application.py
pytest testing_suite/ -v
.\start_application.bat
```

### Model Setup Details
- Auth Required: HF_TOKEN environment variable (gated model access)
- First Run: ~8GB model download to hf_cache/
- Device: GPU ROCm (float16) if available; CPU fallback (float32)

## Project-Specific Patterns

### 1. Image Token Handling (CRITICAL)
Always use processor.apply_chat_template() for prompt formatting:

```python
messages = [
    {"role": "user", "content": [
        {"type": "image", "image": img},
        {"type": "text", "text": prompt_text}
    ]}
]

inputs = processor.apply_chat_template(
    messages, add_generation_prompt=True, tokenize=True,
    return_dict=True, return_tensors="pt"
)

outputs = model.generate(**inputs, max_new_tokens=512)
response = processor.batch_decode(outputs, skip_special_tokens=True)[0]
```

Never manually insert image tokens. Warnings about "memory_efficient_attention" with AMD ROCm are expected and safe.

### 2. Few-Shot Learning (User Examples)
User examples in feedback/good_examples.json are dynamically loaded:
- Format: [{"label": "...", "example": {...}}]
- Last 2 examples prioritized in prompts
- Add via Gradio "Feedback" tab or save_good_example() function

### 3. JSON Parsing Pipeline
Model outputs may contain markdown or extra text:
1. Try markdown blocks first
2. Fallback: extract balanced braces from first {
3. Apply template edits via apply_edits()
4. Run audit_report_internal() for quality flags

### 4. Image Validation (Pre-flight Check)
Called before inference to avoid wasted compute:
- Detects black images (mean < 20)
- Detects white/overexposed images (mean > 240)
- Detects uniform/corrupted images (std < 5)

### 5. Template System
JSON templates stored in templates/ directory with name and template_text keys. Managed with CRUD operations and import from TXT/DOCX/JSON.

### 6. Environment and Config
Configuration loads .env without external dependencies. Key vars: MODEL_ID, HF_TOKEN, MAX_IMAGE_SIZE, DEFAULT_MAX_TOKENS, CPU_NUM_THREADS.

## Testing and Quality Assurance

Before commits: pytest testing_suite/ -v

- Unit tests: each module independently tested
- GPU mocking: run tests without GPU via test configuration
- Coverage target: 70-85% per module

Critical smoke tests:
- test_validate_image_quality_normal
- test_build_prompt_contains_image_token
- test_extract_json_block_*
- test_model_loader_device_detection

MedGemma Testing Notes:
- ROCm GPU required for full model tests; CPU tests use mocks
- "memory_efficient_attention not available" warning is expected and safe
- First test run downloads 8GB model; subsequent runs use cache
- HF_TOKEN must be set in .env for gated model access

## AI Agent Implementation Guidance

When implementing features or fixes:

1. Environment and Dependencies:
   - Always assume HF_TOKEN in .env is required for model access
   - ROCm GPU is optional; code must support CPU fallback
   - Do not add new dependencies without updating requirements

2. MedGemma Integration:
   - Use processor.apply_chat_template() ALWAYS for prompt formatting
   - Never manually construct image tokens—let processor handle it
   - Parse model JSON outputs using extract_json_block() for robustness
   - Call validate_image_quality() BEFORE generate() to save compute

3. Code Structure:
   - Keep modules independent with no circular imports
   - Centralize all constants in configuration
   - All user-facing strings must be in Spanish

4. Testing and Verification:
   - Run pytest testing_suite/ -v before committing
   - Mock GPU in tests via test configuration
   - Test edge cases: black images, malformed JSON, missing templates

5. Logging and Debugging:
   - Use logger.info() for workflow milestones
   - Use logger.warning() for recoverable issues
   - Include line numbers in logs for debugging

6. Documentation:
   - Update markdown files if changing workflows or adding patterns
   - Reference specific line numbers when documenting code
   - Keep documentation in Spanish; technical docs can be bilingual

## Key Code Sections

The following files contain critical implementations:

- Main application (lines 244-350) - generate() inference pipeline
- Configuration module (lines 1-100) - Model ID, HF token, constants
- Prompt builder (lines 73-130) - build_prompt() core logic
- Report processor (lines 16-79) - Validation and JSON parsing
- Model loader (lines 34-120) - GPU/CPU device selection

## Documentation Reference

Project documentation includes:

- Architecture diagrams and data flow documentation
- Installation and first run guide
- Performance strategies and optimizations
- Complete file and module reference
- Testing guide for contributors

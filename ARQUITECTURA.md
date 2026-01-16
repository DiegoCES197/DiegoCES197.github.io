# 🏗️ Arquitectura RadiAPP v2.0 - Diagrama Detallado

## Capas de Procesamiento

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INPUT LAYER                                 │
├─────────────────────────────────────────────────────────────────────┤
│  Imagen (PIL)    Modalidad    Región    Indicación    Extras        │
│      ↓               ↓           ↓           ↓           ↓          │
│  [JPG/PNG]       [TC/RM/RX]   [Cráneo]   [Cefalea]   [Trauma]      │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                   VALIDATION LAYER (NUEVO)                          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  validate_image_quality(img)                                        │
│  ├─ Check: std_dev > 5     ✓ No uniforme                            │
│  ├─ Check: brightness 5-240 ✓ No too dark/bright                   │
│  └─ Output: (valid: bool, reason: str)                             │
│                                                                     │
│  IF NOT valid → RETURN Error ✗                                     │
│  ELSE → Continue ✓                                                  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│              PREPROCESSING & PROMPT BUILDING LAYER                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Image Processing:                                                  │
│  ├─ Convert to RGB                                                  │
│  ├─ Resize to 896×896 (recomendado MedGemma)                        │
│  └─ Output: PIL.Image (normalized)                                  │
│                                                                     │
│  Prompt Building: build_prompt()                                    │
│  ├─ TOKEN DE IMAGEN (gestionado por processor)                    │
│  ├─ TAREA + REGLAS CRÍTICAS                                        │
│  ├─ PLANTILLA A EDITAR                                             │
│  ├─ CONTEXTO (modalidad/región/indicación/extras)                  │
│  ├─ GUÍA POR MODALIDAD (get_prompt_by_modalidad)                  │
│  ├─ FEW-SHOT (format_fewshot_prompt)                              │
│  │   ├─ load_good_examples() → good_examples.json                │
│  │   └─ Últimos 2 ejemplos                                         │
│  └─ ESQUEMA JSON + JSON mínimo de fallback                         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                 PROCESSOR & MODEL INFERENCE LAYER                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Processor (AutoProcessor):                                         │
│  ├─ Image → Features                                               │
│  ├─ Prompt → Tokens                                                │
│  ├─ Chat Template: apply_chat_template() (preferido en MedGemma)   │
│  └─ Output: {input_ids, pixel_values, attention_mask, ...}        │
│                                                                     │
│  Model Inference (MedGemma 1.5 4B):                               │
│  ├─ generate_with_beam_search()                                    │
│  │   ├─ num_beams=1 (actual, rápido)                             │
│  │   ├─ max_new_tokens=512                                         │
│  │   ├─ do_sample=False (determinístico)                          │
│  │   └─ no_repeat_ngram_size=2                                     │
│  │                                                                  │
│  └─ Output: [token_ids_1, token_ids_2, ...]                       │
│                                                                     │
│  Decoding:                                                          │
│  └─ processor.batch_decode() → raw_text                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                    JSON EXTRACTION & CLEANUP LAYER                  │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Raw Output Cleaning:                                               │
│  ├─ Remove markers (--- PLANTILLA ---)                            │
│  ├─ Remove bad tokens (<thought>, <unused>)                       │
│  └─ Output: cleaned_text                                           │
│                                                                     │
│  JSON Extraction (regex):                                           │
│  ├─ Pattern: \\{.*\\}                                              │
│  ├─ Fallback: Try multiple strategies                              │
│  └─ Output: json_dict                                              │
│                                                                     │
│  JSON Parse:                                                        │
│  ├─ json.loads(json_str)                                           │
│  ├─ Try-except: handle malformed                                   │
│  └─ Output: validated json_dict                                    │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│              POST-PROCESSING & CONFIDENCE LAYER (NUEVO)            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  analyze_uncertainty_tokens():                                      │
│  ├─ Scan: \"podría\" (0.60), \"probable\" (0.70), etc             │
│  ├─ Score each add_finding                                         │
│  ├─ Output: confidence_scores in JSON                              │
│  └─ Example: {\"hallazgo1\": 0.95, \"hallazgo2\": 0.45}           │
│                                                                     │
│  apply_edits() → ENHANCED:                                         │
│  ├─ Parse: remove_findings, replace_findings, add_findings        │
│  ├─ Extract: confidence_scores from JSON                           │
│  ├─ Annotate: findings < 0.5 with [⚠️ baja confianza: 45%]      │
│  ├─ Merge: with template HALLAZGOS                                 │
│  ├─ Build: CONCLUSIÓN block                                        │
│  └─ Output: formatted_report                                       │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│           MULTI-TURN ANALYSIS & VALIDATION LAYER (NUEVO)          │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  multi_turn_refinement():                                           │
│  ├─ Check: LESIÓMETRO missing > 3 → Flag incompletitud            │
│  ├─ Check: Confidence scores < 0.5 > 2 → Flag baja confianza     │
│  ├─ Check: DDX vacío o 1 opción → Flag insuficiente               │
│  └─ Output: report + analysis section                             │
│                                                                     │
│  audit_report_internal():                                          │
│  ├─ Check 1: Coherencia (hallazgos + conclusión vacía)            │
│  ├─ Check 2: Omisiones (previos no mencionados)                   │
│  ├─ Check 3: Lenguaje (muy definitivo vs probabilístico)          │
│  ├─ Check 4: Medidas (tamaños específicos incluidos)              │
│  ├─ Check 5: Prohibiciones (tratamiento detectado)                │
│  ├─ Check 6: Diferencial (DDX presente)                           │
│  ├─ Check 7: Limitaciones (técnicas mencionadas)                  │
│  ├─ Check 8: Confianza baja (hallazgos marcados)                  │
│  └─ Output: report + audit section with flags/suggestions         │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────────┐
│                     FINAL OUTPUT & FEEDBACK LAYER                   │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  Output Structure:                                                  │
│  ├─ Section 1: HALLAZGOS                                          │
│  ├─ Section 2: CONCLUSIÓN                                         │
│  ├─ Section 3: 🔍 AUDITORÍA INTERNA                              │
│  │             ├─ ✅ Sin flags / ⚠️ Flags detectados            │
│  │             └─ Recomendaciones                                 │
│  └─ Section 4: 📊 ANÁLISIS DE COMPLETITUD (si aplica)           │
│                ├─ Warnings sobre omisiones                        │
│                └─ Sugerencias de mejora                           │
│                                                                     │
│  Feedback Loop (GRADIO UI):                                         │
│  ├─ Tab \"Feedback\" → Section \"Aprendizaje Continuo\"          │
│  ├─ User: Copia JSON + escribe descripción                        │
│  ├─ Click: \"💾 Guardar como ejemplo bueno\"                    │
│  │                                                                 │
│  └─ save_good_example() → good_examples.json                      │
│      └─ Próxima generación similar:                               │
│          load_good_examples() → build_prompt() → mejora ✓        │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Flujo de Control Principal

```
START
  ↓
generate(image, modalidad, region, indicacion, extras, template_file, max_new_tokens)
  ↓
validate_image_quality(img)
  ├─ PASS ✓ → Continue
  └─ FAIL ✗ → RETURN Error
  ↓
build_prompt(modalidad, region, ...)
  ├─ load_good_examples()
  ├─ get_prompt_by_modalidad(modalidad)
  ├─ format_fewshot_prompt()
  └─ RETURN full_prompt
  ↓
processor(...) → inputs
  ↓
generate_with_beam_search(inputs, model, 512, num_beams=1)
  ↓
processor.batch_decode(outputs)
  ├─ Remove markers (--- PLANTILLA ---)
  ├─ Remove bad tokens (<thought>)
  └─ RETURN cleaned_text
  ↓
extract_json_block(cleaned_text)
  ├─ Regex: \\{.*\\}
  ├─ json.loads()
  └─ RETURN json_dict
  ↓
analyze_uncertainty_tokens(text, json_dict)
  ├─ Scan uncertainty markers
  ├─ Assign confidence_scores
  └─ UPDATE json_dict
  ↓
apply_edits(template_text, json_text)
  ├─ Parse remove/replace/add_findings
  ├─ Extract confidence_scores
  ├─ Annotate < 0.5 with ⚠️
  ├─ Apply to template
  └─ RETURN formatted_report
  ↓
multi_turn_refinement(report, json_dict, template, img)
  ├─ Check LESIÓMETRO, confidence, DDX
  ├─ Add analysis section if needed
  └─ RETURN (report_with_analysis, json_dict)
  ↓
audit_report_internal(report, template, hallazgos_bool)
  ├─ Run 8 checks (coherence, language, etc)
  ├─ Generate flags if issues
  └─ RETURN report_with_audit_section
  ↓
RETURN final_report
  ↓
[UI displays report + flags]
  ↓
[User optionally saves as good example via feedback UI]
  ↓
save_good_example() → good_examples.json
  ↓
END
```

---

## Data Flow Diagram

```
┌──────────────┐
│   Image      │
│  JPG/PNG     │
└──────┬───────┘
       │
       ├─→ validate_image_quality()
       │   └─→ (bool, str)
       │
       ├─→ Resize to 1280x1280
       │
       ├─→ Processor
       │   └─→ {pixel_values, input_ids, ...}
       │
       ├─→ MedGemma Model
       │   └─→ {token_ids_1, token_ids_2, ...}
       │
       ├─→ Decode
       │   └─→ raw_text (with garbage)
       │
       ├─→ Regex JSON Extract
       │   └─→ json_dict (structured)
       │
       ├─→ analyze_uncertainty_tokens()
       │   └─→ confidence_scores {field: 0.xx}
       │
       ├─→ apply_edits()
       │   ├─→ Template
       │   └─→ Formatted Report + ⚠️ annotations
       │
       ├─→ multi_turn_refinement()
       │   └─→ Analysis of completeness
       │
       ├─→ audit_report_internal()
       │   └─→ 8 validation checks + flags
       │
       └─→ FINAL REPORT
           └─→ User UI
               └─→ [Optionally save as good example]
                   └─→ good_examples.json
```

---

## Component Dependencies

```
app.py
├── Imports
│   ├── transformers (AutoProcessor, AutoModelForImageTextToText)
│   ├── torch
│   ├── PIL (Image)
│   ├── numpy
│   ├── json, re
│   ├── gradio
│   └── os, sys, time, csv, datetime
│
├── Global Variables
│   ├── COMMON_FINDINGS (dict)
│   ├── DIAGNOSTIC_CRITERIA (dict)
│   ├── FEWSHOT_EXAMPLES (list)
│   ├── GOOD_EXAMPLES_FILE (str path)
│   ├── BASE_DIR, TEMPLATES_DIR, FEEDBACK_CSV
│   └── processor, model (loaded on startup)
│
├── Helper Functions
│   ├── validate_image_quality(img) → (bool, str)
│   ├── get_prompt_by_modalidad(modalidad) → str
│   ├── format_fewshot_prompt(examples) → str
│   ├── load_good_examples() → list
│   ├── save_good_example(example) → None
│   ├── analyze_uncertainty_tokens(text, json) → dict
│   ├── generate_with_beam_search(inputs, model, max, beams) → tensor
│   ├── extract_json_block(text) → str
│   ├── apply_edits(template, json_str) → str
│   ├── audit_report_internal(report, template, bool) → str
│   └── multi_turn_refinement(report, json, template, img) → (str, dict)
│
├── Core Functions
│   ├── build_prompt(modalidad, region, indicacion, extras, template) → str
│   ├── generate(img, modalidad, region, indicacion, extras, template, max_tokens) → str
│   ├── read_template(filename) → dict
│   ├── write_template(filename, data) → str
│   ├── list_templates() → list
│   ├── load_template_to_editor(file) → (str, str)
│   ├── save_template_from_editor(file, name, text) → (str, str, dropdown)
│   ├── save_feedback(...) → str
│   └── save_good_example_ui(json_str, label) → str [UI wrapper]
│
└── Gradio Interface
    ├── Tab 1: \"Generar\"
    │   ├── Image input
    │   ├── Dropdowns: modalidad, region, template
    │   ├── Textboxes: indicacion, extras, max_tokens
    │   ├── Button: \"Generar\"
    │   └─→ generate() → Output textbox
    │
    ├── Tab 2: \"Plantillas\"
    │   ├── Dropdown: existing templates
    │   ├── Textboxes: name, content
    │   ├── Buttons: Load, Save, Import
    │   └─→ {read/write/import}_template() functions
    │
    └── Tab 3: \"Feedback\"
        ├── Section 1: Traditional Feedback
        │   ├── Dropdowns: template, modalidad
        │   ├── Textboxes: region, indicacion, output, comentario
        │   ├── Radio: rating
        │   ├── Button: \"Guardar feedback\"
        │   └─→ save_feedback() → feedback.csv
        │
        └── Section 2: Continuous Learning ⭐
            ├── Textbox: JSON input
            ├── Textbox: Example label
            ├── Button: \"💾 Guardar como ejemplo bueno\"
            └─→ save_good_example_ui() → good_examples.json
```

---

## Integration Points

```
┌─────────────────────────────────────────────────────────┐
│                    EXTERNAL SYSTEMS                     │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  HuggingFace Hub                                        │
│  └─→ transformers.AutoModel.from_pretrained()         │
│      └─→ google/medgemma-1.5-4b-it                    │
│                                                         │
│  File System                                            │
│  ├─→ templates/*.json                                  │
│  ├─→ feedback/feedback.csv                             │
│  ├─→ good_examples.json                               │
│  └─→ OPTIMIZACIONES.md, QUICK_START.md                │
│                                                         │
│  User Input (Gradio)                                   │
│  ├─→ Image upload                                      │
│  ├─→ Form fields                                       │
│  └─→ Feedback submission                               │
│                                                         │
│  Output (HTML/JSON/CSV)                                │
│  ├─→ HTML rendered in Gradio                           │
│  ├─→ JSON in feedback tab                              │
│  └─→ CSV logs                                          │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Performance Waterfall

```
Timeline (milliseconds)
├─ 0-10ms:    validate_image_quality() ✓
├─ 10-50ms:   build_prompt() ✓
├─ 50-100ms:  Processor conversion ✓
├─ 100-600ms: Processor tokenization ✓
├─ 600ms-5s:  Model inference (bottleneck)
├─ 5-5.1s:    Decode output ✓
├─ 5.1-5.15s: analyze_uncertainty_tokens() ✓
├─ 5.15-5.25s: apply_edits() ✓
├─ 5.25-5.35s: multi_turn_refinement() ✓
├─ 5.35-5.45s: audit_report_internal() ✓
└─ 5.45-5.5s: Return to UI ✓

Total: ~4-6 seconds on CPU
```

---

## Feedback Loop Architecture

```
ITERATION N
├─ generate() → Report
├─ User reviews
└─ IF satisfied:
   ├─ User copies JSON
   ├─ User writes description
   ├─ User clicks \"💾 Guardar como ejemplo bueno\"
   ├─ save_good_example_ui()
   │   └─→ json.dumps() → good_examples.json
   │
   ITERATION N+1
   ├─ load_good_examples()
   │   ├─→ Reads from good_examples.json
   │   └─→ Returns [example1, example2, ..., new_example]
   │
   ├─ build_prompt()
   │   ├─→ format_fewshot_prompt(examples)
   │   └─→ Inserts best 2 examples into prompt
   │
   ├─ generate() → IMPROVED Report
   └─ System learns automatically ✓
```

---

Esta arquitectura garantiza:
✅ **Modularidad:** Cada función independiente  
✅ **Escalabilidad:** Fácil agregar más checks/optimizaciones  
✅ **Robustez:** Validación en múltiples capas  
✅ **Observabilidad:** Auditoría + flags en cada paso  
✅ **Aprendizaje:** Feedback loop automático  


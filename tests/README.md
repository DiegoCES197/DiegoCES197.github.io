# RadiAPP Test Suite

Suite completa de tests con pytest para RadiAPP v2.3

## Estructura

```
tests/
├── conftest.py                    # Configuración pytest
├── test_model_loader.py           # Tests carga modelo en CPU
├── test_prompt_builder.py         # Tests construcción prompts + few-shot
├── test_report_processor.py       # Tests validación + JSON + ediciones
└── test_template_manager.py       # Tests CRUD plantillas
```

## Instalación

```powershell
pip install pytest pytest-cov
```

## Ejecución

### Todos los tests
```powershell
pytest tests/ -v
```

### Test específico
```powershell
pytest tests/test_prompt_builder.py -v
```

### Con coverage
```powershell
pytest tests/ -v --cov=. --cov-report=html
```

### Tests críticos (smoke test)
```powershell
pytest tests/ -v -k "test_build_prompt_contains_image_token or test_validate_image_quality_normal"
```

## Coverage esperado

- `model_loader.py`: ~70% (mocking básico de CPU)
- `prompt_builder.py`: ~85%
- `report_processor.py`: ~80%
- `template_manager.py`: ~85%

## Tests críticos

1. **`test_build_prompt_contains_image_token`** - Verifica que `<image>` NO sea eliminado
2. **`test_validate_image_quality_normal_image`** - Validación de imágenes funciona
3. **`test_apply_edits_combined`** - Pipeline de ediciones JSON funcional
4. **`test_load_model_returns_tuple`** - Carga del modelo básica funciona

## Notas

- Algunos tests requieren mocking del loader (CPU)
- Tests de `model_loader.py` pueden fallar si no hay GPU disponible
- Para CI/CD, usar: `pytest tests/ -v -k "not test_load_model"`

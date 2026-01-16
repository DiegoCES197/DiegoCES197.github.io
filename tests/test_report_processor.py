"""
Suite de tests para report_processor.py
Tests para validación de imágenes, parsing JSON, aplicación de ediciones, auditoría
"""
import pytest
import json
import numpy as np
from PIL import Image
import sys
import os

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from report_processor import (
    validate_image_quality,
    extract_json_block,
    apply_edits
)


class TestImageValidation:
    """Tests para validación de calidad de imagen"""
    
    def test_validate_image_quality_normal_image(self):
        """Test que imagen normal pasa validación"""
        # Crear imagen sintética con contraste normal
        array = np.random.randint(50, 200, (512, 512, 3), dtype=np.uint8)
        img = Image.fromarray(array, mode='RGB')
        
        is_valid, msg = validate_image_quality(img)
        
        assert is_valid == True, "Imagen normal debe ser válida"
        assert msg == "", "No debe haber mensaje de error"
    
    def test_validate_image_quality_too_dark(self):
        """Test que imagen muy oscura falla validación"""
        # Imagen casi negra
        array = np.zeros((512, 512, 3), dtype=np.uint8)
        array[:, :, :] = 10  # Muy oscuro
        img = Image.fromarray(array, mode='RGB')
        
        is_valid, msg = validate_image_quality(img)
        
        assert is_valid == False, "Imagen muy oscura debe fallar"
        assert "oscura" in msg.lower()
    
    def test_validate_image_quality_too_bright(self):
        """Test que imagen sobreexpuesta falla validación"""
        # Imagen casi blanca
        array = np.full((512, 512, 3), 250, dtype=np.uint8)
        img = Image.fromarray(array, mode='RGB')
        
        is_valid, msg = validate_image_quality(img)
        
        assert is_valid == False, "Imagen sobreexpuesta debe fallar"
        assert "clara" in msg.lower() or "sobreexpuesta" in msg.lower()
    
    def test_validate_image_quality_no_contrast(self):
        """Test que imagen sin contraste falla validación"""
        # Imagen completamente uniforme
        array = np.full((512, 512, 3), 128, dtype=np.uint8)
        img = Image.fromarray(array, mode='RGB')
        
        is_valid, msg = validate_image_quality(img)
        
        assert is_valid == False, "Imagen sin contraste debe fallar"
        assert "uniforme" in msg.lower() or "contraste" in msg.lower()


class TestJSONExtraction:
    """Tests para extracción de bloques JSON"""
    
    def test_extract_json_block_clean(self):
        """Test extracción de JSON limpio"""
        text = '{"remove": ["línea 1"], "add_findings": ["hallazgo 1"]}'
        
        result = extract_json_block(text)
        
        assert result == text
        # Verificar que es JSON válido
        json.loads(result)
    
    def test_extract_json_block_with_prefix(self):
        """Test extracción de JSON con texto antes"""
        text = 'Aquí está el resultado: {"remove": [], "add_findings": ["test"]}'
        
        result = extract_json_block(text)
        
        assert result.startswith("{")
        assert result.endswith("}")
        # Debe ser JSON válido
        json.loads(result)
    
    def test_extract_json_block_with_suffix(self):
        """Test extracción de JSON con texto después"""
        text = '{"remove": []} Texto adicional después'
        
        result = extract_json_block(text)
        
        assert result.startswith("{")
        assert "Texto adicional" not in result
        # Debe ser JSON válido
        json.loads(result)
    
    def test_extract_json_block_multiline(self):
        """Test extracción de JSON multilínea"""
        text = '''Resultado:
        {
            "remove": ["línea 1"],
            "add_findings": ["hallazgo 1"]
        }
        Fin del resultado'''
        
        result = extract_json_block(text)
        
        assert result.startswith("{")
        assert result.endswith("}")
        # Debe ser JSON válido
        data = json.loads(result)
        assert "remove" in data
        assert "add_findings" in data
    
    def test_extract_json_block_no_json(self):
        """Test que lanza error si no hay JSON"""
        text = "Texto sin JSON válido"
        
        with pytest.raises(ValueError, match="No se encontró un JSON"):
            extract_json_block(text)


class TestApplyEdits:
    """Tests para aplicación de ediciones JSON sobre plantilla"""
    
    def test_apply_edits_remove(self):
        """Test que remove elimina líneas exactas"""
        template = "Línea 1\nLínea 2\nLínea 3"
        edits = json.dumps({
            "remove": ["Línea 2"],
            "replace": [],
            "add_findings": []
        })
        
        result = apply_edits(template, edits)
        
        assert "Línea 1" in result
        assert "Línea 2" not in result
        assert "Línea 3" in result
    
    def test_apply_edits_replace(self):
        """Test que replace reemplaza líneas exactas"""
        template = "Línea original\nOtra línea"
        edits = json.dumps({
            "remove": [],
            "replace": [{"from": "Línea original", "to": "Línea modificada"}],
            "add_findings": []
        })
        
        result = apply_edits(template, edits)
        
        assert "Línea modificada" in result
        assert "Línea original" not in result
        assert "Otra línea" in result
    
    def test_apply_edits_add_findings(self):
        """Test que add_findings agrega hallazgos después de HALLAZGOS:"""
        template = "HALLAZGOS:\n- Hallazgo previo\n\nCONCLUSIÓN:"
        edits = json.dumps({
            "remove": [],
            "replace": [],
            "add_findings": ["Nuevo hallazgo 1", "Nuevo hallazgo 2"]
        })
        
        result = apply_edits(template, edits)
        
        assert "Nuevo hallazgo 1" in result
        assert "Nuevo hallazgo 2" in result
        assert "HALLAZGOS:" in result
    
    def test_apply_edits_combined(self):
        """Test que aplica remove + replace + add_findings combinados"""
        template = "HALLAZGOS:\nLínea a eliminar\nLínea a modificar\n\nCONCLUSIÓN:"
        edits = json.dumps({
            "remove": ["Línea a eliminar"],
            "replace": [{"from": "Línea a modificar", "to": "Línea modificada"}],
            "add_findings": ["Hallazgo nuevo"]
        })
        
        result = apply_edits(template, edits)
        
        assert "Línea a eliminar" not in result
        assert "Línea modificada" in result
        assert "Hallazgo nuevo" in result
    
    def test_apply_edits_confidence_scores(self):
        """Test que anota hallazgos con baja confianza"""
        template = "HALLAZGOS:\n\nCONCLUSIÓN:"
        edits = json.dumps({
            "remove": [],
            "replace": [],
            "add_findings": ["Hallazgo incierto"],
            "confidence_scores": {"incierto": 0.3}
        })
        
        result = apply_edits(template, edits)
        
        assert "Hallazgo incierto" in result
        # Debe tener anotación de incertidumbre
        assert "INCERTIDUMBRE" in result or "?" in result or "BAJA CONFIANZA" in result
    
    def test_apply_edits_empty_operations(self):
        """Test que maneja operaciones vacías"""
        template = "Plantilla original"
        edits = json.dumps({
            "remove": [],
            "replace": [],
            "add_findings": []
        })
        
        result = apply_edits(template, edits)
        
        # Plantilla debe permanecer igual
        assert "Plantilla original" in result
    
    def test_apply_edits_invalid_json(self):
        """Test que lanza error con JSON inválido"""
        template = "Plantilla"
        edits = "JSON inválido {"
        
        with pytest.raises(json.JSONDecodeError):
            apply_edits(template, edits)


class TestEdgeCases:
    """Tests para casos límite"""
    
    def test_apply_edits_case_sensitivity(self):
        """Test que remove y replace son case-sensitive"""
        template = "Línea Exacta"
        edits = json.dumps({
            "remove": ["línea exacta"],  # lowercase
            "replace": []
        })
        
        result = apply_edits(template, edits)
        
        # No debe eliminar porque case no coincide
        assert "Línea Exacta" in result
    
    def test_apply_edits_whitespace_sensitivity(self):
        """Test que trim de espacios funciona correctamente"""
        template = "  Línea con espacios  "
        edits = json.dumps({
            "remove": ["Línea con espacios"],
            "replace": []
        })
        
        result = apply_edits(template, edits)
        
        # Debe eliminar línea (strip se aplica)
        assert "Línea con espacios" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

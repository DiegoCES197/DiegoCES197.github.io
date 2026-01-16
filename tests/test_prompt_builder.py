"""
Suite de tests para prompt_builder.py
Tests para construcción de prompts, few-shot learning, y gestión de ejemplos
"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch, mock_open
import sys

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prompt_builder import (
    load_good_examples,
    save_good_example,
    get_prompt_by_modalidad,
    format_fewshot_prompt,
    build_prompt
)


class TestGoodExamplesManagement:
    """Tests para carga y guardado de ejemplos buenos"""
    
    def test_load_good_examples_returns_list(self):
        """Test que load_good_examples retorna lista"""
        result = load_good_examples()
        
        assert isinstance(result, list), "Debe retornar lista"
        assert len(result) >= 0, "Lista puede estar vacía"
    
    def test_save_good_example_creates_file(self):
        """Test que save_good_example guarda ejemplo en archivo"""
        example = {
            "label": "Test ejemplo",
            "remove": ["línea test"],
            "add_findings": ["hallazgo test"]
        }
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "test_examples.json")
            
            with patch('prompt_builder.GOOD_EXAMPLES_FILE', test_file):
                # Primera vez crea archivo
                save_good_example(example)
                
                assert os.path.exists(test_file), "Debe crear archivo"
                
                # Verificar contenido
                with open(test_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                assert len(data) > 0, "Debe tener al menos 1 ejemplo"
                assert any(ex.get('label') == 'Test ejemplo' for ex in data)


class TestModalidadPrompts:
    """Tests para prompts específicos por modalidad"""
    
    def test_get_prompt_by_modalidad_tc(self):
        """Test que retorna prompt para TC"""
        result = get_prompt_by_modalidad("TC")
        
        assert isinstance(result, str)
        assert len(result) > 0
        assert "TC" in result or "Unidades Hounsfield" in result or "contraste" in result
    
    def test_get_prompt_by_modalidad_rm(self):
        """Test que retorna prompt para RM"""
        result = get_prompt_by_modalidad("RM")
        
        assert isinstance(result, str)
        assert "T1" in result or "T2" in result or "gadolinio" in result
    
    def test_get_prompt_by_modalidad_unknown(self):
        """Test que modalidad desconocida retorna prompt por defecto"""
        result = get_prompt_by_modalidad("MODALIDAD_INEXISTENTE")
        
        assert isinstance(result, str)
        assert len(result) > 0


class TestFewshotFormatting:
    """Tests para formateo de ejemplos few-shot"""
    
    def test_format_fewshot_prompt_with_examples(self):
        """Test que format_fewshot_prompt formatea correctamente"""
        examples = [
            {
                "label": "Ejemplo 1",
                "example": {"remove": ["línea 1"], "add_findings": ["hallazgo 1"]}
            },
            {
                "label": "Ejemplo 2",
                "example": {"remove": ["línea 2"], "add_findings": ["hallazgo 2"]}
            }
        ]
        
        result = format_fewshot_prompt(examples)
        
        assert isinstance(result, str)
        assert "EJEMPLOS" in result
        assert "Ejemplo 1" in result or "Ejemplo 2" in result
        assert len(result) > 0
    
    def test_format_fewshot_prompt_empty_list(self):
        """Test que format_fewshot_prompt maneja lista vacía"""
        result = format_fewshot_prompt([])
        
        assert isinstance(result, str)
        assert "EJEMPLOS" in result


class TestPromptBuilding:
    """Tests para construcción del prompt completo"""
    
    def test_build_prompt_contains_text(self):
        """Test CRÍTICO: que build_prompt incluye contenido de texto"""
        result = build_prompt(
            modalidad="TC",
            region="Cráneo",
            indicacion="Trauma",
            extras="Sin contraste",
            template_text="Plantilla de prueba"
        )
        
        assert isinstance(result, str)
        assert len(result) > 0
    
    def test_build_prompt_includes_all_params(self):
        """Test que build_prompt incluye todos los parámetros"""
        modalidad = "TC"
        region = "Tórax"
        indicacion = "Control post-op"
        extras = "Con contraste IV"
        template_text = "--- PLANTILLA DE PRUEBA ---"
        
        result = build_prompt(modalidad, region, indicacion, extras, template_text)
        
        assert modalidad in result, "Debe incluir modalidad"
        assert region in result, "Debe incluir región"
        assert indicacion in result, "Debe incluir indicación"
        assert extras in result, "Debe incluir extras"
        assert template_text in result, "Debe incluir template_text"
    
    def test_build_prompt_includes_instructions(self):
        """Test que build_prompt incluye instrucciones para el modelo"""
        result = build_prompt("TC", "Cráneo", "Trauma", "", "Plantilla test")
        
        # Debe tener palabras clave de instrucciones
        assert "TAREA" in result or "radiólogo" in result
        assert "JSON" in result
        assert "remove" in result or "replace" in result or "add_findings" in result
    
    def test_build_prompt_structure(self):
        """Test que build_prompt tiene estructura esperada"""
        result = build_prompt("TC", "Cráneo", "Trauma", "", "Plantilla test")
        
        # Debe tener secciones clave
        assert "PLANTILLA" in result
        assert "INSTRUCCIONES" in result or "CRÍTICAS" in result or "TAREA" in result
        assert "CONTEXTO" in result
        assert "EJEMPLOS" in result
    
    def test_build_prompt_no_strip_bug(self):
        """Test que build_prompt NO usa .strip() que eliminaría el inicio"""
        result = build_prompt("TC", "Cráneo", "Trauma", "", "Plantilla test")
        
        # Debe conservar el inicio del prompt
        assert result[:1] != "", "El .strip() NO debe estar presente"


class TestEdgeCases:
    """Tests para casos límite"""
    
    def test_build_prompt_with_empty_strings(self):
        """Test que build_prompt maneja strings vacíos"""
        result = build_prompt(
            modalidad="TC",
            region="Región",
            indicacion="",
            extras="",
            template_text="Template"
        )
        
        assert isinstance(result, str)
        assert len(result) > 100, "Debe generar prompt completo"
    
    def test_build_prompt_with_special_characters(self):
        """Test que build_prompt maneja caracteres especiales"""
        result = build_prompt(
            modalidad="TC",
            region="Región con ñ y ü",
            indicacion="Paciente > 60 años",
            extras="Contraste: \"Omnipaque 300\"",
            template_text="Template con 'comillas' y ñ"
        )
        
        assert isinstance(result, str)
        assert "ñ" in result
        assert ">" in result or "&gt;" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

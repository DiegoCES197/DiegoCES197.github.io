"""
Suite de tests para template_manager.py
Tests para CRUD de plantillas, importación TXT/DOCX/JSON
"""
import pytest
import json
import os
import tempfile
from unittest.mock import patch, MagicMock
import sys

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from template_manager import (
    list_templates,
    read_template,
    write_template,
    text_from_docx,
    import_template
)


class TestListTemplates:
    """Tests para listado de plantillas"""
    
    def test_list_templates_returns_list(self):
        """Test que list_templates retorna lista"""
        result = list_templates()
        
        assert isinstance(result, list)
    
    def test_list_templates_only_json(self):
        """Test que list_templates solo retorna archivos .json"""
        result = list_templates()
        
        for filename in result:
            assert filename.endswith('.json'), f"Archivo {filename} no es .json"
    
    def test_list_templates_sorted(self):
        """Test que list_templates retorna lista ordenada"""
        result = list_templates()
        
        if len(result) > 1:
            assert result == sorted(result), "Lista debe estar ordenada alfabéticamente"


class TestReadTemplate:
    """Tests para lectura de plantillas"""
    
    def test_read_template_returns_dict(self):
        """Test que read_template retorna dict"""
        templates = list_templates()
        
        if len(templates) > 0:
            result = read_template(templates[0])
            
            assert isinstance(result, dict), "Debe retornar dict"
    
    def test_read_template_has_expected_keys(self):
        """Test que plantilla tiene keys esperadas"""
        templates = list_templates()
        
        if len(templates) > 0:
            result = read_template(templates[0])
            
            # Puede tener 'name', 'template_text', etc.
            assert len(result) > 0, "Dict no debe estar vacío"


class TestWriteTemplate:
    """Tests para escritura de plantillas"""
    
    def test_write_template_creates_file(self):
        """Test que write_template crea archivo"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('template_manager.TEMPLATES_DIR', tmpdir):
                data = {"name": "Test", "template_text": "Contenido de prueba"}
                filename = "test_template.json"
                
                result = write_template(filename, data)
                
                assert result == filename
                assert os.path.exists(os.path.join(tmpdir, filename))
    
    def test_write_template_adds_json_extension(self):
        """Test que write_template añade .json si no existe"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('template_manager.TEMPLATES_DIR', tmpdir):
                data = {"name": "Test", "template_text": "Test"}
                filename = "test_template"  # Sin .json
                
                result = write_template(filename, data)
                
                assert result.endswith('.json')
                assert os.path.exists(os.path.join(tmpdir, result))
    
    def test_write_template_valid_json(self):
        """Test que write_template escribe JSON válido"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('template_manager.TEMPLATES_DIR', tmpdir):
                data = {"name": "Test", "template_text": "Contenido", "extra": 123}
                filename = "test.json"
                
                write_template(filename, data)
                
                # Leer y verificar JSON válido
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                
                assert loaded == data


class TestTextFromDocx:
    """Tests para extracción de texto desde DOCX"""
    
    @patch('template_manager.Document')
    def test_text_from_docx_extracts_paragraphs(self, mock_document):
        """Test que text_from_docx extrae párrafos"""
        # Simular documento con párrafos
        mock_doc = MagicMock()
        mock_para1 = MagicMock()
        mock_para1.text = "Párrafo 1"
        mock_para2 = MagicMock()
        mock_para2.text = "Párrafo 2"
        mock_doc.paragraphs = [mock_para1, mock_para2]
        mock_document.return_value = mock_doc
        
        result = text_from_docx("dummy.docx")
        
        assert "Párrafo 1" in result
        assert "Párrafo 2" in result
    
    @patch('template_manager.Document')
    def test_text_from_docx_skips_empty_paragraphs(self, mock_document):
        """Test que text_from_docx omite párrafos vacíos"""
        mock_doc = MagicMock()
        mock_para1 = MagicMock()
        mock_para1.text = "Contenido"
        mock_para2 = MagicMock()
        mock_para2.text = "   "  # Solo espacios
        mock_para3 = MagicMock()
        mock_para3.text = "Más contenido"
        mock_doc.paragraphs = [mock_para1, mock_para2, mock_para3]
        mock_document.return_value = mock_doc
        
        result = text_from_docx("dummy.docx")
        
        assert "Contenido" in result
        assert "Más contenido" in result
        # No debe tener líneas vacías múltiples
        assert "\n\n\n" not in result


class TestImportTemplate:
    """Tests para importación de plantillas desde archivos"""
    
    def test_import_template_txt(self):
        """Test importación desde archivo TXT"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Plantilla de prueba\nCon múltiples líneas")
            f.flush()
            temp_path = f.name
        
        try:
            mock_file = MagicMock()
            mock_file.name = temp_path
            
            name, text = import_template(mock_file)
            
            assert isinstance(name, str)
            assert isinstance(text, str)
            assert "Plantilla de prueba" in text
            assert len(name) > 0
        finally:
            os.unlink(temp_path)
    
    def test_import_template_json(self):
        """Test importación desde archivo JSON"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
            data = {"name": "Template JSON", "template_text": "Contenido JSON"}
            json.dump(data, f)
            f.flush()
            temp_path = f.name
        
        try:
            mock_file = MagicMock()
            mock_file.name = temp_path
            
            name, text = import_template(mock_file)
            
            assert name == "Template JSON"
            assert text == "Contenido JSON"
        finally:
            os.unlink(temp_path)
    
    @patch('template_manager.text_from_docx')
    def test_import_template_docx(self, mock_text_from_docx):
        """Test importación desde archivo DOCX"""
        mock_text_from_docx.return_value = "Texto extraído del DOCX"
        
        mock_file = MagicMock()
        mock_file.name = "plantilla.docx"
        
        name, text = import_template(mock_file)
        
        assert name == "plantilla"
        assert text == "Texto extraído del DOCX"
        mock_text_from_docx.assert_called_once()


class TestEdgeCases:
    """Tests para casos límite"""
    
    def test_write_template_unicode(self):
        """Test que write_template maneja Unicode correctamente"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('template_manager.TEMPLATES_DIR', tmpdir):
                data = {"name": "Prueba ñ ü", "template_text": "Contenido con ñ, ü, é"}
                filename = "test_unicode.json"
                
                write_template(filename, data)
                
                # Leer y verificar
                filepath = os.path.join(tmpdir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                
                assert loaded["name"] == "Prueba ñ ü"
                assert loaded["template_text"] == "Contenido con ñ, ü, é"
    
    def test_import_template_empty_txt(self):
        """Test importación de TXT vacío"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("")  # Archivo vacío
            f.flush()
            temp_path = f.name
        
        try:
            mock_file = MagicMock()
            mock_file.name = temp_path
            
            name, text = import_template(mock_file)
            
            assert isinstance(name, str)
            assert text == ""
        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""
Suite de tests para model_loader.py
Tests para carga del modelo MedGemma en CPU y gestión de memoria
"""
import pytest
import torch
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Agregar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from model_loader import load_model, get_device, prepare_inputs, USE_DML


class TestModelLoader:
    """Tests para carga y configuración del modelo"""
    
    def test_load_model_returns_tuple(self):
        """Test que load_model retorna tupla (model, processor, use_dml)"""
        model, processor, use_dml = load_model()
        
        assert model is not None, "Model no debe ser None"
        assert processor is not None, "Processor no debe ser None"
        assert isinstance(use_dml, bool), "use_dml debe ser bool"
    
    def test_get_device_returns_cpu(self):
        """Test que get_device retorna cpu"""
        device = get_device()
        expected = "cuda" if torch.cuda.is_available() else "cpu"
        assert device == expected
    
    @patch('model_loader.AutoModelForImageTextToText.from_pretrained')
    def test_load_model_cpu_path(self, mock_from_pretrained):
        """Test que load_model carga en CPU"""
        mock_from_pretrained.return_value = MagicMock()

        with patch('model_loader.AutoProcessor.from_pretrained') as mock_processor, \
             patch('model_loader.torch.cuda.is_available', return_value=False):
            mock_processor.return_value = MagicMock()

            model, processor, use_dml = load_model()

            assert use_dml is False
            assert mock_from_pretrained.call_count == 1
    
    def test_prepare_inputs_moves_to_device(self):
        """Test que prepare_inputs mueve tensors al device correcto"""
        model = MagicMock()
        model.hf_device_map = None
        
        # Crear inputs simulados
        inputs = {
            'input_ids': torch.tensor([[1, 2, 3]]),
            'attention_mask': torch.tensor([[1, 1, 1]])
        }
        
        result = prepare_inputs(inputs, model)
        
        # Debe retornar dict con mismas keys
        assert set(result.keys()) == set(inputs.keys())
        
        # Debe tener tensors
        assert all(isinstance(v, torch.Tensor) or v is None for v in result.values())


class TestMemoryManagement:
    """Tests para gestión de memoria"""
    
    def test_prepare_inputs_calls_gc_collect(self):
        """Test que prepare_inputs llama gc.collect() para liberar memoria"""
        with patch('gc.collect') as mock_gc:
            model = MagicMock()
            model.hf_device_map = None
            inputs = {'input_ids': torch.tensor([[1, 2, 3]])}
            
            prepare_inputs(inputs, model)
            
            # Debe haber llamado gc.collect()
            mock_gc.assert_called()


class TestErrorHandling:
    """Tests para manejo de errores"""
    
    @patch('model_loader.AutoProcessor.from_pretrained')
    def test_load_model_raises_on_processor_failure(self, mock_processor):
        """Test que load_model lanza RuntimeError si falla processor"""
        mock_processor.side_effect = Exception("Processor failed")
        
        with pytest.raises(RuntimeError, match="No se pudo cargar el processor"):
            load_model()
    
    @patch('model_loader.AutoModelForImageTextToText.from_pretrained')
    @patch('model_loader.AutoProcessor.from_pretrained')
    def test_load_model_raises_on_total_failure(self, mock_processor, mock_model):
        """Test que load_model lanza RuntimeError si todos los devices fallan"""
        mock_processor.return_value = MagicMock()
        
        # Simular que todos los intentos fallan
        mock_model.side_effect = RuntimeError("Fallo total")
        
        with pytest.raises(RuntimeError, match="No se pudo cargar el modelo en ning"):
            load_model()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

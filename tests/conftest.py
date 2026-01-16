"""
Configuración de pytest para RadiAPP
"""
import sys
import os

# Agregar path del proyecto al PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

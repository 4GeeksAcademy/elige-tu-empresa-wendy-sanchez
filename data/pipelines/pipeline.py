#!/usr/bin/env python3
"""Punto de entrada principal del pipeline mensual de insumos por clínica.

Uso:
    python data/pipelines/pipeline.py --month 2025-01-01
    python data/pipelines/pipeline.py --init-schema
    python data/pipelines/pipeline.py --help
"""

import sys
from pathlib import Path

# Asegurar que el proyecto raíz esté en sys.path
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from data.pipelines.runner import main

if __name__ == "__main__":
    main()

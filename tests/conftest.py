import sys
from pathlib import Path

# El hook de build (hatch_build.py) vive en la raíz del repo, no en el paquete
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

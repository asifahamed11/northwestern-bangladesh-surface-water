"""Replay the five revised figures, including completed Figure 8D pilot cells.

Historical replay: reproduce_figures_v020.py.
"""
from pathlib import Path
import subprocess,sys
if __name__=='__main__':
    subprocess.run([sys.executable,str(Path(__file__).resolve().parent/'revision/plot_revision.py'),*sys.argv[1:]],check=True)

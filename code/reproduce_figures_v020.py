"""Replay Figures 1, 3 and 5 in an isolated copy of the original figure layout.

The source plotting scripts are unchanged. No original figure is overwritten.
This command does not refit scientific models or repeat raw-pixel classification.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import shutil
import subprocess
import sys
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'reproduced/figures_1_3_5')
    args = parser.parse_args()
    out = args.output.resolve()
    assert not out.exists(), 'Choose a new output directory.'
    for name in ['code', 'data', 'figures', 'manuscript', 'provenance', 'docs', '.git']:
        protected = (ROOT / name).resolve()
        assert out != protected and not out.is_relative_to(protected)
    assert out != ROOT
    layout = out / '_source_layout'
    project = layout / 'Frontiers_Earth_Science_Inline_20261016'
    (project / 'Figures').mkdir(parents=True)
    (project / 'setup').mkdir()
    (project / 'manuscripts').mkdir()
    manifest = json.loads((ROOT / 'provenance/figure_manifest_v020.json').read_text(encoding='utf-8'))
    (project / 'setup/inline_figure_manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
    shutil.copytree(ROOT / 'data/tables', project / 'Supplementary_Data')
    for name in ['manuscript.md', 'manuscript_build.md']:
        # The plotting source only reads/updates its real caption strings. The
        # full author manuscript is unnecessary in a reviewer code/data bundle.
        captions = '\n\n'.join(item['caption'] for item in manifest)
        (project / 'manuscripts' / name).write_text(captions, encoding='utf-8')
    (layout / 'NW_Bangladesh_2000_2024').mkdir()
    shutil.copy2(ROOT / 'data/boundaries/study_area.geojson', layout / 'NW_Bangladesh_2000_2024/verified_study_area.geojson')
    (layout / 'dataset-download/boundaries').mkdir(parents=True)
    target = layout / 'dataset-download/boundaries/Bangladesh_ADM2_original.geojson'
    target.write_bytes(gzip.decompress((ROOT / 'data/boundaries/national_adm2.geojson.gz').read_bytes()))
    assert hashlib.sha256(target.read_bytes()).hexdigest() == '54379ccc77f6f59dab3569ecc5f9b3850dbed2d65a5f43a034bdf92179f5621b'
    (layout / 'research_outputs/analysis_20261013_completed_data').mkdir(parents=True)
    shutil.copy2(ROOT / 'data/inputs/annual_transition_primary_pre2022.tif',
                 layout / 'research_outputs/analysis_20261013_completed_data/annual_transition_primary_pre2022.tif')
    for name in ['redesign_figure1.py', 'redraw_promoted.py']:
        shutil.copy2(ROOT / 'code/figure_sources' / name, project / name)
        subprocess.run([sys.executable, str(project / name)], check=True, cwd=project)
    records = []
    for number in [1, 3, 5]:
        item = manifest[number-1]
        fresh = project / 'Figures' / item['png']
        original = ROOT / 'provenance/legacy_figures' / item['png']
        with Image.open(fresh) as a, Image.open(original) as b:
            equal = a.size == b.size and a.convert('RGB').tobytes() == b.convert('RGB').tobytes()
        records.append({'figure': number, 'same_rendered_pixels': equal,
                        'replayed_sha256': hashlib.sha256(fresh.read_bytes()).hexdigest(),
                        'original_sha256': hashlib.sha256(original.read_bytes()).hexdigest()})
        for extension in ['.png', '.tiff', '.pdf', '.svg']:
            source = fresh.with_suffix(extension)
            shutil.copy2(source, out / source.name)
    (out / 'FIGURE_REPLAY_REPORT.json').write_text(json.dumps({'figures': records,
        'scientific_models_refit': False, 'original_figures_overwritten': False}, indent=2), encoding='utf-8')
    assert all(r['same_rendered_pixels'] for r in records), 'Inspect differences before claiming figure reproduction.'
    print('PASS: Figures 1, 3 and 5 reproduce the original rendered pixels.')


if __name__ == '__main__': main()

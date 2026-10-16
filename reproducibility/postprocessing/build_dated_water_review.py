"""Build new simple date-wise page; older review and saved backups remain valid."""
import json
from pathlib import Path
from build_dated_water_dataset import ROOT,OUT,digest,write_json,now


def main():
    dataset=json.loads((OUT/'dated_review_dataset.json').read_text(encoding='utf-8'))
    sources=[ROOT/'postprocessing'/s for s in ('dated_water_review.html','dated_water_core.js','dated_water_app.js')]
    page=sources[0].read_text(encoding='utf-8')
    for token,value in [('__DATASET__',json.dumps(dataset,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')),('__CORE__',sources[1].read_text(encoding='utf-8')),('__APP__',sources[2].read_text(encoding='utf-8'))]:
        if page.count(token)!=1:raise ValueError('Page marker mismatch')
        page=page.replace(token,value)
    target=ROOT/'Water_Easy_Date_Review.html';target.write_text(page,encoding='utf-8')
    write_json(OUT/'review_manifest.json',{'created_at':now(),'dataset_id':dataset['id'],'schema':dataset['schema'],
        'dataset_sha256':digest(OUT/'dated_review_dataset.json'),'ui_sha256':digest(target),
        'source_sha256':{str(p.relative_to(ROOT)).replace('\\','/'):digest(p) for p in sources+[Path(__file__)]},
        'old_global_answers_copied_to_dates':False,'actual_human_labels_created':0,'independent_accuracy_complete':False})
    print('READY: Water_Easy_Date_Review.html; one date per answer, color hints over each panel.')


if __name__=='__main__':main()

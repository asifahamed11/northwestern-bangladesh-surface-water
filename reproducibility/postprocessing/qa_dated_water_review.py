"""Real UI/software behavior checks in disposable contexts, not human reference data."""
from pathlib import Path
from tempfile import TemporaryDirectory
import csv,io,json,shutil,subprocess,sys
from playwright.sync_api import sync_playwright
from build_dated_water_dataset import ROOT,OUT,digest,write_json,now,color_mndwi
import numpy as np


def loaded(page):page.wait_for_function("window.datedReviewReady && document.querySelector('#image').complete && document.querySelector('#image').naturalWidth===800")


def main():
    target=ROOT/'Water_Easy_Date_Review.html';D=json.loads((OUT/'dated_review_dataset.json').read_text(encoding='utf-8'))
    qa=OUT/'qa';qa.mkdir(exist_ok=True);errors=[];checks={}
    colors=color_mndwi(np.array([[.8,-.8,0,np.nan]]),np.array([[True,True,True,False]]))[0]
    assert colors[0,2]>colors[0,0] and colors[1,0]>colors[1,2] and colors[2].min()>240 and (colors[3]==[145,145,145]).all()
    checks['palette_sign_and_invalid_support_match_color_hints']=True
    with TemporaryDirectory(prefix='water_DATED_TEST_ONLY_') as temp,sync_playwright() as p:
        temp=Path(temp);browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        context=browser.new_context(viewport={'width':1280,'height':1100},accept_downloads=True)
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(target.as_uri());loaded(page)
        assert '0/245' in page.locator('#progress').inner_text();assert not page.locator('#dateDetails').get_attribute('open')
        assert page.locator('.answers .selected').count()==0
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(qa/'dated_desktop_initial.png'),full_page=True)
        page.locator('.zone[data-kind=mndwi]').hover();tip=page.locator('#hoverTip')
        assert tip.is_visible() and 'নীল' in tip.inner_text() and 'কমলা/লাল' in tip.inner_text() and 'ধূসর' in tip.inner_text()
        page.screenshot(path=str(qa/'dated_mndwi_hover.png'),full_page=True)
        page.locator('.zone[data-kind=ir]').focus();assert 'উজ্জ্বল লাল' in tip.inner_text() and 'ছায়া' in tip.inner_text()
        page.locator('#help').click();assert page.locator('#helpDialog').is_visible();page.locator('#closeHelp').click()
        checks['one_date_view_hidden_date_wall_and_correct_hover_focus_hints']=True
        page.locator('[data-label="0"]').click();assert page.locator('#error').is_visible()
        page.locator('#name').fill('TEST_REVIEWER_SOFTWARE_ONLY')
        first_date=page.locator('#dayDate').inner_text();page.locator('[data-label="0"]').click();loaded(page)
        assert page.locator('#dayDate').inner_text()!=first_date and page.locator('.answers .selected').count()==0
        second_date=page.locator('#dayDate').inner_text();page.locator('[data-label="1"]').click();loaded(page)
        assert 'দিনভেদে বদলেছে' in page.locator('#monthState').inner_text()
        checks['one_answer_advances_date_without_copying_and_mixed_dates_detected']=True
        with page.expect_download() as d:page.locator('#backup').click()
        backup_path=temp/'TEST_ONLY_DATED_BACKUP.json';d.value.save_as(backup_path)
        backup=json.loads(backup_path.read_text(encoding='utf-8'));answered=[e for e in backup['records'] if e['dates']]
        assert len(backup['records'])==720 and len(answered)==1 and len(answered[0]['dates'])==2
        assert sorted(a['label'] for a in answered[0]['dates'].values())==['0','1']
        sid=answered[0]['sample_id'];row=next(r for r in D['rows'] if r['sample_id']==sid)
        assert len(row['scenes'])>2
        assert set(answered[0]['dates']) < {s['item_id'] for s in row['scenes']}
        page.locator('#options').click()
        with page.expect_download() as d:page.locator('#csv').click()
        csv_path=temp/'TEST_ONLY_DATED_LABELS.csv';d.value.save_as(csv_path)
        records=list(csv.DictReader(io.StringIO(csv_path.read_text(encoding='utf-8-sig'))))
        assert len(records)==3022 and len({(r['sample_id'],r['scene_id']) for r in records})==3022
        assert sum(bool(r['human_answer']) for r in records)==2
        assert sorted(r['human_water'] for r in records if r['human_answer'])==['0','1']
        assert all(r['reference_water']=='' and r['independent_reference_eligible']=='false' for r in records)
        assert all(r['acquisition_date']==next(s['date'] for rr in D['rows'] if rr['sample_id']==r['sample_id'] for s in rr['scenes'] if s['item_id']==r['scene_id']) for r in records if r['human_answer'])
        with page.expect_download() as d:page.locator('#summaryCSV').click()
        summary_path=temp/'TEST_ONLY_SUMMARY.csv';d.value.save_as(summary_path)
        summary=list(csv.DictReader(io.StringIO(summary_path.read_text(encoding='utf-8-sig'))));ss=next(r for r in summary if r['sample_id']==sid)
        assert len(summary)==720 and ss['temporal_change_observed']=='true' and ss['assisted_water']==''
        page.locator('#closeOptions').click()
        checks['date_csv_ids_actual_dates_zero_one_and_no_monthly_collapse']=True
        # Exercise the future verifier in a disposable project only.
        sandbox=temp/'TEST_PROJECT';(sandbox/'postprocessing').mkdir(parents=True)
        for name in ('dated_water_core.js','evaluate_dated_water_backup.cjs'):shutil.copyfile(ROOT/'postprocessing'/name,sandbox/'postprocessing'/name)
        base=sandbox/'assisted_water_screening_20261015/date_review_v2';base.mkdir(parents=True)
        for name in ('dated_review_dataset.json','review_manifest.json'):shutil.copyfile(OUT/name,base/name)
        result=subprocess.run(['node',str(sandbox/'postprocessing/evaluate_dated_water_backup.cjs'),'--backup',str(backup_path)],capture_output=True,text=True,encoding='utf-8')
        assert result.returncode==0,result.stderr;result=json.loads(result.stdout)
        assert result['date_answers']==2 and result['temporal_changes']==1 and result['independent_accuracy_complete'] is False
        checks['future_verifier_retains_two_date_answers_and_change']=True
        page.reload();loaded(page);assert 'দিনভেদে বদলেছে' in page.locator('#monthState').inner_text()
        clean=browser.new_context(viewport={'width':1280,'height':1100});other=clean.new_page();other.goto(target.as_uri());loaded(other)
        other.locator('#file').set_input_files(str(backup_path));other.locator('#importDialog').wait_for(state='visible');other.locator('#confirmImport').click();loaded(other)
        assert 'দিনভেদে বদলেছে' in other.locator('#monthState').inner_text()
        checks['dated_backup_restore_and_reload_preserve_different_dates']=True
        legacy={'schema':'nw-assisted-spectral-triage-v1','dataset_id':D['parent_dataset_id'],'exported_at':'2026-10-15T12:00:00Z',
            'independent_reference_eligible':False,'reviewer':'TEST_REVIEWER_SOFTWARE_ONLY','active_id':sid,
            'records':[{'sample_id':r['sample_id'],'label':'0' if r['sample_id']==sid else '',
                'reviewer':'TEST_REVIEWER_SOFTWARE_ONLY' if r['sample_id']==sid else '',
                'notes':'TEST_OLD_NOTE' if r['sample_id']==sid else '', 'updated_at':'2026-10-15T10:00:00Z' if r['sample_id']==sid else '',
                'seen_scenes':[s['item_id'] for s in r['scenes']] if r['sample_id']==sid else []} for r in D['rows']]}
        legacy_path=temp/'TEST_ONLY_LEGACY.json';legacy_path.write_text(json.dumps(legacy),encoding='utf-8')
        other.locator('#file').set_input_files(str(legacy_path));other.locator('#importDialog').wait_for(state='visible')
        assert 'copy হবে না' in other.locator('#importInfo').inner_text();other.locator('#confirmImport').click();loaded(other)
        assert other.locator('#legacyNotice').is_visible() and other.locator('.answers .selected').count()==0
        with other.expect_download() as d:other.locator('#backup').click()
        migrated_path=temp/'TEST_ONLY_MIGRATED.json';d.value.save_as(migrated_path)
        migrated=json.loads(migrated_path.read_text(encoding='utf-8'));record=next(e for e in migrated['records'] if e['sample_id']==sid)
        assert record['legacy_point_answer']['label']=='0' and record['dates']=={} and record['notes']=='TEST_OLD_NOTE'
        checks['legacy_point_answer_retained_without_any_dated_label']=True
        bad={**backup,'dataset_id':'FOREIGN'};bad_path=temp/'FOREIGN_TEST.json';bad_path.write_text(json.dumps(bad),encoding='utf-8')
        other.locator('#file').set_input_files(str(bad_path));other.locator('#error').wait_for(state='visible');assert not other.locator('#importDialog').is_visible()
        checks['foreign_backup_rejected']=True
        tab=context.new_page();tab.goto(target.as_uri());loaded(tab);page.locator('#error').wait_for(state='visible');assert 'অন্য tab' in page.locator('#error').inner_text()
        checks['cross_tab_guard']=True
        mobile=browser.new_context(viewport={'width':390,'height':1040},is_mobile=True,has_touch=True);m=mobile.new_page();m.goto(target.as_uri());loaded(m)
        assert m.evaluate('document.documentElement.scrollWidth<=innerWidth');m.screenshot(path=str(qa/'dated_mobile_initial.png'),full_page=True)
        m.locator('.zone[data-kind=mndwi]').tap();assert m.locator('#hoverTip').is_visible() and 'কমলা' in m.locator('#hoverTip').inner_text()
        rect=m.locator('#hoverTip').bounding_box();assert rect['x']>=0 and rect['x']+rect['width']<=390
        checks['mobile_no_overflow_touch_hint_and_clean_storage']=True
        assert not errors,errors;browser.close()
    write_json(OUT/'software_ui_checks.json',{'status':'PASS','checked_at':now(),'ui_sha256':digest(target),'checks':checks,
        'scope':'Isolated installed Chrome, temporary contexts and explicitly TEST_REVIEWER software labels; all test backups and outputs discarded.',
        'actual_human_labels_created':0,'test_answers_used_as_research_results':False,'javascript_page_errors':errors,
        'independent_accuracy_complete':False})
    print(json.dumps({'status':'PASS','checks':len(checks),'actual_human_labels_created':0}))


if __name__=='__main__':main()

"""Isolated assisted UI and export checks; no real human labels are invented."""
from pathlib import Path
from tempfile import TemporaryDirectory
import csv,io,json,shutil,subprocess,sys
from playwright.sync_api import sync_playwright
from screen_water_colors import ROOT,OUT,digest,write_json,now


def loaded(page):page.wait_for_function("window.assistedReviewReady && document.querySelector('#image').complete && document.querySelector('#image').naturalWidth===800")


def main():
    target=ROOT/'Water_Only_Confused_Review.html';qa=OUT/'qa';qa.mkdir(exist_ok=True)
    D=json.loads((OUT/'screening_dataset.json').read_text(encoding='utf-8'));errors=[];checks={}
    with TemporaryDirectory(prefix='water_ASSISTED_TEST_ONLY_') as tmp,sync_playwright() as p:
        temporary=Path(tmp);browser=p.chromium.launch(executable_path='C:/Program Files/Google/Chrome/Application/chrome.exe',headless=True)
        ctx=browser.new_context(viewport={'width':1280,'height':1100},accept_downloads=True)
        page=ctx.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(target.as_uri());loaded(page)
        assert page.locator('#reviewCount').inner_text()=='245' and page.locator('#autoCount').inner_text()=='337'
        assert page.locator('#missingCount').inner_text()=='138' and page.locator('#filter').input_value()=='REVIEW'
        assert page.locator('.answers .selected').count()==0 and '0/245' in page.locator('#progress').inner_text()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(qa/'assisted_desktop_initial.png'),full_page=True)
        assert page.evaluate("Object.keys(localStorage).every(k=>k.startsWith('nw-assisted-water-review:'))")
        checks['only_245_unclear_cases_default_and_no_old_storage']=True
        page.locator('.zone[data-kind=ir]').hover();assert 'ছায়া' in page.locator('#tip').inner_text()
        page.locator('#help').click();assert page.locator('#helpDialog').is_visible();page.locator('#closeHelp').click()
        page.locator('[data-label="0"]').click();assert page.locator('#error').is_visible()
        page.locator('#name').fill('TEST_REVIEWER_SOFTWARE_ONLY');page.locator('#autoNext').uncheck()
        # At least one prepared date has not been opened yet.
        page.locator('[data-label="0"]').click();assert 'সব তারিখ' in page.locator('#error').inner_text()
        assert page.locator('.answers .selected').count()==0
        for b in page.locator('#dates button').all():b.click();loaded(page)
        page.locator('[data-label="0"]').click();assert 'assisted' in page.locator('#humanState').inner_text()
        assert '1/245' in page.locator('#progress').inner_text()
        checks['all_prepared_dates_required_and_human_zero_saved']=True
        with page.expect_download() as d:page.locator('#backup').click()
        backup_path=temporary/'TEST_ONLY_BACKUP.json';d.value.save_as(backup_path)
        backup=json.loads(backup_path.read_text(encoding='utf-8'))
        assert len(backup['records'])==720 and backup['independent_reference_eligible'] is False
        assert sum(bool(e['label']) for e in backup['records'])==1
        with page.expect_download() as d:page.locator('#csv').click()
        csv_path=temporary/'TEST_ONLY_LABELS.csv';d.value.save_as(csv_path)
        records=list(csv.DictReader(io.StringIO(csv_path.read_text(encoding='utf-8-sig'))))
        assert len(records)==720 and all(r['reference_water']=='' and r['independent_reference_eligible']=='false' for r in records)
        assert sum(r['human_water']=='0' for r in records)==1 and all(r['reference_quality']!='VERIFIED' for r in records)
        assert sum(r['label_origin']=='UNRESOLVED_QUALITY' and r['assisted_water']=='' for r in records)==138
        checks['all_720_exports_and_unknowns_preserved_no_verified_reference']=True
        # Run the real future verifier within a disposable isolated project tree.
        sandbox=temporary/'TEST_PROJECT';(sandbox/'postprocessing').mkdir(parents=True)
        for name in ('assisted_water_core.js','evaluate_assisted_water_backup.cjs'):shutil.copyfile(ROOT/'postprocessing'/name,sandbox/'postprocessing'/name)
        (sandbox/'assisted_water_screening_20261015').mkdir()
        for name in ('screening_dataset.json','review_manifest.json'):shutil.copyfile(OUT/name,sandbox/'assisted_water_screening_20261015'/name)
        result=subprocess.run(['node',str(sandbox/'postprocessing/evaluate_assisted_water_backup.cjs'),'--backup',str(backup_path)],capture_output=True,text=True,encoding='utf-8')
        assert result.returncode==0,result.stderr
        res=json.loads(result.stdout);assert res['required_review_completed']==1 and res['independent_accuracy_complete'] is False
        sys.path.insert(0,str(ROOT/'postprocessing'));from evaluate_blind_accuracy import evaluate
        try:evaluate(backup_path,out=temporary/'MUST_NOT_BE_CREATED')
        except ValueError as exc:assert 'identity mismatch' in str(exc)
        else:raise AssertionError('Independent evaluator accepted assisted answers')
        assert not (temporary/'MUST_NOT_BE_CREATED').exists()
        checks['future_assisted_verifier_and_independent_evaluator_rejection']=True
        page.reload();loaded(page);assert page.locator('[data-label="0"]').get_attribute('class')=='selected'
        page.locator('#autoNext').uncheck()
        page.locator('#filter').select_option('AUTO');loaded(page)
        assert 'প্রাথমিক অনুমান' in page.locator('#reason').inner_text()
        for b in page.locator('#dates button').all():b.click();loaded(page)
        page.locator('[data-label="UNCERTAIN"]').click()
        assert 'অনিশ্চিত' in page.locator('#humanState').inner_text()
        checks['saved_reload_and_optional_auto_case_uncertain_override']=True
        clean=browser.new_context(viewport={'width':1280,'height':1100});other=clean.new_page();other.goto(target.as_uri());loaded(other)
        other.locator('#file').set_input_files(str(backup_path));other.locator('#importDialog').wait_for(state='visible')
        assert '0/245' in other.locator('#progress').inner_text();other.locator('#confirmImport').click();loaded(other)
        assert '1/245' in other.locator('#progress').inner_text()
        bad={**backup,'schema':'nw-independent-dated-review-v1'};bad_path=temporary/'FOREIGN_TEST.json';bad_path.write_text(json.dumps(bad),encoding='utf-8')
        other.locator('#file').set_input_files(str(bad_path));other.locator('#error').wait_for(state='visible')
        assert not other.locator('#importDialog').is_visible() and '1/245' in other.locator('#progress').inner_text()
        checks['backup_restore_confirmation_and_foreign_file_rejection']=True
        tab=ctx.new_page();tab.goto(target.as_uri());loaded(tab);page.locator('#error').wait_for(state='visible')
        assert 'অন্য tab' in page.locator('#error').inner_text();checks['cross_tab_guard']=True
        mobile=browser.new_context(viewport={'width':390,'height':1040},is_mobile=True,has_touch=True)
        m=mobile.new_page();m.goto(target.as_uri());loaded(m)
        assert m.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert '0/245' in m.locator('#progress').inner_text()
        m.screenshot(path=str(qa/'assisted_mobile_initial.png'),full_page=True)
        checks['mobile_layout_blank_answers_and_panel_help']=True
        assert not errors,errors
        browser.close()
    write_json(OUT/'software_ui_checks.json',{'status':'PASS','checked_at':now(),'ui_sha256':digest(target),
        'scope':'Isolated installed Chrome software QA. TEST_REVIEWER answers and downloads discarded with temporary contexts/directories.',
        'checks':checks,'test_labels_used_as_research_evidence':False,'actual_human_labels_created':0,'javascript_page_errors':errors,
        'independent_accuracy_completed':False})
    print(json.dumps({'status':'PASS','checks':len(checks),'actual_human_labels_created':0}))


if __name__=='__main__':main()

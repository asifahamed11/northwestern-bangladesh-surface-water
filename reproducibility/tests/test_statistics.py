"""Synthetic numeric fixtures test algorithms only; they are not research datasets."""
from pathlib import Path
import numpy as np
import pandas as pd
import pytest
from scipy import stats
import statsmodels.api as sm
from statsmodels.stats.sandwich_covariance import cov_hac
from research_pipeline.common import calendar_hac_covariance,fit_linear,month_number,bool_values,load_config
from research_pipeline.models import climate_features,blocked_cv
from research_pipeline.drought import spi_series

def test_hac_matches_independent_statsmodels_regular_calendar():
    rng=np.random.default_rng(17); x=sm.add_constant(rng.normal(size=(120,2)))
    y=x@np.array([2,.7,-.3])+rng.normal(size=120)
    fitted=sm.OLS(y,x).fit()
    own=calendar_hac_covariance(x,fitted.resid,np.arange(120),12)
    np.testing.assert_allclose(own,cov_hac(fitted,nlags=12,use_correction=True),rtol=1e-10,atol=1e-12)

def test_hac_does_not_compress_calendar_gaps():
    x=np.column_stack([np.ones(8),np.arange(8)]); residual=np.array([1,-1,2,-2,1,2,-1,3.])
    spaced=calendar_hac_covariance(x,residual,np.arange(8)*10,1)
    white=calendar_hac_covariance(x,residual,np.arange(8),0)
    compressed=calendar_hac_covariance(x,residual,np.arange(8),1)
    np.testing.assert_allclose(spaced,white)
    assert not np.allclose(spaced,compressed)

@pytest.mark.parametrize('clock',[[0,1,2,3,3,5,6,7],[7,6,5,4,3,2,1,0]])
def test_hac_rejects_duplicate_or_unsorted_clock(clock):
    with pytest.raises(ValueError): calendar_hac_covariance(np.column_stack([np.ones(8),np.arange(8)]),np.ones(8),clock,2)

def test_scaling_recovers_raw_unit_coefficients():
    rng=np.random.default_rng(9); f=pd.DataFrame({'rain':rng.normal(300,90,80),'temp':rng.normal(25,2,80)})
    y=4+.03*f.rain-.5*f.temp
    model=fit_linear(f,y,np.arange(80),2)
    np.testing.assert_allclose(model['coefficients'],[4,.03,-.5],rtol=1e-10,atol=1e-10)
    np.testing.assert_allclose(model['predict'](f),y,rtol=1e-10)

@pytest.mark.parametrize('failure',['constant','rank','nan','short'])
def test_invalid_regressions_are_rejected(failure):
    f=pd.DataFrame({'x':np.arange(30.)}); y=np.arange(30.)
    if failure=='constant': f.x=1
    if failure=='rank': f['duplicate']=2*f.x
    if failure=='nan': f.loc[0,'x']=np.nan
    if failure=='short': f=f.iloc[:5]; y=y[:5]
    with pytest.raises(ValueError): fit_linear(f,y,np.arange(len(f)),2)

def test_month_clock_crosses_year_correctly():
    assert month_number(2001,1)-month_number(2000,12)==1

def test_rolling_climate_features_preserve_omitted_month():
    periods=['2000-01','2000-02','2000-04','2000-05','2000-06']
    frame=pd.DataFrame({'region':'R','period':periods,'year':2000,'month':[1,2,4,5,6],
                        'chirps_rainfall_mm':[1,2,4,5,6],'era5_precipitation_mm':[2,4,8,10,12]})
    out=climate_features(frame)
    assert out.rain_3m_mm.iloc[:4].isna().all()
    assert out.rain_3m_mm.iloc[4]==15

def test_cross_validation_uses_only_past_training_and_calendar_gap(monkeypatch):
    idx=pd.period_range('2000-01','2010-12',freq='M')
    frame=pd.DataFrame({'period':idx.astype(str),'year':idx.year,'month':idx.month,
                        'feature':np.arange(len(idx)),'water_fraction':.3,'response_logit':-.7})
    seen=[]
    def spy(features,y,clock,maxlags):
        seen.append(clock.copy())
        return {'predict':lambda test:np.full(len(test),-.7)}
    monkeypatch.setattr('research_pipeline.models.fit_linear',spy)
    config={'cv_test_start_years':[2009],'cv_gap_months':3,'cv_test_years':2,
            'minimum_cv_train':36,'minimum_cv_test':6,'monthly_hac_lags':12}
    result=blocked_cv(frame,['feature'],config)[0]
    assert result['status']=='PASS' and result['last_train_period']=='2008-09'
    assert result['first_test_period']=='2009-01'
    assert max(seen[0])==month_number(2008,9)

def test_spi_rejects_short_baseline_without_substitution():
    idx=pd.period_range('2000-01','2024-12',freq='M')
    rain=np.random.default_rng(1).gamma(2,20,len(idx))
    spi,parameters=spi_series(rain,idx,3,2000,2024)
    assert spi.isna().all() and (parameters.status=='INSUFFICIENT_BASELINE').all()

def test_spi_matches_independent_zero_adjusted_gamma_calculation():
    idx=pd.period_range('1981-01','2024-12',freq='M')
    rain=np.random.default_rng(1).gamma(2,20,len(idx)); rain[::36]=0
    spi,parameters=spi_series(rain,idx,1,1981,2020)
    assert (parameters.status=='PASS').all()
    reference=rain[(idx.year<=2020)&(idx.month==1)]; positives=reference[reference>0]
    shape,_,scale=stats.gamma.fit(positives,floc=0); q=np.mean(reference==0)
    point=pd.Period('2024-01','M'); value=rain[idx==point][0]
    expected=stats.norm.ppf(np.clip(q+(1-q)*stats.gamma.cdf(value,shape,scale=scale),1e-8,1-1e-8))
    assert spi.loc[point]==pytest.approx(expected)

def test_spi_accumulation_preserves_calendar_gap():
    idx=pd.period_range('1981-01','2024-12',freq='M'); rain=np.random.default_rng(3).gamma(2,30,len(idx))
    keep=idx!=pd.Period('2023-06','M')
    spi,_=spi_series(rain[keep],idx[keep],3,1981,2020)
    assert spi.loc['2023-06':'2023-08'].isna().all()
    assert np.isfinite(spi.loc['2023-09'])

@pytest.mark.parametrize('failure',['duplicate','negative'])
def test_spi_rejects_invalid_input(failure):
    idx=pd.period_range('1981-01','2024-12',freq='M'); rain=np.ones(len(idx))
    if failure=='duplicate': idx=pd.PeriodIndex([idx[0],idx[0]]+list(idx[2:]),freq='M')
    else: rain[3]=-1
    with pytest.raises(ValueError): spi_series(rain,idx,3,1981,2020)

def test_boolean_parser_never_accepts_arbitrary_truthy_string():
    assert bool_values(pd.Series(['true','0','1','false'])).tolist()==[True,False,True,False]
    with pytest.raises(ValueError): bool_values(pd.Series(['False','unknown']))

def test_default_config_validates():
    c=load_config(Path(__file__).parents[1]/'research_pipeline/config.json')
    assert c['spi_baseline_end']-c['spi_baseline_start']+1==40

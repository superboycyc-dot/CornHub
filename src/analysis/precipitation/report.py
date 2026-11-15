"""Create the Chinese precipitation handoff, real pixel calculation example and plot."""
import argparse,csv,datetime as dt,gzip,hashlib,json,subprocess,sys
from pathlib import Path
import numpy as np
import netCDF4
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

D=Path('data/processed/analysis/precipitation');R=Path('reports/d_analysis/precipitation')
def read(name):return list(csv.DictReader((D/name).open()))
def table(path,rows):
 with path.open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
 global D,R
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,default=Path('/tmp/cornhub_weekly_precip'));p.add_argument('--output',type=Path,default=D);p.add_argument('--report',type=Path,default=R);a=p.parse_args();D,R=a.output,a.report
 weekly=read('weekly_all_scopes_2021_2025.csv');annual=read('annual_summary_2021_2025.csv')
 gaps=[r for r in weekly if float(r['coverage_fraction'])<.9]
 table(D/'coverage_below_90pct.csv',gaps)
 for state in ['AK','HI']:table(D/f'weekly_{state.lower()}_2021_2025.csv',[r for r in weekly if r['scope_id']==state])
 national=[r for r in weekly if r['scope_id']=='US50_DC'];full=[r for r in national if r['status']=='computed']
 peak=sorted(full,key=lambda r:float(r['precip_total_mm']),reverse=True)[:5]
 aa={(r['year'],r['scope_id']):r for r in annual}
 text=['# 美国 2021–2025 年逐周降水数据总结','',
 '已实际下载 NOAA CPC 全球逐日降水文件，按周一至周日归并，并用 Census 2024 年简化州界与 0.5° 格点的相交面积加权。范围沿用此前 2021–2025 年。', '',
 '**这是总降水水深，不能分离纯降雨；不是农田专用数据，也不是 NOAA 已发布的现成全国统计。以下是本仓库依据官方格点自行计算的结果。**','',
 '## 数据规模与范围','',
 '- 1,826 个源日期齐全；这不等于每个州每个格点都有效。',
 '- 262 个周区间：260 个完整七天，首尾各一个三天区间标为 partial_week，不冒充完整周。',
 '- 53 个统计范围：50 州＋华盛顿特区、US50_DC（50 州＋DC）、CONUS48_DC（本土 48 州＋DC）；13,886 行周数据。',
 '- 不含波多黎各及其他美国海外领地；全美主表包含阿拉斯加、夏威夷的边界权重，但缺测区域不补零。',
 f"- 全美每周有效面积覆盖率 {min(float(r['coverage_fraction']) for r in national):.4%}–{max(float(r['coverage_fraction']) for r in national):.4%}。",'',
 '## 必须注意的夏威夷缺测','',
 '**夏威夷有 148 个周区间没有任何格点能凑齐所需日期，结果为空；另有 5 周覆盖率低于 90%。不能声称 50 州每一周的数据均完整。** 这是输入缺值/连续七天要求造成的有效性缺口，不能解释为没有下雨；尚未独立核实这些源缺值的产生原因。', '',
 '夏威夷 2021/2022 的全年连续有效区域仅约 14.28%，2023–2025 没有全年连续有效格点。对应年度结果不能当作完整全州气候；全国平均仍排除了缺测区，因此必须连同面积覆盖率使用。', '',
 '补源核查：已找到 NASA/ORNL Daymet 作为潜在独立来源，但 2025 Hawaii 文件直接访问返回 HTTP 401，需要使用者自己的 Earthdata 授权。另测试的 NOAA PSL GPCP 年文件路径返回 404，未取得数据。没有用不同产品或插值偷偷补入 CPC。后续补源必须单列产品、单位、空间分辨率与时间口径。', '',
 '## 年度汇总（mm）','',
 '年度值在全年每天都有效的格点上计算，因此与逐周变化覆盖范围下的周表相加未必相等。', '',
 '| 年份 | 全美有效区域平均年累计 | 本土48州＋DC | 马里兰州 | 全美全年有效面积覆盖率 |', '| --- | ---: | ---: | ---: | ---: |']
 for y in range(2021,2026):
  n=aa[(str(y),'US50_DC')];c=aa[(str(y),'CONUS48_DC')];m=aa[(str(y),'MD')]
  text.append(f"| {y} | {float(n['precip_total_mm']):.2f} | {float(c['precip_total_mm']):.2f} | {float(m['precip_total_mm']):.2f} | {float(n['coverage_fraction']):.4%} |")
 vals={y:float(aa[(str(y),'US50_DC')]['precip_total_mm']) for y in range(2021,2026)}
 text += ['',f"本口径下，五年中 2024 年最高（{vals[2024]:.2f} mm），2022 年最低（{vals[2022]:.2f} mm）；2025 比 2024 低 {(1-vals[2025]/vals[2024]):.2%}。这些是描述性比较，覆盖区有小幅变化，不能直接归因于气候趋势或单个灾害。",'',
 '## 全美周累计最高的五个完整周','', '| 周一至周日 | 有效区域平均周累计 mm | 有效面积覆盖率 |', '| --- | ---: | ---: |']
 for r in peak:text.append(f"| {r['week_start']}–{r['week_end']} | {float(r['precip_total_mm']):.2f} | {float(r['coverage_fraction']):.4%} |")
 text += ['', '最高周描述的是全国有效区域平均水深，不能代表任意县、农场或田块。局地暴雨可能被全国平均稀释。', '',
 '## 文件入口','',
 '- `weekly_us50_2021_2025.csv`：全美周表，可直接预览；含日期、mm、英寸、覆盖率及状态。',
 '- `weekly_conus48_2021_2025.csv`：本土 48 州＋DC，避免误把 CONUS 叫全美。',
 '- `weekly_all_scopes_2021_2025.csv.gz`：全部 53 个范围的完整 CSV，gzip 解压即可读取。',
 '- `weekly_maryland_2021_2025.csv`、`weekly_ak_2021_2025.csv`、`weekly_hi_2021_2025.csv`：重点范围。',
 '- `annual_summary_2021_2025.csv`、`coverage_below_90pct.csv`：年度汇总与需注意的覆盖缺口。',
 '- `inputs/grid_state_weights.csv`：每州每格点的真实相交面积权重；`inputs/source_manifest.json`：原件 URL、SHA-256 和下载时间。',
 '- 详细步骤、公式、运行命令及限制见 README.md；检查见 validation.json，真实逐日示例见 calculation_example.json。', '',
 '![逐周总降水与覆盖率](weekly_precipitation.svg)','']
 (R/'summary_zh.md').write_text('\n'.join(text))
 # Real Maryland example: verify a seven-day pixel sequence against the original NetCDF.
 with np.load(a.cache/'selected_us_daily.npz') as z:
  data=z['values'];rr=z['rows'];cc=z['cols'];w=z['weights']
 scopes=json.load((D/'inputs/scopes.json').open());md=next(i for i,s in enumerate(scopes) if s['scope_id']=='MD')
 start=dt.date(2025,3,31);days=[start+dt.timedelta(days=i) for i in range(7)];offset=(start-dt.date(2021,1,1)).days
 cube=data[offset:offset+7];valid=np.isfinite(cube).all(axis=0);totals=cube.sum(axis=0,dtype='float64');weights=w[md]*valid
 mean=float(np.nansum(totals*weights)/weights.sum());row=next(r for r in weekly if r['scope_id']=='MD' and r['week_start']==str(start))
 assert abs(mean-float(row['precip_total_mm']))<1e-10
 chosen=int(np.argmax(weights));srcindex=(start-dt.date(2025,1,1)).days
 with netCDF4.Dataset(a.cache/'precip.2025.nc') as ds:
  raw=np.asarray(ds['precip'][srcindex:srcindex+7,rr[chosen],cc[chosen]])
 np.testing.assert_array_equal(raw,cube[:,chosen])
 example={'scope':'MD','week_start':str(start),'week_end':str(days[-1]),'daily_units':'mm',
  'chosen_cell':{'grid_row':int(rr[chosen]),'grid_col':int(cc[chosen]),'intersection_area_km2':float(weights[chosen]),
   'daily_values':[{'date':str(d),'precip_mm':float(v)} for d,v in zip(days,raw)],'seven_day_total_mm':float(raw.sum(dtype='float64'))},
  'state_weighted_numerator_mm_km2':float(np.nansum(totals*weights)),'state_valid_area_km2':float(weights.sum()),
  'state_weekly_mean_mm':mean,'independent_source_pixel_check':'exact match to original NetCDF values'}
 (R/'calculation_example.json').write_text(json.dumps(example,indent=2)+'\n')
 # Scientific plot: only full-week amounts, all coverage rows kept for diagnostics.
 fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True,layout='constrained')
 for code,label in [('US50_DC','US 50 states + DC'),('CONUS48_DC','Contiguous 48 + DC')]:
  q=[r for r in weekly if r['scope_id']==code and r['days_in_requested_range']=='7']
  axes[0].plot([dt.date.fromisoformat(r['week_start']) for r in q],[float(r['precip_total_mm']) if r['precip_total_mm'] else np.nan for r in q],label=label,lw=1)
 for code,label in [('US50_DC','US 50 states + DC'),('AK','Alaska'),('HI','Hawaii')]:
  q=[r for r in weekly if r['scope_id']==code]
  axes[1].plot([dt.date.fromisoformat(r['week_start']) for r in q],[100*float(r['coverage_fraction']) for r in q],label=label,lw=1)
 axes[0].set(title='NOAA CPC: US weekly total precipitation, 2021–2025',ylabel='Area-weighted depth (mm/week)')
 axes[1].set(ylabel='Complete-period valid area (%)',xlabel='Week start',ylim=(-1,102))
 for ax in axes:ax.legend(ncol=3);ax.grid(alpha=.2)
 fig.savefig(R/'weekly_precipitation.svg',metadata={'Date':None});plt.close(fig)
 raw=(D/'weekly_all_scopes_2021_2025.csv').read_bytes();(D/'weekly_all_scopes_2021_2025.csv.gz').write_bytes(gzip.compress(raw,mtime=0))
 validation=json.load((R/'validation.json').open());checked=subprocess.run([sys.executable,'-m','unittest','discover','-s',str(Path(__file__).parent),'-p','test_*.py','-v'],capture_output=True,text=True);(R/'unit_tests.txt').write_text(checked.stdout+checked.stderr);assert checked.returncode==0;validation['unit_test_exit_code']=checked.returncode;validation['independent_original_netcdf_pixel_check']='passed';validation['state_vs_weekly_example_max_difference_mm']=abs(mean-float(row['precip_total_mm']))
 validation['geometry_area_partition_max_relative_difference']=max(abs(s['weighted_area_km2']/s['geometry_area_km2']-1) for s in scopes if s.get('geometry_area_km2'))
 validation['source_code_sha256']={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path('src/analysis/precipitation').glob('*.py')}
 (R/'validation.json').write_text(json.dumps(validation,indent=2)+'\n')
 print(json.dumps({'example':example,'national_annual_mm':vals,'weekly_rows':len(weekly),'compressed_all_scopes_bytes':(D/'weekly_all_scopes_2021_2025.csv.gz').stat().st_size}))
if __name__=='__main__':main()

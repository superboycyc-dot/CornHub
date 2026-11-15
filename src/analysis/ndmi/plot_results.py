"""Plot derived real NDMI and coverage; never interpolate missing months."""
import csv
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

p=Path('data/processed/analysis/ndmi/maryland_corn_ndmi_monthly_2021_2025.csv')
rows=list(csv.DictReader(p.open()))
fig,axes=plt.subplots(2,1,figsize=(10,7),sharex=True,layout='constrained',height_ratios=[2,1])
for year in range(2021,2026):
    yy=sorted((r for r in rows if int(r['year'])==year),key=lambda r:int(r['month']))
    x=[int(r['month']) for r in yy]
    y=[float(r['ndmi_mean']) if r['ndmi_mean'] else np.nan for r in yy]
    c=[100*float(r['valid_area_fraction']) if r['valid_area_fraction'] else np.nan for r in yy]
    line,=axes[0].plot(x,y,marker='o',ms=4,label=str(year))
    axes[1].plot(x,c,marker='o',ms=3,color=line.get_color())
axes[0].set(title='Maryland annual CDL Corn areas: monthly NDMI, 2021–2025',ylabel='NDMI (unitless)')
axes[0].axhline(0,color='gray',lw=.7);axes[0].legend(ncol=5)
axes[1].set(ylabel='Valid corn area (%)',xlabel='Calendar month',ylim=(0,101),xticks=range(1,13))
for ax in axes:ax.grid(alpha=.2)
fig.supxlabel('First-clear-pixel monthly mosaics; changing annual corn masks; missing values are not zero.',fontsize=9)
out=Path('reports/d_analysis/ndmi/ndmi_monthly.svg')
out.parent.mkdir(parents=True,exist_ok=True)
fig.savefig(out,metadata={'Date':None})
print(out)

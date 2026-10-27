from pathlib import Path
import json
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'report'
OUT.mkdir(exist_ok=True)
df=pd.read_csv(ROOT/'data/baseline_results.csv' if (ROOT/'data').exists() else ROOT.parent/'results.csv')
supp=pd.read_csv(ROOT/'data/supplement_results.csv' if (ROOT/'data').exists() else ROOT/'results.csv')
assert len(df)==30 and len(supp)==54
assert (supp.groupby(['bucket','variant','L']).size()==3).all()
assert supp[['recall_percent','mean_latency_us','mean_ios']].notna().all().all()
assert supp.recall_percent.between(0,100).all()
assert not supp.duplicated(['bucket','variant','L','repeat']).any()
metrics=['recall_percent','mean_latency_us','mean_ios','qps','filter_skips','tunnel_time_us','io_time_us','peak_rss_kb']
supp.groupby(['bucket','variant','L'])[metrics].agg(['median','min','max']).to_csv(OUT/'supplement_summary.csv')
df.groupby(['system','bucket','L'])[['recall_percent','mean_latency_us','mean_ios','qps']].agg(['median','min','max']).to_csv(OUT/'baseline_summary.csv')
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
colors={'pipeann':'#246b96','gateann':'#c04b36'}
def point(ax, rows, x, y, color, marker='o', label=None):
    xs=rows[x]; ys=rows[y]
    ax.errorbar(xs.median(),ys.median(),xerr=[[xs.median()-xs.min()],[xs.max()-xs.median()]],yerr=[[ys.median()-ys.min()],[ys.max()-ys.median()]],color=color,marker=marker,capsize=3,label=label)
fig,ax=plt.subplots(figsize=(7.2,3.4))
for system,label in [('pipeann','PipeANN-Filter'),('gateann','GateANN')]:
    data=df[(df.system==system)&(df.bucket=='high')]
    med=data.groupby('L')[['recall_percent','mean_latency_us']].median()
    ax.plot(med.mean_latency_us,med.recall_percent,color=colors[system],label=label)
    for L,rows in data.groupby('L'):
        point(ax,rows,'mean_latency_us','recall_percent',colors[system])
        ax.annotate(f'L={L}',(rows.mean_latency_us.median(),rows.recall_percent.median()),xytext=(3,7),textcoords='offset points',fontsize=8)
ax.set(xlabel='Mean latency (us)',ylabel='Recall@10 (%)',xlim=(400,2700),ylim=(78,102)); ax.legend(loc='lower right'); ax.grid(alpha=.2)
fig.tight_layout(); fig.savefig(OUT/'figure1.png',dpi=220); plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(9,3.0))
for ax,metric,label in zip(axes,['recall_percent','mean_latency_us','mean_ios'],['Recall@10 (%)','Mean latency (us)','Logical I/O / query']):
    for system,L,name in [('pipeann',40,'PipeANN-Filter'),('gateann',320,'GateANN')]:
        groups=[df[(df.system==system)&(df.L==L)&(df.bucket==b)][metric] for b in ['low','medium','high']]
        m=np.array([g.median() for g in groups]); lo=np.array([g.min() for g in groups]); hi=np.array([g.max() for g in groups])
        ax.errorbar(range(3),m,yerr=[m-lo,hi-m],label=name,color=colors[system],marker='o',capsize=3)
    ax.set_xticks(range(3),['Low','Medium','High']); ax.set_ylabel(label); ax.grid(alpha=.2)
axes[0].legend(fontsize=8); fig.tight_layout(); fig.savefig(OUT/'figure2.png',dpi=220); plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(9,3.2))
for ax,b in zip(axes,['low','medium','high']):
    data=supp[(supp.bucket==b)&(supp.variant=='baseline')]
    med=data.groupby('L')[['recall_percent','mean_latency_us']].median()
    ax.plot(med.recall_percent,med.mean_latency_us,color=colors['gateann'],label='Fixed L')
    for L,rows in data.groupby('L'):
        point(ax,rows,'recall_percent','mean_latency_us',colors['gateann'])
        ax.annotate(str(L),(rows.recall_percent.median(),rows.mean_latency_us.median()),xytext=(3,3),textcoords='offset points',fontsize=7)
    point(ax,supp[(supp.bucket==b)&(supp.variant=='adaptive')],'recall_percent','mean_latency_us','#238455',marker='D',label='Adaptive')
    ax.set(title=b.capitalize(),xlabel='Recall@10 (%)',ylabel='Mean latency (us)'); ax.grid(alpha=.2)
axes[0].legend(fontsize=8);fig.tight_layout();fig.savefig(OUT/'figure3.png',dpi=220);plt.close(fig)
summary=supp.groupby(['bucket','variant','L'])[metrics].median()
print(summary.to_string())
loads=[json.loads(p.read_text())['loadavg'][0] for p in (ROOT/'runs/formal_1000000').glob('*/command.json')]
(OUT/'validation.json').write_text(json.dumps({'baseline_rows':len(df),'supplement_rows':len(supp),'all_repeats_complete':True,'load1_min':min(loads) if loads else None,'load1_max':max(loads) if loads else None},indent=2))

"""Build data-driven HTML, Markdown, SVG charts and a two-page PDF. No browser needed."""
from pathlib import Path
import base64
import csv
import html
import json
import math
from reportlab.graphics import renderPDF, renderSVG
from reportlab.graphics.shapes import Drawing, Line, Rect, Circle, String
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth

ROOT=Path(__file__).resolve().parents[1]
INK='#173B37';TEAL='#087F75';MUTED='#60716C';AMBER='#AA6425';RED='#B75A45';LINE='#DCE4DE';BG='#F5F5EF'


def pct(x):return f'{100*x:.2f}%'
def pp(x):return f'{100*x:+.2f} pp' if x else '0 pp'
def usd(x):return f'-${abs(x):.2f}' if x<0 else f'${x:.2f}'
def signed_usd(x):return ('+' if x>0 else '')+usd(x)
def ci(values,fmt):return f'{fmt(values[0])} to {fmt(values[1])}'
def count(x):return f'{x:,}' if x is not None else 'No finite sample'
def text(d,x,y,value,size=11,color=INK,font='Helvetica',anchor='start'):
    d.add(String(x,y,value,fontName=font,fontSize=size,fillColor=HexColor(color),textAnchor=anchor))


def interval_chart(rows,lo,hi,fmt,threshold=None):
    h=90+len(rows)*65;d=Drawing(760,h);left=290;right=704
    scale=lambda v:left+(v-lo)/(hi-lo)*(right-left)
    d.add(Rect(0,0,760,h,fillColor=white,strokeColor=None))
    for value in [lo,0,hi]:
        x=scale(value)
        d.add(Line(x,46,x,h-25,strokeColor=HexColor(LINE if value else '#8A9D95'),strokeWidth=1))
        text(d,x,26,fmt(value),10,MUTED,anchor='middle')
    if threshold is not None:
        value,label=threshold;x=scale(value)
        d.add(Line(x,46,x,h-25,strokeColor=HexColor(AMBER),strokeWidth=1.2,strokeDashArray=[4,3]))
        text(d,x,h-12,label,10,AMBER,anchor='middle')
    for i,(label,point,bounds) in enumerate(rows):
        y=h-49-i*65
        text(d,18,y+6,label,12,INK,'Helvetica-Bold')
        text(d,18,y-14,f'{fmt(point)} [{fmt(bounds[0])}, {fmt(bounds[1])}]',10,MUTED)
        x0,x1=map(scale,bounds)
        d.add(Line(x0,y,x1,y,strokeColor=HexColor(TEAL),strokeWidth=3))
        for x in [x0,x1]:d.add(Line(x,y-5,x,y+5,strokeColor=HexColor(TEAL),strokeWidth=1.5))
        d.add(Circle(scale(point),y,4.5,fillColor=HexColor(TEAL),strokeColor=white,strokeWidth=1))
    return d


def make_charts(m):
    c=m['conversion'];r=m['refunds'];rv=m['revenue'];g=m['groups'];cfg=m['config']
    # Bounds expand with data so new input cannot silently clip a confidence interval.
    convlo=min(-.005,c['ci95'][0]*1.25);convhi=max(.017,c['ci95'][1]*1.2)
    loss=cfg['decision']['net_revenue_loss_margin_usd'];rm=cfg['decision']['refund_rate_increase_margin']
    drawings={
        'conversion':interval_chart([('Purchase conversion',c['difference'],c['ci95'])],convlo,convhi,pp,(0,'No effect')),
        'revenue':interval_chart([(label,rv[k]['difference'],rv[k]['ci95']) for label,k in [('Gross revenue / user','gross'),('After-refund revenue / user','net')]],min(-loss*1.4,min(v['ci95'][0] for v in rv.values())*1.15),max(.5,max(v['ci95'][1] for v in rv.values())*1.15),usd,(-loss,f'Safety limit {usd(-loss)}')),
        'refunds':interval_chart([('Refunded-user rate',r['difference'],r['ci95'])],min(-.002,r['ci95'][0]*1.2),max(rm*1.5,r['ci95'][1]*1.2),pp,(rm,f'Safety limit {pp(rm)}')),
    }
    d=Drawing(760,180);d.add(Rect(0,0,760,180,fillColor=white,strokeColor=None))
    n=sum(x['n'] for x in g.values());x0=170;span=460;top=max(x['n'] for x in g.values())*1.15
    for i,v in enumerate(['control','new']):
        y=116-i*54;width=g[v]['n']/top*span
        text(d,18,y+10,'Control' if v=='control' else 'New checkout',12)
        d.add(Rect(x0,y,width,28,fillColor=HexColor('#A7BBB2' if v=='control' else TEAL),strokeColor=None))
        text(d,x0+width+12,y+10,f"{g[v]['n']:,} ({g[v]['n']/n:.2%})",11)
    text(d,18,17,f"Intended treatment share {m['config']['measurement']['expected_treatment_share']:.0%} | SRM p = {m['allocation']['p_value']:.3f} | Flag at p < {m['allocation']['alert_threshold']}",10,MUTED)
    drawings['allocation']=d
    b=m['revenue_bridge']
    if b:
        components=[('More buyers',b['gross_contributions']['conversion']),
                    ('Orders per buyer',b['gross_contributions']['orders_per_buyer']),
                    ('Average order value',b['gross_contributions']['average_order_value']),
                    ('Additional refunds',b['additional_refund_drag']),
                    ('Total net difference',b['net_difference'])]
        d=Drawing(760,275);d.add(Rect(0,0,760,275,fillColor=white,strokeColor=None))
        extent=max(abs(v) for _,v in components)*1.3;scale=lambda v:490+v/extent*175
        d.add(Line(490,35,490,260,strokeColor=HexColor(LINE)))
        for i,(label,value) in enumerate(components):
            y=230-i*43;x=scale(value)
            text(d,18,y+6,label,12,INK,'Helvetica-Bold' if i==4 else 'Helvetica')
            text(d,225,y+6,signed_usd(value),12,INK,'Helvetica-Bold')
            d.add(Rect(min(x,490),y,abs(x-490),23,fillColor=HexColor(INK if i==4 else TEAL if value>0 else RED),strokeColor=None))
        text(d,490,14,'USD per assigned user | exact descriptive decomposition',10,MUTED,anchor='middle')
        drawings['revenue_drivers']=d
    d=Drawing(760,220);d.add(Rect(0,0,760,220,fillColor=white,strokeColor=None))
    plan=m['planning'];nnet=plan['net_safety_scenarios'][0]['n_per_arm']
    items=[(f"Conversion {pp(plan['target_absolute_effect'])}",plan['approx_n_per_arm']),
           ('Refund safety: no increase',plan['refund_safety_scenarios'][0]['n_per_arm']),
           ('Revenue safety: no loss',nnet)]
    maxn=max(v for _,v in items);left=270;span=360
    for i,(label,value) in enumerate(items):
        y=158-i*52;width=value/maxn*span
        text(d,18,y+10,label,12)
        d.add(Rect(left,y,width,28,fillColor=HexColor(AMBER if i==2 else TEAL),strokeColor=None))
        text(d,left+width+10,y+10,f'{value:,}',11,INK,'Helvetica-Bold')
    text(d,18,18,'Approximate users per arm | 80% power for each criterion separately',10,MUTED)
    drawings['sample_size']=d
    return drawings


def report_rows(m):
    g=m['groups'];c=m['conversion'];r=m['refunds'];rv=m['revenue']
    return [
        ('Assigned users',count(g['control']['n']),count(g['new']['n']),f"SRM p = {m['allocation']['p_value']:.3f}"),
        ('Purchase conversion',pct(c['control']),pct(c['new']),f"{pp(c['difference'])} [{ci(c['ci95'],pp)}]"),
        ('Gross revenue / user',usd(g['control']['gross_rpu']),usd(g['new']['gross_rpu']),f"{signed_usd(rv['gross']['difference'])} [{ci(rv['gross']['ci95'],usd)}]"),
        ('After-refund revenue / user',usd(g['control']['net_rpu']),usd(g['new']['net_rpu']),f"{signed_usd(rv['net']['difference'])} [{ci(rv['net']['ci95'],usd)}]"),
        ('Refunded-user rate',pct(r['control']),pct(r['new']),f"{pp(r['difference'])} [{ci(r['ci95'],pp)}]")]


def decision_copy(m):
    status=m['decision']['status']
    if status=='LAUNCH CANDIDATE':
        return ('The agreed outcome criteria clear their interval boundaries.',
                'Advance to operational review and a staged rollout if the illustrative margins are business-approved.')
    if status=='REJECT OR REDESIGN':
        return ('At least one outcome provides evidence against the launch rule.',
                'Retain the existing checkout and redesign the proposal before another confirmatory experiment.')
    if status.startswith('PAUSE'):
        return ('Allocation quality needs investigation before causal interpretation.',
                'Pause launch decisions and resolve the allocation discrepancy before interpreting outcomes.')
    return ('Conversion is promising; revenue and refund safety remain unresolved.',
            'Retain the existing checkout. Treat this as an inconclusive pilot and assess whether a fresh, independently planned test is economically feasible.')


def make_pdf(root,m,q,drawings):
    path=root/'experiment-readout.pdf'
    pdf=canvas.Canvas(str(path),pagesize=(612,792),invariant=1)
    pdf.setTitle('Should we launch the new checkout? | Simulated experiment')
    pdf.setAuthor('Product analytics portfolio')
    width=516;left=48
    def label(x,y,s,size=10,color=INK,bold=False):
        pdf.setFillColor(HexColor(color));pdf.setFont('Helvetica-Bold' if bold else 'Helvetica',size);pdf.drawString(x,y,s)
    def paragraph(s,y,size=10.5,leading=15,available=516,color=INK):
        words=s.split();line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if stringWidth(candidate,'Helvetica',size)>available:
                label(left,y,line,size,color);y-=leading;line=word
            else:line=candidate
        if line:label(left,y,line,size,color);y-=leading
        return y
    def footer(page):
        pdf.setStrokeColor(HexColor(LINE));pdf.line(48,40,564,40)
        label(48,25,'SIMULATED DATA  |  Reproducible SQL + Python  |  Experiment 03',8,MUTED)
        label(540,25,f'{page} / 2',8,MUTED)
    c=m['conversion'];g=m['groups'];rv=m['revenue'];r=m['refunds'];plan=m['planning']
    cfg=m['config'];loss=cfg['decision']['net_revenue_loss_margin_usd'];rm=cfg['decision']['refund_rate_increase_margin']
    status=m['decision']['status'].replace(' — ',' - ')
    label(left,751,'PRODUCT EXPERIMENT / DECISION MEMO',9,TEAL,True)
    label(left,716,'Should we launch the new checkout?',25,INK,True)
    label(left,691,f"{sum(g[v]['n'] for v in g):,} fictional users. One accountable launch decision.",12,MUTED)
    pdf.setFillColor(HexColor('#F6EBD9'));pdf.roundRect(48,607,516,62,8,fill=1,stroke=0)
    label(63,646,status,11,AMBER,True)
    label(63,625,decision_copy(m)[0],10,INK)
    y=paragraph('Decision: '+decision_copy(m)[1],586,11,16)
    label(left,525,'01 / Does the new checkout improve conversion?',12,INK,True)
    drawing=drawings['conversion'];scale=516/drawing.width
    pdf.saveState();pdf.translate(left,405);pdf.scale(scale,scale);renderPDF.draw(drawing,pdf,0,0);pdf.restoreState()
    paragraph(f"Control: {pct(c['control'])}. New: {pct(c['new'])}. Relative lift: {c['relative_change']*100:+.2f}% (95% CI {c['relative_ci95'][0]*100:+.2f}% to {c['relative_ci95'][1]*100:+.2f}%). The absolute interval includes no improvement.",393,10,14)
    label(left,339,'02 / Do revenue and refunds clear the safety criteria?',12,INK,True)
    # Compact, legible three-column table; all values come from metrics.
    pdf.setFillColor(HexColor(BG));pdf.rect(48,302,516,24,fill=1,stroke=0)
    label(57,310,'Metric',9,INK,True);label(255,310,'Difference [95% CI]',9,INK,True);label(488,310,'Safety',9,INK,True)
    table=[('Gross revenue / user',rv['gross']['difference'],rv['gross']['ci95'],usd,'Secondary'),
           ('After-refund revenue / user',rv['net']['difference'],rv['net']['ci95'],usd,'Cleared' if m['decision']['gates']['net_revenue_safety'] else 'Unresolved'),
           ('Refunded-user rate',r['difference'],r['ci95'],pp,'Cleared' if m['decision']['gates']['refund_safety'] else 'Unresolved')]
    y=282
    for title,point,bounds,fmt,gate in table:
        label(57,y,title,9);label(255,y,f'{fmt(point)} [{ci(bounds,fmt)}]',9);label(488,y,gate,8,AMBER)
        pdf.setStrokeColor(HexColor(LINE));pdf.line(48,y-11,564,y-11);y-=35
    paragraph(f"Illustrative launch rule: conversion lower 95% bound > 0; after-refund revenue/user lower bound > {usd(-loss)}; refund-rate upper bound < {pp(rm)}. All must pass. Current outcome criteria cleared: {sum(m['decision']['gates'].values())} of 3. Margins require stakeholder agreement before confirmation.",164,9.5,13)
    paragraph(f"Assignment checks: {g['control']['n']:,} control / {g['new']['n']:,} new; SRM p={m['allocation']['p_value']:.3f}. {q['duplicate_extra_rows']} exact ingestion retries removed, no assignment conflicts, and all {q['nonbuyers_retained']:,} nonbuyers retained.",94,9.5,13)
    footer(1);pdf.showPage()
    label(left,751,'PRODUCT EXPERIMENT / EXPLANATION & NEXT ACTION',9,TEAL,True)
    label(left,716,'More buyers, nearly flat revenue estimate',22,INK,True)
    paragraph(f"Gross revenue per assigned user is {signed_usd(rv['gross']['difference'])} at the point estimate, with a 95% interval from {usd(rv['gross']['ci95'][0])} to {usd(rv['gross']['ci95'][1])}. The bridge is descriptive and does not establish separate causal mechanisms.",690,10.5,15)
    drawing=drawings['revenue_drivers'];scale=516/drawing.width
    pdf.saveState();pdf.translate(left,465);pdf.scale(scale,scale);renderPDF.draw(drawing,pdf,0,0);pdf.restoreState()
    label(left,442,'03 / The next test is constrained by revenue precision',12,INK,True)
    nnet=plan['net_safety_scenarios'][0]['n_per_arm'];pnet=plan['net_safety_scenarios'][0]['power_at_reference_n']
    paragraph(f"Conversion alone needs approximately {plan['approx_n_per_arm']:,} users per arm to detect +{plan['target_absolute_effect']*100:.2f} percentage points with {plan['marginal_power']:.0%} power. The {usd(loss)} revenue-loss safety margin needs about {nnet:,} per arm even assuming zero true loss. At {plan['reference_users_per_arm']:,} per arm, that safety check has only {pnet:.0%} approximate power.",420,10.5,15)
    paragraph('Agree on acceptable economic loss, available traffic, test cost and sample cap before starting. If the required precision is unaffordable, retain the current checkout and redesign the proposal. Do not relax a safety margin merely to make the test pass.',341,10.5,15)
    label(left,271,'Measurement and interpretation',12,INK,True)
    bullets=[
        'Intention-to-treat: all assigned users. Paid orders in [assignment, +7 days); refunds on eligible orders in [order, +30 days). All follow-up is mature.',
        '95% proportion intervals: Newcombe/Wilson. Revenue: 10,000 within-arm user bootstrap resamples, including nonbuyers and repeat orders.',
        'Planning figures are approximate marginal powers, not a joint launch guarantee. Further testing uses a fresh fixed-horizon run; avoid optional stopping.',
        'No segment wins are claimed. Multiple subgroup searches can create false discoveries; use planned interactions and multiplicity control.',
        'Synthetic data do not validate a real retailer. After-refund revenue excludes costs, fees and long-term effects; it is not profit.'
    ]
    y=250
    for i,s in enumerate(bullets):
        y=paragraph(f'{i+1}. {s}',y,9.2,12.5)-5
    footer(2);pdf.save()
    return path


def build(root=ROOT):
    root=Path(root);m=json.loads((root/'results/metrics.json').read_text());q=json.loads((root/'results/quality_checks.json').read_text())
    cfg=m['config'];c=m['conversion'];r=m['refunds'];rv=m['revenue'];g=m['groups'];p=m['planning'];b=m['revenue_bridge']
    drawings=make_charts(m);svgs={}
    for name,drawing in drawings.items():
        svg=renderSVG.drawToString(drawing)
        (root/'charts'/f'{name}.svg').write_text(svg);svgs[name]=svg
    def figure(name,alt):
        encoded=base64.b64encode(svgs[name].encode()).decode()
        return f'<figure><div class="chart-scroll"><img src="data:image/svg+xml;base64,{encoded}" alt="{html.escape(alt,quote=True)}"></div><figcaption>{html.escape(alt)}</figcaption></figure>'
    rows=report_rows(m)
    table=''.join('<tr>'+f'<th scope="row">{html.escape(row[0])}</th>'+''.join(f'<td>{html.escape(v)}</td>' for v in row[1:])+'</tr>' for row in rows)
    net=p['net_safety_scenarios'][0];refundpilot=p['refund_safety_scenarios'][-1]
    loss=cfg['decision']['net_revenue_loss_margin_usd'];rm=cfg['decision']['refund_rate_increase_margin']
    gate_labels=[('Conversion superiority','Lower 95% bound > 0',pp(c['ci95'][0]),'conversion_superiority'),
                 ('Revenue safety',f'Lower 95% bound > {usd(-loss)}',usd(rv['net']['ci95'][0]),'net_revenue_safety'),
                 ('Refund safety',f'Upper 95% bound < {pp(rm)}',pp(r['ci95'][1]),'refund_safety')]
    gates=''.join(f'<tr><th scope="row">{label}</th><td>{html.escape(rule)}</td><td>{actual}</td><td><span class="status">{"Cleared" if m["decision"]["gates"][key] else "Unresolved"}</span></td></tr>' for label,rule,actual,key in gate_labels)
    scenarios=''.join(f'<tr><th scope="row">{usd(row["loss_margin_usd"])}</th><td>{count(row["n_per_arm"])}</td><td>{row["power_at_reference_n"]:.0%}</td></tr>' for row in p['net_safety_scenarios'] if row['assumed_true_difference_usd']==0)
    allocation_text=f"Control {g['control']['n']:,}; new {g['new']['n']:,}. SRM p={m['allocation']['p_value']:.3f}."
    decision=m['decision']['status']
    title={'LAUNCH CANDIDATE':'A launch candidate, subject to operational review',
           'REJECT OR REDESIGN':'Retain the existing checkout and redesign',
           'PAUSE — INVESTIGATE ALLOCATION':'Pause interpretation and investigate allocation'}.get(decision,'Keep testing only if the next test is worth running')
    page=f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Should we launch the new checkout? | Product analytics case study</title><style>
:root{{--ink:{INK};--muted:{MUTED};--teal:{TEAL};--line:{LINE};--paper:{BG};--amber:{AMBER}}}*{{box-sizing:border-box}}html{{scroll-behavior:smooth}}body{{margin:0;background:var(--paper);color:var(--ink);font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}a{{color:var(--teal);text-underline-offset:4px}}a:focus-visible,summary:focus-visible{{outline:3px solid var(--amber);outline-offset:5px}}.wrap{{max-width:1100px;margin:auto;padding:0 30px}}header{{border-bottom:1px solid var(--line);padding:22px 0}}.top{{display:flex;justify-content:space-between;gap:16px;flex-wrap:wrap;font-size:12px;letter-spacing:1px}}.brand{{font-weight:750}}nav{{display:flex;gap:20px}}.hero{{padding:65px 0 36px}}.eyebrow{{font-size:12px;letter-spacing:2px;font-weight:750;color:var(--teal)}}h1{{font-size:clamp(38px,6vw,70px);line-height:1.04;letter-spacing:-2.5px;max-width:850px;margin:20px 0}}.intro{{font-size:21px;line-height:1.5;color:var(--muted);max-width:780px}}.badge{{display:inline-block;border:1px solid #c7d8cf;background:#e8efe6;border-radius:30px;padding:4px 12px;font-size:12px;letter-spacing:.3px}}.decision{{background:var(--ink);color:white;padding:30px;border-radius:12px;margin:27px 0}}.decision h2{{font-size:27px;margin:6px 0 12px}}.decision .eyebrow{{color:#c9e6d8}}.decision p{{color:#e4ede8;margin:0}}.actions{{display:flex;gap:12px;flex-wrap:wrap;margin:24px 0}}.button{{display:inline-block;padding:10px 17px;border:1px solid var(--teal);border-radius:5px;text-decoration:none;font-size:14px;font-weight:650}}.button.primary{{background:var(--teal);color:white}}.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:25px 0 0}}.metric{{background:white;border:1px solid var(--line);border-radius:9px;padding:22px}}.metric .value{{font-size:34px;font-weight:750;letter-spacing:-1px;display:block;margin:5px 0}}.small{{font-size:13px;color:var(--muted)}}.metric .small{{line-height:1.5}}.section{{padding:38px 0;border-top:1px solid var(--line)}}.section-head{{display:grid;grid-template-columns:60px 1fr;gap:15px}}.section-number{{font-size:15px;color:var(--teal);font-weight:750;padding-top:5px}}h2{{font-size:28px;line-height:1.25;margin:0 0 16px;letter-spacing:-.6px}}h3{{font-size:18px;margin:0 0 12px}}p{{margin:0 0 16px}}.reading{{max-width:830px}}.panel{{background:#fff;border:1px solid var(--line);border-radius:9px;padding:24px;margin:20px 0}}figure{{margin:16px 0 24px}}.chart-scroll{{overflow:auto;background:white;border:1px solid var(--line);border-radius:8px}}figure img{{display:block;width:100%;min-width:620px}}figcaption{{font-size:12px;line-height:1.5;color:var(--muted);padding:9px 3px}}table{{width:100%;border-collapse:collapse;font-size:14px;line-height:1.45}}th,td{{text-align:right;padding:14px 12px;border-bottom:1px solid var(--line);vertical-align:top;font-variant-numeric:tabular-nums}}th:first-child{{text-align:left}}thead th{{font-size:12px;background:#eaf0e9}}.table-scroll{{overflow:auto;margin:20px 0}}.status{{color:var(--amber);font-size:12px;font-weight:700}}.insight{{border-left:4px solid var(--amber);padding:16px 20px;background:#f5ead7;margin:24px 0}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:20px}}.two .panel{{margin:0}}ul{{padding-left:20px}}li{{margin-bottom:10px}}details{{border-top:1px solid var(--line);padding:16px 0}}summary{{cursor:pointer;font-weight:650}}details>div{{padding:18px 0 0}}code{{font-size:13px;background:#eaf0e9;padding:2px 4px;border-radius:3px}}footer{{padding:30px 0 50px;font-size:13px;color:var(--muted)}}.no-margin{{margin:0}}@media(max-width:740px){{.wrap{{padding:0 18px}}.hero{{padding-top:36px}}.cards,.two{{grid-template-columns:1fr}}h1{{letter-spacing:-1.4px}}.section-head{{grid-template-columns:32px 1fr;gap:8px}}h2{{font-size:24px}}.decision{{padding:23px}}th,td{{min-width:125px}}.metric .value{{font-size:30px}}}}@media print{{header,.actions,details{{display:none}}.hero{{padding-top:12px}}.section{{break-inside:avoid}}body{{background:white}}figure img{{min-width:0}}.wrap{{max-width:none}}}}
</style></head><body><header><div class="wrap top"><span class="brand">EXPERIMENT 03 / PRODUCT ANALYTICS</span><nav aria-label="Report navigation"><a href="#evidence">Evidence</a><a href="#economics">Economics</a><a href="#next">Next decision</a></nav></div></header><main class="wrap"><div class="hero"><span class="badge">Portfolio simulation · SQL + Python · Version 2</span><h1>Should we launch<br>the new checkout?</h1><p class="intro">A checkout test with a promising conversion estimate, uncertain economics, and a decision that respects both.</p><div class="decision"><span class="eyebrow">RECOMMENDATION</span><h2>{title}</h2><p>{html.escape(decision)}. {html.escape(decision_copy(m)[1])}</p></div><div class="actions"><a class="button primary" href="experiment-readout.pdf">Read the 2-page brief</a><a class="button" href="analysis.ipynb">Explore the executed notebook</a><a class="button" href="README.md">Reproduce the project</a></div><div class="cards"><div class="metric"><span class="small">PURCHASE CONVERSION</span><span class="value">{pp(c['difference'])}</span><span class="small">95% CI: {ci(c['ci95'],pp)}<br>Relative change: {c['relative_change']*100:+.2f}%</span></div><div class="metric"><span class="small">AFTER-REFUND REVENUE / USER</span><span class="value">{signed_usd(rv['net']['difference'])}</span><span class="small">95% CI: {ci(rv['net']['ci95'],usd)}</span></div><div class="metric"><span class="small">REFUNDED-USER RATE</span><span class="value">{pp(r['difference'])}</span><span class="small">95% CI: {ci(r['ci95'],pp)}</span></div></div></div>
<section class="section" id="evidence"><div class="section-head"><span class="section-number">01</span><div><h2>The evidence supports caution.</h2><p class="reading">All {q['assigned_users']:,} assigned users count, including {q['nonbuyers_retained']:,} who never purchased. Orders count for {cfg['measurement']['purchase_days']} days after assignment; their refunds are observed for {cfg['measurement']['refund_days']} days. All follow-up is complete at the frozen extract. The {cfg['measurement']['purchase_days']}-day window is primary. The 1- and 3-day comparisons are exploratory point estimates only; they have no confidence intervals or hypothesis tests, and must not be selected based on which looks best.</p><div class="table-scroll"><table><thead><tr><th>Metric</th><th>Control</th><th>New checkout</th><th>Difference [95% CI]</th></tr></thead><tbody>{table}</tbody></table></div>{figure('conversion','New minus control. Bars show 95% confidence intervals; the vertical reference is no effect.')}<p class="reading">The conversion point estimate is equivalent to {c['difference']*1000:.1f} additional buyers per 1,000 assigned users. Its interval spans {c['ci95'][0]*1000:.1f} to {c['ci95'][1]*1000:.1f}. A useful gain remains plausible, but a positive effect has not been established.</p>{figure('revenue','Revenue uncertainty includes both a loss and a gain. The dashed line is the illustrative after-refund safety boundary; it does not apply to gross revenue.')}{figure('refunds','Refunds are numerically higher. The upper interval bound exceeds the illustrative safety limit, so acceptable harm has not been ruled out.')}<p class="small">Individual 95% intervals do not provide joint 95% coverage. Non-significance does not establish equivalence or safety. Amounts are fictional USD; after-refund revenue is not profit.</p></div></div></section>
<section class="section" id="economics"><div class="section-head"><span class="section-number">02</span><div><h2>More buyers, nearly flat revenue estimate.</h2><p class="reading">Gross revenue per assigned user is {signed_usd(rv['gross']['difference'])} at the point estimate. Its 95% interval runs from {usd(rv['gross']['ci95'][0])} to {usd(rv['gross']['ci95'][1])}, so these data do not establish either a gain or a loss. Gross revenue equals conversion × orders per buyer × average order value. In this sample, lower repeat ordering and basket value offset the conversion contribution. Additional refunds reduce the after-refund point estimate further.</p>{figure('revenue_drivers','Arithmetic decomposition of the observed difference, averaged across all six factor replacement orders. These are descriptive contributions, not separately established causal effects.')}<div class="two"><div class="panel"><h3>Average order value</h3><p class="no-margin">{usd(g['control']['average_order_value'])} → {usd(g['new']['average_order_value'])}</p><span class="small">Control → new checkout</span></div><div class="panel"><h3>Orders per buyer</h3><p class="no-margin">{g['control']['orders_per_buyer']:.3f} → {g['new']['orders_per_buyer']:.3f}</p><span class="small">Descriptive; buyer composition can change</span></div></div><details><summary>Why use a user bootstrap for revenue?</summary><div><p>Approximately {g['control']['zero_revenue_share']:.0%} of control users and {g['new']['zero_revenue_share']:.0%} of new-checkout users generate zero revenue. The top 1% of assigned users account for {g['control']['top_one_percent_revenue_share']:.1%} and {g['new']['top_one_percent_revenue_share']:.1%} of gross revenue, respectively.</p><p>We resample assigned users within each arm {m['bootstrap_replicates']:,} times, retaining zeroes and all orders and refunds for each selected user. No outliers are deleted. A separate normal-approximation interval gives a similar conclusion: {ci(rv['net']['normal_ci95_sensitivity'],usd)} for after-refund revenue/user.</p></div></details></div></div></section>
<section class="section"><div class="section-head"><span class="section-number">03</span><div><h2>Validate assignment before interpreting effects.</h2>{figure('allocation',allocation_text)}<p class="reading">No allocation alert at p &lt; {m['allocation']['alert_threshold']}. There are {q['duplicate_extra_rows']} exact ingestion retries and {q['conflicting_users']} conflicting assignments. The pipeline rejects conflicting assignments, broken keys, malformed timestamps, excess refunds and immature follow-up. SQL has its own assignment and maturity gates.</p><div class="panel"><h3>Every assigned user reconciles</h3><p>Independent Python logic reproduces the SQL order, refund and checkout outcomes for all {q['reconciled_users']:,} users. {q['excluded_orders']} orders are excluded by the measurement contract: {q['excluded_order_reasons']['not_paid']} not paid, {q['excluded_order_reasons']['pre_assignment']} before assignment, and {q['excluded_order_reasons']['after_purchase_window']} after the purchase window.</p><p class="small no-margin">An unflagged allocation test does not prove exposure delivery or tracking are correct. The simulation assumes complete identities and logs.</p></div></div></div></section>
<section class="section" id="next"><div class="section-head"><span class="section-number">04</span><div><h2>Make the next experiment an economic decision.</h2><p class="reading">Agree on these illustrative success and safety criteria before a new confirmatory test. The recommendation is calculated from the intervals, rather than stored as a fixed answer.</p><div class="table-scroll"><table><thead><tr><th>Criterion</th><th>Rule</th><th>Observed bound</th><th>Status</th></tr></thead><tbody>{gates}</tbody></table></div>{figure('sample_size','Conversion and safety tests need different sample sizes. These normal-approximation scenarios target 80% power per criterion separately, with a one-sided 2.5% boundary for safety.')}<div class="insight"><strong>The limiting factor is revenue precision.</strong><p class="no-margin">A {usd(loss)} loss limit requires about {net['n_per_arm']:,} users per group under zero true revenue loss. At {p['reference_users_per_arm']:,} per group, power is only {net['power_at_reference_n']:.0%}. A bigger conversion test alone does not solve the launch decision.</p></div><details><summary>How sensitive is this to business assumptions?</summary><div><p>Under zero true revenue change, a larger acceptable-loss margin requires less traffic. These are planning scenarios, not suggested threshold changes.</p><div class="table-scroll"><table><thead><tr><th>Acceptable loss / user</th><th>Users / arm</th><th>Power at {p['reference_users_per_arm']:,} / arm</th></tr></thead><tbody>{scenarios}</tbody></table></div><p>If the observed revenue estimate of {usd(rv['net']['difference'])} were the true effect, it would fall below the {usd(-loss)} safety boundary; more users would not make that effect safe. If the observed refund increase persisted, refund safety alone would need about {refundpilot['n_per_arm']:,} users per arm. Pilot effects are uncertain, so these are scenarios, not predictions.</p></div></details><ol><li><strong>Agree on economics.</strong> Define acceptable loss using margin, implementation cost and customer impact; confirm available traffic.</li><li><strong>Decide whether confirmation is worthwhile.</strong> Estimate test cost and precision for all criteria. If infeasible, retain the current checkout and redesign.</li><li><strong>Predefine the next test.</strong> Use a fresh independent fixed-horizon run, or a valid prospective sequential design. Specify sample cap and mature follow-up.</li><li><strong>Launch only after all agreed criteria clear.</strong> Operational readiness still requires review, followed by a staged rollout.</li></ol></div></div></section>
<section class="section"><div class="section-head"><span class="section-number">05</span><div><h2>What a reviewer should challenge</h2><details open><summary>Simulation and external validity</summary><div><p>All records are fictional and the randomization process is disclosed. The observed recommendation is based on estimated effects, not the simulator's hidden probabilities. Real experiments require audits of identities, assignment delivery, payment reconciliation, tracking gaps and spillovers.</p></div></details><details><summary>Repeated checking and subgroup fishing</summary><div><p>Stopping at the first favorable ordinary confidence interval increases false positives. Use a fixed horizon or a valid sequential design. Searching many device, customer or date slices creates accidental winners. This project makes no segment launch claims; balance and shorter-window diagnostics are exploratory.</p></div></details><details><summary>Refund interpretation and missing costs</summary><div><p>Refunds among buyers are {pct(g['control']['refund_buyer_rate'])} versus {pct(g['new']['refund_buyer_rate'])}, but purchasing is affected by assignment. That conditional comparison is descriptive. The primary refund guardrail retains all assigned users. Neither revenue metric includes fees, fulfillment costs, profit margin, chargebacks or long-term customer effects.</p></div></details><details><summary>Explore the evidence and reproduce it</summary><div><ul><li><a href="docs/METHODOLOGY.md">Measurement, inference and planning assumptions</a></li><li><a href="docs/DATA_DICTIONARY.md">Raw tables and simulation provenance</a></li><li><a href="results/window_sensitivity.csv">Exploratory 1-, 3- and 7-day point estimates, without inference</a></li><li><a href="results/metrics.json">Full precision results and decision gates</a></li><li><a href="docs/INTERVIEW_GUIDE.md">Interview walkthrough and reviewer questions</a></li></ul></div></details></div></div></section></main><footer class="wrap">Built for an analyst portfolio. Synthetic data, disclosed assumptions, reproducible results.<br>Seed {m['seed']} · Bootstrap seed {m['bootstrap_seed']} · Enrollment January 1–28, 2026 · Frozen extract {cfg['measurement']['extract_at']} UTC.</footer></body></html>'''
    (root/'readout.html').write_text(page)
    summary=f'''# Should we launch the new checkout?

**{decision}.** {decision_copy(m)[0]} {decision_copy(m)[1]}

**Clearly labeled simulation:** {q['assigned_users']:,} fictional users, 50:50 random assignment, {cfg['measurement']['purchase_days']}-day paid-order window and {cfg['measurement']['refund_days']}-day refund follow-up. All outcomes are mature.

| Metric | Control | New checkout | Difference [95% CI] |
|---|---:|---:|---:|
'''+''.join('| '+' | '.join(row)+' |\n' for row in rows)+f'''
## What the evidence means

Conversion rises by {pp(c['difference'])}, or {c['relative_change']*100:+.2f}% relative (relative 95% CI: {c['relative_ci95'][0]*100:+.2f}% to {c['relative_ci95'][1]*100:+.2f}%). Its interval includes no improvement. The refund estimate is higher, but that difference is also uncertain. Revenue and refund intervals do not rule out unacceptable harm at the illustrative margins.

The revenue bridge reconciles the after-refund difference: conversion contributes {signed_usd(b['gross_contributions']['conversion'])}/user, order frequency {signed_usd(b['gross_contributions']['orders_per_buyer'])}, basket value {signed_usd(b['gross_contributions']['average_order_value'])}, and additional refunds {signed_usd(b['additional_refund_drag'])}. This is descriptive arithmetic, not causal mediation; rounded contributions may not sum exactly.

## What would change the decision?

Launch candidate only when conversion lower 95% bound > 0, after-refund revenue/user lower bound > {usd(-loss)}, and refunded-user rate upper bound < {pp(rm)}. All must clear at an agreed analysis. Current gates cleared: {sum(m['decision']['gates'].values())}/3. These margins are illustrative and require stakeholder agreement; they were not historically preregistered.

Conversion planning needs approximately {p['approx_n_per_arm']:,} users per arm for +{p['target_absolute_effect']*100:.2f} pp at {p['marginal_power']:.0%} power. **Revenue safety needs about {net['n_per_arm']:,} per arm under zero true loss**, using the {usd(loss)} margin and pilot variance. At {p['reference_users_per_arm']:,} per arm its approximate power is only {net['power_at_reference_n']:.0%}. If the true revenue difference equaled the observed {usd(rv['net']['difference'])}, it would be below the safety boundary; more data would not make it safe.

Agree on economic tolerance, test cost and available traffic. Use a fresh independent confirmatory test only if feasible; otherwise retain the existing checkout and redesign. The planning calculations are approximate powers for each individual criterion, not a joint 80% probability of passing all gates. Do not extend the pilot until a favorable unadjusted interval appears.

## Trust and limitations

Assignment counts are {g['control']['n']:,} vs {g['new']['n']:,}; SRM p={m['allocation']['p_value']:.3f}. {q['duplicate_extra_rows']} exact duplicate deliveries are removed. No conflicting assignments; all {q['nonbuyers_retained']:,} nonbuyers remain. Independent Python reconciles every SQL analysis row, including order windows, refunds and checkout events.

Proportions use Wilson/Newcombe intervals; revenue uses {m['bootstrap_replicates']:,} within-arm user bootstrap resamples. Individual 95% intervals do not have joint 95% coverage. Repeated checking and many subgroup comparisons can inflate false positives. Buyer-only refund rates are descriptive because treatment changes who buys. After-refund revenue is not profit. The simulation omits real-world instrumentation errors, fraud, seasonality, spillovers and long-term effects.

See [the two-page PDF](experiment-readout.pdf), [visual readout](readout.html), [methodology](docs/METHODOLOGY.md), and [reproduction guide](README.md).
'''
    (root/'READOUT.md').write_text(summary)
    pdf_path=make_pdf(root,m,q,drawings)
    import pypdfium2 as pdfium
    with pdfium.PdfDocument(str(pdf_path)) as doc:
        doc[0].render(scale=1.8).to_pil().save(root/'charts/readout-preview.png')
    print('Built six SVG charts, HTML readout, decision memo and two-page PDF.')
    return m


if __name__=='__main__':build()

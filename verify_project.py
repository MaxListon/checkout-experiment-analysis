"""Verify saved artifacts offline and render the PDF preview. No browser automation."""
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import unquote
import hashlib
import json
import math
import re
import sqlite3
import xml.etree.ElementTree as ET
import numpy as np
import pypdfium2 as pdfium
from statistics_tools import decide
from quality import require
from run_analysis import save_json

ROOT=Path(__file__).resolve().parents[1]


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__();self.links=[];self.ids=[];self.image_alts=[]
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        if 'id' in attrs:self.ids.append(attrs['id'])
        if tag=='a':self.links.append(attrs.get('href',''))
        if tag=='img':self.image_alts.append(attrs.get('alt',''))


def verify(root=ROOT):
    root=Path(root);m=json.loads((root/'results/metrics.json').read_text())
    q=json.loads((root/'results/quality_checks.json').read_text())
    manifest=json.loads((root/'results/data_sha256.json').read_text())
    for name,expected in manifest.items():
        require(hashlib.sha256((root/name).read_bytes()).hexdigest()==expected,f'CSV changed: {name}')
    original=json.loads((root/'docs/original_pilot_sha256.json').read_text())
    original_preserved=all(manifest.get(k)==v for k,v in original.items())
    baseline=json.loads((root/'docs/original_pilot_estimates.json').read_text())
    differences=[]
    for metric in ['conversion','refunds']:
        differences.append(abs(m[metric]['difference']-baseline[metric]['difference']))
        differences.extend(abs(np.array(m[metric]['ci95'])-baseline[metric]['ci95']))
    for metric in ['gross','net']:
        differences.append(abs(m['revenue'][metric]['difference']-baseline['revenue'][metric]['difference']))
        differences.extend(abs(np.array(m['revenue'][metric]['ci95'])-baseline['revenue'][metric]['ci95']))
    max_change=float(max(differences))
    if original_preserved:
        require(max_change<1e-10,'Original data produced materially different headline estimates')
    draws=np.loadtxt(root/'results/bootstrap_draws.csv',delimiter=',',skiprows=1)
    require(len(draws)==m['bootstrap_replicates'],'Wrong bootstrap sample count')
    for i,key in enumerate(['gross','net']):
        require(np.allclose(np.quantile(draws[:,i],[.025,.975]),m['revenue'][key]['ci95'],rtol=0,atol=1e-12),f'Wrong {key} bootstrap CI')
    margin=m['config']['decision']
    decision=decide(m['conversion']['ci95'],m['revenue']['net']['ci95'],m['refunds']['ci95'],
        margin['net_revenue_loss_margin_usd'],margin['refund_rate_increase_margin'])
    if m['allocation']['flagged']:decision['status']='PAUSE — INVESTIGATE ALLOCATION'
    require(decision==m['decision'],'Decision inconsistent with evidence')
    with sqlite3.connect(root/'data/experiment.sqlite') as con:
        require(con.execute('PRAGMA integrity_check').fetchone()[0]=='ok','SQLite integrity issue')
        for v,n,buyers,gross,net in con.execute('SELECT variant,COUNT(*),SUM(converted),AVG(gross_cents)/100.0,AVG(net_cents)/100.0 FROM user_analysis GROUP BY variant'):
            g=m['groups'][v]
            require(n==g['n'] and buyers==g['buyers'],'Count mismatch in saved database')
            require(math.isclose(gross,g['gross_rpu']) and math.isclose(net,g['net_rpu']),'Revenue mismatch in saved database')
        require(con.execute('SELECT purchase_days FROM experiment_config').fetchone()[0]==m['config']['measurement']['purchase_days'],'Exploratory window left active')
    notebook=json.loads((root/'analysis.ipynb').read_text())
    cells=[c for c in notebook['cells'] if c['cell_type']=='code']
    require([c['execution_count'] for c in cells]==list(range(1,len(cells)+1)),'Notebook not fully executed')
    require(all(not any(o['output_type']=='error' for o in c['outputs']) for c in cells),'Notebook has errors')
    for cell in cells:compile(''.join(cell['source']),'notebook','exec')
    parser=ReportParser();page=(root/'readout.html').read_text();parser.feed(page)
    require(len(parser.ids)==len(set(parser.ids)),'Duplicate HTML IDs')
    require(len(parser.image_alts)==6 and all(parser.image_alts),'Missing chart descriptions')
    for target in parser.links:
        if target.startswith('#'):require(target[1:] in parser.ids,f'Broken section link {target}')
        elif not target.startswith(('https:','http:')):require((root/unquote(target)).exists(),f'Broken file link {target}')
    for path in root.rglob('*.md'):
        for target in re.findall(r'\]\(([^)]+)\)',path.read_text()):
            if target.startswith(('https:','http:','#')):continue
            require((path.parent/target).exists(),f'Broken Markdown link in {path.name}: {target}')
    for path in (root/'charts').glob('*.svg'):ET.fromstring(path.read_text())
    pdf_path=root/'experiment-readout.pdf';doc=pdfium.PdfDocument(str(pdf_path))
    require(len(doc)==2,'Expected two-page brief')
    text=''.join(doc[i].get_textpage().get_text_range() for i in range(len(doc)))
    for expected in ['24,000','0.59','644,548','SIMULATED DATA']:
        require(expected in text,f'Missing PDF content: {expected}')
    # Geometry check supplements, but does not replace, visual review.
    for page_index in range(len(doc)):
        page_pdf=doc[page_index];tp=page_pdf.get_textpage();w,h=page_pdf.get_size()
        for index in range(tp.count_chars()):
            char=tp.get_text_range(index,1)
            if not char.strip():continue
            l,b,r,t=tp.get_charbox(index)
            require(l>=0 and r<=w and b>=0 and t<=h,f'PDF character outside page {page_index+1}')
    doc[0].render(scale=1.8).to_pil().save(root/'charts/readout-preview.png')
    pdf_hash=hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    notes_path=root/'results/visual_review.json'
    notes=json.loads(notes_path.read_text()) if notes_path.exists() else {}
    reviewed=notes.get('pdf_sha256')==pdf_hash and notes.get('status')=='PASS'
    report={'status':'PASS','source_quality':q['status'],'original_pilot_csvs_preserved':original_preserved,
        'csv_hashes_verified':True,'max_change_from_original_headline_estimates':max_change,'bootstrap_intervals_reconstructed':True,
        'decision_recomputed':True,'sqlite_integrity_and_saved_metrics':'PASS',
        'primary_window_restored':True,'executed_notebook_cells':len(cells),
        'local_links_and_svg_structure':'PASS','pdf_pages':len(doc),
        'pdf_text_and_page_bounds':'PASS','pdf_sha256':pdf_hash,
        'pdf_visual_review':'PASS' if reviewed else 'Pending review of this exact PDF',
        'html_browser_preview':'Unavailable: prior local-file browser policy block. No browser visual verification claimed.'}
    save_json(root/'results/verification.json',report)
    print(f"Artifact checks PASS; {len(cells)} executed cells; 2 PDF pages; original data preserved: {original_preserved}.")
    return report


if __name__=='__main__':verify()

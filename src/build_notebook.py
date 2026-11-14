"""Create a notebook with real saved outputs by executing every code cell in Python.

The cells use only standard Python and NumPy, and execute in one shared namespace.
No notebook kernel-specific syntax is used. Opening in Jupyter supports normal reruns.
"""
from pathlib import Path
import contextlib
import io
import json
import os
import platform
import traceback

ROOT=Path(__file__).resolve().parents[1]


def markdown(source):
    return {'cell_type':'markdown','metadata':{},'source':source.splitlines(True)}


def code(source):
    return {'cell_type':'code','metadata':{},'source':source.splitlines(True),'execution_count':None,'outputs':[]}


def build(root=ROOT):
    root=Path(root)
    cells=[
        markdown('''# Should we launch the new checkout?

**Product analytics / Experiment 03 / Clearly labeled simulation**

This notebook is an analytical walkthrough with executed outputs. It uses the same simulated user assignment, events, orders and refunds as the portfolio readout. The full pipeline is in `src/run_analysis.py`; run `python src/run_analysis.py --regenerate` to recreate raw data and all statistical results, then `python src/build_readout.py` for reports.

**Decision:** continue testing only if confirmation is feasible. Higher estimated conversion is insufficient when revenue and refund safety remain unresolved.
'''),
        code('''from pathlib import Path
import csv, json, sqlite3, sys
import numpy as np
ROOT = Path.cwd()
if not (ROOT / 'config.json').exists():
    raise RuntimeError('Run from the checkout-experiment project directory.')
sys.path.insert(0, str(ROOT / 'src'))
from statistics_tools import binary_effect, sample_ratio_test, decide
from run_analysis import load_database
from quality import validate_sources, reconcile
config = json.loads((ROOT / 'config.json').read_text())
metrics = json.loads((ROOT / 'results/metrics.json').read_text())
print('Source: fictional, locally generated randomized experiment')
print('Seed:', config['simulation']['seed'])
print('Purchase/refund windows:', config['measurement']['purchase_days'], '/', config['measurement']['refund_days'], 'days')
'''),
        markdown('''## 1. Establish the unit of analysis and data quality

Randomization is independent 50:50 at user level. All assigned users belong in the denominator. Exact duplicate deliveries are removed; variant or time conflicts stop analysis. The following cells load the source CSVs, enforce the schema and execute the production SQL again in an in-memory database.
'''),
        code('''con = load_database(ROOT, config)
quality = validate_sources(con, config)
print(json.dumps(quality, indent=2))
print('Raw order/refund counts:', con.execute('SELECT COUNT(*) FROM orders').fetchone()[0], con.execute('SELECT COUNT(*) FROM refunds').fetchone()[0])
'''),
        code('''sql = (ROOT / 'sql/01_user_analysis.sql').read_text()
con.executescript(sql)
print(json.dumps(reconcile(con, config), indent=2))
arm_rows = con.execute('SELECT variant, COUNT(*), SUM(converted), AVG(gross_cents)/100.0, AVG(net_cents)/100.0 FROM user_analysis GROUP BY variant').fetchall()
print('\\nVariant | users | buyers | gross RPU | after-refund RPU')
for variant,n,buyers,gross,net in arm_rows:
    print(f'{variant:8} | {n:5,d} | {buyers:5,d} | ${gross:.2f} | ${net:.2f}')
'''),
        markdown('''### Why the SQL joins are ordered this way

Refund ledger → order totals → user totals → assigned users. This prevents split refunds from multiplying order value. The final joins keep users with no events or purchases; zero outcomes are explicit. Orders count in [assignment, assignment + 7 days), and refunds in [order, order + 30 days), with complete follow-up.
'''),
        code('''print(sql)
'''),
        markdown('''## 2. Check allocation before interpreting outcomes

The sample-ratio mismatch test uses unique assigned users. A p-value below 0.001 is an investigation flag. An unflagged result does not prove tracking or exposure delivery is correct.
'''),
        code('''n0, x0 = arm_rows[0][1:3]
n1, x1 = arm_rows[1][1:3]
allocation = sample_ratio_test(n0, n1, config['measurement']['expected_treatment_share'])
print(json.dumps(allocation, indent=2))
'''),
        markdown('![Allocation counts](charts/allocation.svg)\n'),
        markdown('''## 3. Estimate conversion effects with uncertainty

Absolute effect: new conversion minus control conversion, reported in percentage points. Relative effect: new/control minus one. These are different quantities. The absolute interval is Newcombe's independent-proportions method using Wilson limits; the relative interval uses a log risk ratio.
'''),
        code('''conversion = binary_effect(x0, n0, x1, n1)
print(f"Control: {conversion['control']:.2%}; new: {conversion['new']:.2%}")
print(f"Absolute difference: {conversion['difference']*100:+.2f} pp")
print('95% absolute CI:', [round(x*100, 3) for x in conversion['ci95']], 'pp')
print(f"Relative lift: {conversion['relative_change']:+.2%}")
print('95% relative CI:', [round(x*100, 3) for x in conversion['relative_ci95']], '%')
'''),
        markdown('![Conversion effect and uncertainty](charts/conversion.svg)\n\nThe interval includes a small decline and a commercially useful improvement. Inconclusive is not equivalent to no effect.\n'),
        markdown('''## 4. Revenue: retain zeroes and resample users

The pipeline performs 10,000 independent within-arm user resamples. Each selected user carries all of their orders and refunds. Gross and after-refund outcomes use the same user draws. This cell recomputes the reported intervals from the saved bootstrap draws, rather than copying numbers into the notebook.
'''),
        code('''draws = np.loadtxt(ROOT / 'results/bootstrap_draws.csv', delimiter=',', skiprows=1)
print('Bootstrap replicates:', len(draws))
for i,key in enumerate(['gross','net']):
    bounds = np.quantile(draws[:,i], [.025,.975])
    np.testing.assert_allclose(bounds, metrics['revenue'][key]['ci95'])
    print(f"{key}: difference ${metrics['revenue'][key]['difference']:+.2f}; 95% CI ${bounds[0]:+.2f} to ${bounds[1]:+.2f}")
print('All saved bootstrap intervals independently reconstructed.')
'''),
        markdown('![Revenue effects and uncertainty](charts/revenue.svg)\n'),
        code('''bridge = metrics['revenue_bridge']
for label,value in bridge['gross_contributions'].items():
    print(f'{label:24s} {value:+.4f} USD/user')
print(f"{'additional_refund_drag':24s} {bridge['additional_refund_drag']:+.4f} USD/user")
print(f"{'net_difference':24s} {bridge['net_difference']:+.4f} USD/user")
'''),
        markdown('''![Revenue decomposition](charts/revenue_drivers.svg)

This is an exact arithmetic decomposition averaged across six factor replacement orders. It is descriptive, not evidence that each factor independently changed because of the checkout.
'''),
        markdown('''## 5. Refund safety and the launch rule

The guardrail denominator is all assigned users. The buyer-only rate is descriptive because treatment can change who buys. Launch requires all three criteria. The margins are illustrative business assumptions, not historical preregistration or stakeholder approval.
'''),
        code('''print(json.dumps(metrics['refunds'], indent=2))
decision = decide(conversion['ci95'], metrics['revenue']['net']['ci95'], metrics['refunds']['ci95'],
                  config['decision']['net_revenue_loss_margin_usd'],
                  config['decision']['refund_rate_increase_margin'])
print(json.dumps(decision, indent=2))
'''),
        markdown('![Refund uncertainty](charts/refunds.svg)\n'),
        markdown('''## 6. Is more testing worthwhile?

Conversion-only sample size is insufficient for the full launch decision. Below are planning scenarios using pilot variance, a one-sided 2.5% safety boundary and 80% power for each criterion. They do not imply 80% power to pass all criteria jointly.
'''),
        code('''print('Conversion users per arm:', metrics['planning']['approx_n_per_arm'])
print('\\nRevenue safety if true revenue change is zero:')
for row in metrics['planning']['net_safety_scenarios']:
    if row['assumed_true_difference_usd'] == 0:
        print(f"Loss margin ${row['loss_margin_usd']:.2f}: {row['n_per_arm']:,} per arm; power at {metrics['planning']['reference_users_per_arm']:,}/arm = {row['power_at_reference_n']:.1%}")
print('\\nRefund safety scenarios:')
for row in metrics['planning']['refund_safety_scenarios']:
    print(f"Assumed increase {row['assumed_true_difference']*100:.3f} pp: {row['n_per_arm']:,} per arm")
'''),
        markdown('![Next-test sample requirements](charts/sample_size.svg)\n'),
        markdown('''## 7. Exploratory checks without searching for a win

Shorter-window results use the same users and fixed raw data. They are exploratory point estimates only: no confidence intervals or hypothesis tests are calculated for them. They are not candidate windows to select after viewing outcomes and do not replace the configured primary analysis. Pre-assignment balance summaries do not establish randomization integrity by themselves.
'''),
        code('''for name in ['window_sensitivity','exploratory_balance']:
    print(name)
    print((ROOT / 'results' / f'{name}.csv').read_text())
con.close()
'''),
        markdown('''## Final recommendation and limitations

Retain the existing checkout. Consider a fresh independently planned test only after confirming economic tolerance, sample requirements and traffic capacity. If confirmation is too expensive, redesign the proposal. Do not keep adding users until an ordinary fixed-horizon interval becomes favorable.

This dataset is simulated, with stable identities, complete logging and no spillovers. Real evidence needs instrumentation audits. After-refund revenue excludes costs and long-term effects. Multiple subgroup searches can create false positives; no segment launch claims are made. Individual 95% intervals are not simultaneous 95% intervals.

See `docs/METHODOLOGY.md` for formulas, assumptions and references, and `docs/INTERVIEW_GUIDE.md` for a concise explanation of the project.
''')
    ]
    namespace={'__name__':'__notebook__'};execution=0
    previous=Path.cwd();os.chdir(root)
    try:
        for i,cell in enumerate(cells):
            cell['id']=f'checkout-v2-{i:02d}'
            if cell['cell_type']!='code':continue
            execution+=1;buffer=io.StringIO()
            with contextlib.redirect_stdout(buffer):
                exec(compile(''.join(cell['source']),f'notebook-cell-{i}','exec'),namespace)
            cell['execution_count']=execution
            if buffer.getvalue():cell['outputs']=[{'output_type':'stream','name':'stdout','text':buffer.getvalue().splitlines(True)}]
    finally:os.chdir(previous)
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{
        'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},
        'language_info':{'name':'python','version':platform.python_version()},
        'execution_note':'All code cells executed in order in a shared Python namespace by src/build_notebook.py; no kernel-specific syntax.'},'cells':cells}
    (root/'analysis.ipynb').write_text(json.dumps(notebook,indent=2)+'\n')
    print(f'Executed and saved {execution} notebook code cells.')


if __name__=='__main__':build()

"""Reproducible CLI. Default analyzes existing CSVs; --regenerate recreates simulation."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import math
import platform
import sqlite3
import numpy as np
from simulate import generate
from quality import validate_sources, reconcile, require
from statistics_tools import (wilson, binary_effect, sample_ratio_test, bootstrap_revenue,
    decide, conversion_sample_size, safety_sample_size, safety_power, revenue_decomposition)

ROOT = Path(__file__).resolve().parents[1]
TABLES=['users','assignments','checkout_events','orders','refunds']


def save_json(path, value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False,default=lambda x:float(x))+'\n')


def write_csv(path, header, rows):
    with path.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(header);w.writerows(rows)


def load_database(root, config):
    """Build in memory, with enforced keys; publish database only after success."""
    con=sqlite3.connect(':memory:')
    con.executescript((root/'sql/00_schema.sql').read_text())
    for table in TABLES:
        with (root/'data'/f'{table}.csv').open(newline='') as f:
            reader=csv.reader(f); header=next(reader)
            expected=[r[1] for r in con.execute(f'PRAGMA table_info({table})')]
            require(header==expected,f'Unexpected CSV schema for {table}')
            con.executemany(f'INSERT INTO {table} VALUES ({",".join("?" for _ in header)})',reader)
    measurement=config['measurement']
    con.execute('INSERT INTO experiment_config VALUES (1,?,?,?)',
                (measurement['purchase_days'],measurement['refund_days'],measurement['extract_at']))
    return con


def run(root=ROOT, regenerate=False):
    root=Path(root)
    config=json.loads((root/'config.json').read_text())
    require(config['inference']['confidence_level']==.95,'This report implements 95% intervals')
    for directory in ['data','results','charts']:(root/directory).mkdir(exist_ok=True)
    if regenerate: generate(root,config)
    con=load_database(root,config)
    qa=validate_sources(con,config)
    sql=(root/'sql/01_user_analysis.sql').read_text()
    con.executescript(sql)
    qa.update(reconcile(con,config));qa['status']='PASS'
    cols=[r[1] for r in con.execute('PRAGMA table_info(user_analysis)')]
    records=con.execute('SELECT * FROM user_analysis ORDER BY user_id').fetchall()
    a={col:np.array([r[i] for r in records]) for i,col in enumerate(cols)}
    numeric=['converted','gross_cents','refund_cents','net_cents','any_refund','order_count','started_checkout']
    for col in numeric:a[col]=a[col].astype(float)
    groups={v:{col:a[col][a['variant']==v] for col in a} for v in ['control','new']}
    stats={}
    for v,g in groups.items():
        n=len(g['converted']);buyers=int(g['converted'].sum());orders=int(g['order_count'].sum())
        stats[v]={'n':n,'buyers':buyers,'orders':orders,
                  'checkout_starters':int(g['started_checkout'].sum()),
                  'conversion':float(g['converted'].mean()),'conversion_ci95':wilson(buyers,n),
                  'gross_rpu':float(g['gross_cents'].mean()/100),
                  'net_rpu':float(g['net_cents'].mean()/100),
                  'refund_rpu':float(g['refund_cents'].mean()/100),
                  'refunded_users':int(g['any_refund'].sum()),
                  'refund_user_rate':float(g['any_refund'].mean()),
                  'refund_buyer_rate':float(g['any_refund'].sum()/buyers) if buyers else None,
                  'orders_per_buyer':orders/buyers if buyers else None,
                  'average_order_value':float(g['gross_cents'].sum()/100/orders) if orders else None,
                  'net_variance_usd':float(np.var(g['net_cents']/100,ddof=1)),
                  'zero_revenue_share':float((g['gross_cents']==0).mean()),
                  'max_user_revenue':float(g['gross_cents'].max()/100),
                  'top_one_percent_revenue_share':float(np.sort(g['gross_cents'])[-math.ceil(n*.01):].sum()/g['gross_cents'].sum()) if orders else None}
    c0,c1=stats['control'],stats['new']
    conversion=binary_effect(c0['buyers'],c0['n'],c1['buyers'],c1['n'])
    refund=binary_effect(c0['refunded_users'],c0['n'],c1['refunded_users'],c1['n'])
    matrices={v:np.column_stack([g['gross_cents']/100,g['net_cents']/100]) for v,g in groups.items()}
    revenue,draws=bootstrap_revenue(matrices['control'],matrices['new'],
        config['inference']['bootstrap_replicates'],config['inference']['bootstrap_seed'])
    allocation=sample_ratio_test(c0['n'],c1['n'],config['measurement']['expected_treatment_share'])
    allocation['alert_threshold']=config['inference']['srm_alert_threshold']
    allocation['flagged']=allocation['p_value']<allocation['alert_threshold']
    margins=config['decision']
    decision=decide(conversion['ci95'],revenue['net']['ci95'],refund['ci95'],
                    margins['net_revenue_loss_margin_usd'],margins['refund_rate_increase_margin'])
    if allocation['flagged']: decision['status']='PAUSE — INVESTIGATE ALLOCATION'
    # Diagnostic arithmetic identity: CVR * orders/buyer * average order value.
    factors={v:[stats[v][k] for k in ['conversion','orders_per_buyer','average_order_value']] for v in stats}
    bridge=None
    if all(x is not None for values in factors.values() for x in values):
        contribution=revenue_decomposition(factors['control'],factors['new'])
        refund_drag=-(c1['refund_rpu']-c0['refund_rpu'])
        bridge={'method':'Average of all six factor replacement orders; descriptive, not causal',
                'gross_contributions':dict(zip(['conversion','orders_per_buyer','average_order_value'],contribution)),
                'additional_refund_drag':refund_drag,'net_difference':revenue['net']['difference']}
        require(abs(sum(contribution)+refund_drag-revenue['net']['difference'])<1e-10,'Revenue bridge fails reconciliation')
    power=config['planning']['marginal_power'];reference=config['planning']['reference_users_per_arm']
    variance=c0['net_variance_usd']+c1['net_variance_usd']
    net_rows=[]
    for margin in dict.fromkeys([margins['net_revenue_loss_margin_usd'],.25,.5,1.0]):
        for assumed in [0.0,revenue['net']['difference']]:
            distance=assumed+margin
            net_rows.append({'loss_margin_usd':margin,'assumed_true_difference_usd':assumed,
                            'n_per_arm':safety_sample_size(variance,distance,power),
                            'power_at_reference_n':safety_power(reference,variance,distance)})
    refund_rows=[]
    for assumed in [0.0,.001,refund['difference']]:
        p0=refund['control'];p1=p0+assumed
        var=p0*(1-p0)+p1*(1-p1)
        distance=margins['refund_rate_increase_margin']-assumed
        refund_rows.append({'assumed_true_difference':assumed,
                           'n_per_arm':safety_sample_size(var,distance,power),
                           'power_at_reference_n':safety_power(reference,var,distance)})
    planning={'marginal_power':power,'reference_users_per_arm':reference,
              'target_absolute_effect':config['planning']['conversion_target_absolute'],
              'approx_n_per_arm':conversion_sample_size(conversion['control'],config['planning']['conversion_target_absolute'],power),
              'net_safety_scenarios':net_rows,'refund_safety_scenarios':refund_rows,
              'note':'First-order marginal-power approximations, not a joint-power or launch guarantee. Pilot effects are uncertain; margins must be agreed before confirmation.'}
    # Point-estimate window sensitivity, fixed raw data and assigned-user denominator.
    sensitivity=[]
    # Deduplicate if the configured primary window is already 1 or 3 days.
    windows = list(dict.fromkeys([1,3,config['measurement']['purchase_days']]))
    for days in windows:
        con.execute('UPDATE experiment_config SET purchase_days=?',(days,));con.executescript(sql)
        for variant,n,buyers,gross,net in con.execute('SELECT variant,COUNT(*),SUM(converted),AVG(gross_cents)/100.0,AVG(net_cents)/100.0 FROM user_analysis GROUP BY variant'):
            sensitivity.append([days,variant,n,buyers,buyers/n,gross,net])
    con.execute('UPDATE experiment_config SET purchase_days=?',(config['measurement']['purchase_days'],));con.executescript(sql)
    qa['restored_primary_reconciliation']=reconcile(con,config)['reconciliation']
    # Descriptive pre-assignment balance, standardized differences on binary attributes.
    balance=[]
    for col,level in [('device','mobile'),('customer_type','returning')]:
        p0=float((groups['control'][col]==level).mean());p1=float((groups['new'][col]==level).mean())
        sd=math.sqrt((p0*(1-p0)+p1*(1-p1))/2)
        balance.append([col,level,p0,p1,p1-p0,(p1-p0)/sd if sd else 0])
    result={'simulation':True,'project_version':config['project_version'],'seed':config['simulation']['seed'],
            'bootstrap_seed':config['inference']['bootstrap_seed'],
            'bootstrap_replicates':config['inference']['bootstrap_replicates'],
            'config':config,'groups':stats,'conversion':conversion,'refunds':refund,'revenue':revenue,
            'allocation':allocation,'planning':planning,'decision':decision,'revenue_bridge':bridge}
    # Publish after all data contracts and reconciliations have passed.
    save_json(root/'results/metrics.json',result)
    save_json(root/'results/quality_checks.json',qa)
    write_csv(root/'data/user_analysis.csv',cols,records)
    write_csv(root/'results/window_sensitivity.csv',['purchase_days','variant','assigned_users','buyers','conversion','gross_rpu','net_rpu','interpretation'],[[*row,'Exploratory point estimate only; no confidence interval or significance test'] for row in sensitivity])
    write_csv(root/'results/exploratory_balance.csv',['attribute','level','control_share','new_share','difference','standardized_difference'],balance)
    write_csv(root/'results/bootstrap_draws.csv',['gross_rpu_difference','net_rpu_difference'],draws)
    save_json(root/'results/environment.json',{'python':platform.python_version(),'numpy':np.__version__,
        'sqlite':sqlite3.sqlite_version,'platform':platform.system()})
    save_json(root/'results/data_sha256.json',{str(f.relative_to(root)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted((root/'data').glob('*.csv'))})
    con.commit()
    target=root/'data/experiment.sqlite'
    if target.exists():target.unlink()
    with sqlite3.connect(target) as output:con.backup(output)
    con.close()
    print(f"Analyzed {c0['n']+c1['n']:,} assigned users; quality checks PASS.")
    print(f"Recommendation: {decision['status']}")
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regenerate',action='store_true',help='Recreate the fictional source data before analyzing')
    args=parser.parse_args()
    run(regenerate=args.regenerate)

"""Synthetic raw data only. Seed and draw order preserve the original pilot."""
from datetime import datetime, timedelta
import csv
import math
import numpy as np


def generate(root, config):
    """Write five fictional source tables. Never used to choose a favorable result."""
    SEED = config['simulation']['seed']
    N = config['simulation']['users']
    (root / 'data').mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    base = datetime.fromisoformat(config['simulation']['enrollment_start'])
    stamp = lambda t: t.strftime('%Y-%m-%dT%H:%M:%S')
    rows = {k: [] for k in ['users','assignments','checkout_events','orders','refunds']}
    headers = {
     'users':['user_id','device','customer_type'],
     'assignments':['user_id','variant','assigned_at'],
     'checkout_events':['event_id','user_id','event_type','event_at'],
     'orders':['order_id','user_id','ordered_at','amount_cents','status'],
     'refunds':['refund_id','order_id','refunded_at','amount_cents']}
    # Independent Bernoulli assignment; pretreatment attributes precede treatment.
    for i in range(N):
        uid = f'U{i:06d}'
        device = 'mobile' if rng.random() < .67 else 'desktop'
        customer = 'returning' if rng.random() < .30 else 'new'
        treatment = rng.random() < config['measurement']['expected_treatment_share']
        variant = 'new' if treatment else 'control'
        at = base + timedelta(seconds=int(rng.integers(0,config['simulation']['enrollment_days']*86400)))
        rows['users'].append([uid,device,customer])
        rows['assignments'].append([uid,variant,stamp(at)])
        # Constant additive effect; no implanted subgroup wins.
        p = .112 + .026*(customer == 'returning') + .016*(device == 'desktop') + .006*treatment
        buyer = rng.random() < p
        start = buyer or rng.random() < .40
        if start:
            rows['checkout_events'].append([f'E{len(rows["checkout_events"]):06d}',uid,'checkout_started',stamp(at+timedelta(seconds=60))])
        if buyer:
            for j in range(1 + int(rng.random() < .08)):
                ot = at + timedelta(seconds=int(rng.integers(120,config['measurement']['purchase_days']*86400)))
                amount = int(round(rng.lognormal(math.log(78),.75)*100))
                oid = f'O{len(rows["orders"]):06d}'
                rows['orders'].append([oid,uid,stamp(ot),amount,'paid'])
                rows['checkout_events'].append([f'E{len(rows["checkout_events"]):06d}',uid,'checkout_completed',stamp(ot)])
                if rng.random() < (.080 + .008*treatment):
                    refund = int(round(amount * (1 if rng.random()<.80 else .5)))
                    rt = ot + timedelta(seconds=int(rng.integers(1,config['measurement']['refund_days']*86400)))
                    # Some partial refunds are split across two ledger records.
                    parts = [refund//2,refund-refund//2] if rng.random()<.20 else [refund]
                    for part in parts:
                        rows['refunds'].append([f'R{len(rows["refunds"]):06d}',oid,stamp(rt),part])
        # Deliberate window/status traps, excluded from the primary outcome.
        if i % 211 == 0:
            rows['orders'].append([f'O{len(rows["orders"]):06d}',uid,stamp(at+timedelta(days=config['measurement']['purchase_days']+1)),9900,'paid'])
        if i % 997 == 0:
            rows['orders'].append([f'O{len(rows["orders"]):06d}',uid,stamp(at-timedelta(hours=1)),5000,'paid'])
        if i % 613 == 0:
            rows['orders'].append([f'O{len(rows["orders"]):06d}',uid,stamp(at+timedelta(days=1)),4000,'cancelled'])
    # 24 ingestion duplicates, chosen independently of outcomes; not additional users.
    rows['assignments'] += [r.copy() for r in rows['assignments'][::1000]]
    for name, data in rows.items():
        with (root/'data'/f'{name}.csv').open('w',newline='') as f:
            w=csv.writer(f); w.writerow(headers[name]); w.writerows(data)

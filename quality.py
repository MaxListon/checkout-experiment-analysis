"""Data contracts and independent reconciliation. No removable assert gates."""
from datetime import datetime, timedelta


class DataQualityError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DataQualityError(message)


def validate_sources(con, config):
    """Fail before metrics; record useful counts for the reviewer."""
    times = [('assignments','assigned_at'),('checkout_events','event_at'),
             ('orders','ordered_at'),('refunds','refunded_at')]
    extract = config['measurement']['extract_at']
    for table,col in times:
        for value, in con.execute(f'SELECT {col} FROM {table}'):
            try:
                parsed = datetime.strptime(value,'%Y-%m-%dT%H:%M:%S')
                valid = parsed.strftime('%Y-%m-%dT%H:%M:%S') == value
            except (ValueError,TypeError):
                valid = False
            require(valid, f'Invalid normalized UTC timestamp in {table}: {value}')
            require(value < extract, f'Post-extract record in {table}')
    conflicts = con.execute('''SELECT user_id FROM assignments GROUP BY user_id
        HAVING COUNT(DISTINCT variant)>1 OR COUNT(DISTINCT assigned_at)>1''').fetchall()
    require(not conflicts,'Conflicting user assignments; analysis stopped')
    require(not con.execute('PRAGMA foreign_key_check').fetchall(),'Orphan source keys')
    require(con.execute('SELECT COUNT(DISTINCT variant) FROM assignments').fetchone()[0]==2,
            'Both treatment arms must contain users')
    max_assignment = con.execute('SELECT MAX(assigned_at) FROM assignments').fetchone()[0]
    total_days = config['measurement']['purchase_days']+config['measurement']['refund_days']
    require(datetime.fromisoformat(max_assignment)+timedelta(days=total_days)
            <= datetime.fromisoformat(extract),'Incomplete outcome maturity')
    require(con.execute('''SELECT COUNT(*) FROM refunds r JOIN orders o USING(order_id)
        WHERE r.refunded_at < o.ordered_at OR o.status!='paid' ''').fetchone()[0]==0,
        'Refund predates its order or references a non-paid order')
    require(con.execute('''SELECT COUNT(*) FROM (
        SELECT o.order_id FROM orders o JOIN refunds r USING(order_id)
        GROUP BY o.order_id HAVING SUM(r.amount_cents)>MAX(o.amount_cents))''').fetchone()[0]==0,
        'Refund ledger exceeds paid order amount')
    raw,unique=con.execute('SELECT COUNT(*),COUNT(DISTINCT user_id) FROM assignments').fetchone()
    return {'raw_assignment_rows':raw,'assigned_users':unique,
            'duplicate_extra_rows':raw-unique,'conflicting_users':len(conflicts),
            'complete_followup':True}


def reconcile(con, config):
    """Independent Python window/join logic for every assigned user's outcomes."""
    assignments={u:(v,datetime.fromisoformat(t)) for u,v,t in con.execute('SELECT * FROM assignments')}
    expected={u:[0,0,0,0,0] for u in assignments} # count, gross, refunds, any_refund, started
    eligible={}
    purchase=timedelta(days=config['measurement']['purchase_days'])
    refund=timedelta(days=config['measurement']['refund_days'])
    exclusions={'not_paid':0,'pre_assignment':0,'after_purchase_window':0,'unassigned':0}
    for oid,u,time,amount,status in con.execute('SELECT * FROM orders'):
        if u not in assignments:
            exclusions['unassigned']+=1; continue
        t=datetime.fromisoformat(time); at=assignments[u][1]
        if status!='paid': exclusions['not_paid']+=1
        elif t<at: exclusions['pre_assignment']+=1
        elif t>=at+purchase: exclusions['after_purchase_window']+=1
        else:
            expected[u][0]+=1; expected[u][1]+=amount; eligible[oid]=(u,t)
    for _,oid,time,amount in con.execute('SELECT * FROM refunds'):
        if oid in eligible:
            u,ot=eligible[oid]; rt=datetime.fromisoformat(time)
            if ot<=rt<ot+refund:
                expected[u][2]+=amount; expected[u][3]=1
    for _,u,kind,time in con.execute('SELECT * FROM checkout_events'):
        if u in assignments and kind=='checkout_started':
            at=assignments[u][1]; t=datetime.fromisoformat(time)
            if at<=t<at+purchase: expected[u][4]=1
    actual=con.execute('''SELECT user_id,order_count,gross_cents,refund_cents,
        any_refund,started_checkout,converted,net_cents FROM user_analysis''').fetchall()
    require(len(actual)==len(assignments),'Assigned users lost or duplicated')
    for u,count,gross,ref,any_ref,started,converted,net in actual:
        require([count,gross,ref,any_ref,started]==expected[u],f'SQL mismatch for {u}')
        require(converted==int(count>0) and net==gross-ref,f'Derived outcome mismatch for {u}')
    require(len({r[0] for r in actual})==len(actual),'Duplicate analysis users')
    return {'nonbuyers_retained':sum(v[0]==0 for v in expected.values()),
            'excluded_orders':sum(exclusions.values()),'excluded_order_reasons':exclusions,
            'reconciled_users':len(actual),'reconciliation':'PASS'}

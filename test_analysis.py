"""Behavioral regression tests for measurement contracts and decision logic.

Run: python -m unittest discover -s tests -v
"""
from pathlib import Path
import json
import sqlite3
import sys
import unittest
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from quality import DataQualityError, validate_sources
from statistics_tools import (wilson,binary_effect,bootstrap_revenue,sample_ratio_test,
    decide,safety_sample_size,safety_power,revenue_decomposition)


class MeasurementTests(unittest.TestCase):
    def setUp(self):
        self.con=sqlite3.connect(':memory:')
        self.con.executescript((ROOT/'sql/00_schema.sql').read_text())
        self.config=json.loads((ROOT/'config.json').read_text())
        self.con.execute("INSERT INTO experiment_config VALUES(1,7,30,'2026-03-07T00:00:00')")
        self.con.executemany('INSERT INTO users VALUES(?,?,?)',[('a','mobile','new'),('b','desktop','returning')])
        self.con.executemany('INSERT INTO assignments VALUES(?,?,?)',[
            ('a','control','2026-01-01T00:00:00'),('a','control','2026-01-01T00:00:00'),
            ('b','new','2026-01-01T00:00:00')])

    def tearDown(self):self.con.close()

    def analyze(self):self.con.executescript((ROOT/'sql/01_user_analysis.sql').read_text())

    def test_nonbuyers_and_duplicate_deliveries(self):
        self.analyze()
        self.assertEqual(self.con.execute('SELECT COUNT(*),SUM(converted),SUM(gross_cents) FROM user_analysis').fetchone(),(2,0,0))
        self.assertEqual(validate_sources(self.con,self.config)['duplicate_extra_rows'],1)

    def test_order_boundaries_payment_status_and_repeat_orders(self):
        self.con.executemany('INSERT INTO orders VALUES(?,?,?,?,?)',[
            ('start','a','2026-01-01T00:00:00',1000,'paid'),
            ('last','a','2026-01-07T23:59:59',2000,'paid'),
            ('cutoff','a','2026-01-08T00:00:00',9000,'paid'),
            ('before','a','2025-12-31T23:59:59',9000,'paid'),
            ('cancel','b','2026-01-02T00:00:00',9000,'cancelled')])
        self.analyze()
        self.assertEqual(self.con.execute("SELECT order_count,gross_cents,converted FROM user_analysis WHERE user_id='a'").fetchone(),(2,3000,1))
        self.assertEqual(self.con.execute("SELECT converted FROM user_analysis WHERE user_id='b'").fetchone(),(0,))

    def test_split_refunds_and_refund_boundary_without_fanout(self):
        self.con.execute("INSERT INTO orders VALUES('o','a','2026-01-01T00:00:00',1000,'paid')")
        self.con.executemany('INSERT INTO refunds VALUES(?,?,?,?)',[
            ('r1','o','2026-01-01T00:00:00',100),('r2','o','2026-01-30T23:59:59',200),
            ('r3','o','2026-01-31T00:00:00',300)])
        self.analyze()
        self.assertEqual(self.con.execute("SELECT gross_cents,refund_cents,net_cents,any_refund FROM user_analysis WHERE user_id='a'").fetchone(),(1000,300,700,1))

    def test_checkout_event_boundary(self):
        self.con.executemany('INSERT INTO checkout_events VALUES(?,?,?,?)',[
            ('e1','a','checkout_started','2026-01-01T00:00:00'),
            ('e2','b','checkout_started','2026-01-08T00:00:00')])
        self.analyze()
        self.assertEqual(self.con.execute('SELECT started_checkout FROM user_analysis ORDER BY user_id').fetchall(),[(1,),(0,)])

    def test_crossover_stops_python_and_sql(self):
        self.con.execute("INSERT INTO assignments VALUES('a','new','2026-01-01T00:00:00')")
        with self.assertRaises(DataQualityError):validate_sources(self.con,self.config)
        with self.assertRaises(sqlite3.IntegrityError):self.analyze()

    def test_reassignment_time_conflict_stops(self):
        self.con.execute("INSERT INTO assignments VALUES('a','control','2026-01-02T00:00:00')")
        with self.assertRaises(DataQualityError):validate_sources(self.con,self.config)
        with self.assertRaises(sqlite3.IntegrityError):self.analyze()

    def test_immature_followup_stops(self):
        self.con.execute("UPDATE assignments SET assigned_at='2026-03-01T00:00:00'")
        with self.assertRaises(DataQualityError):validate_sources(self.con,self.config)
        with self.assertRaises(sqlite3.IntegrityError):self.analyze()

    def test_missing_user_rejected_by_foreign_key(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("INSERT INTO assignments VALUES('missing','new','2026-01-01T00:00:00')")

    def test_duplicate_order_key_rejected(self):
        self.con.execute("INSERT INTO orders VALUES('o','a','2026-01-01T00:00:00',100,'paid')")
        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("INSERT INTO orders VALUES('o','a','2026-01-01T00:00:00',100,'paid')")

        with self.assertRaises(sqlite3.IntegrityError):
            self.con.execute("INSERT INTO orders VALUES('fractional','a','2026-01-01T00:00:00',10.5,'paid')")

    def test_overrefund_stops(self):
        self.con.execute("INSERT INTO orders VALUES('o','a','2026-01-01T00:00:00',100,'paid')")
        self.con.execute("INSERT INTO refunds VALUES('r','o','2026-01-02T00:00:00',101)")
        with self.assertRaises(DataQualityError):validate_sources(self.con,self.config)

    def test_malformed_timestamp_stops(self):
        self.con.execute("UPDATE assignments SET assigned_at='yesterday' WHERE user_id='a'")
        with self.assertRaises(DataQualityError):validate_sources(self.con,self.config)

    def test_postextract_order_stops(self):
        self.con.execute("INSERT INTO orders VALUES('o','a','2026-03-07T00:00:00',100,'paid')")
        with self.assertRaises(DataQualityError):validate_sources(self.con,self.config)


class StatisticalTests(unittest.TestCase):
    def test_wilson_known_reference(self):
        lo,hi=wilson(50,100)
        self.assertAlmostEqual(lo,.40383153,places=7)
        self.assertAlmostEqual(hi,.59616847,places=7)

    def test_zero_events_are_handled_without_relative_division(self):
        effect=binary_effect(0,100,0,100)
        self.assertIsNone(effect['relative_change'])
        self.assertLess(effect['ci95'][0],0)
        self.assertGreater(effect['ci95'][1],0)

    def test_arm_swap_reverses_absolute_interval(self):
        a=binary_effect(100,1000,130,1200);b=binary_effect(130,1200,100,1000)
        self.assertAlmostEqual(a['difference'],-b['difference'])
        self.assertAlmostEqual(a['ci95'][0],-b['ci95'][1])

    def test_balanced_and_extreme_allocations(self):
        self.assertEqual(sample_ratio_test(100,100)['p_value'],1)
        self.assertLess(sample_ratio_test(190,10)['p_value'],.001)
        self.assertEqual(sample_ratio_test(150,50,.25)['p_value'],1)

    def test_bootstrap_includes_partial_batch_and_is_reproducible(self):
        control=np.array([[0.,0.],[0.,0.],[9.,8.]])
        treatment=np.array([[0.,0.],[3.,2.],[9.,8.]])
        r0,d0=bootstrap_revenue(control,treatment,replicates=137,seed=19)
        r1,d1=bootstrap_revenue(control,treatment,replicates=137,seed=19)
        self.assertEqual(d0.shape,(137,2));np.testing.assert_array_equal(d0,d1)
        self.assertEqual(r0,r1)

    def test_constant_revenue_bootstrap(self):
        results,_=bootstrap_revenue(np.ones((7,2))*2,np.ones((8,2))*3,100)
        self.assertEqual(results['net']['ci95'],[1.,1.])

    def test_decision_changes_with_evidence(self):
        self.assertEqual(decide([.001,.01],[-.1,.2],[-.001,.002],.25,.003)['status'],'LAUNCH CANDIDATE')
        self.assertEqual(decide([-.001,.01],[-.1,.2],[-.001,.002],.25,.003)['status'],'CONTINUE TESTING — CONDITIONAL ON FEASIBILITY')
        self.assertEqual(decide([.001,.01],[-.7,-.3],[-.001,.002],.25,.003)['status'],'REJECT OR REDESIGN')
        self.assertEqual(decide([.001,.01],[-.1,.2],[.004,.008],.25,.003)['status'],'REJECT OR REDESIGN')

    def test_unsafe_effect_has_no_finite_safety_sample_size(self):
        self.assertIsNone(safety_sample_size(100,-.1))
        self.assertIsNone(safety_sample_size(100,0))

    def test_planning_power_matches_target_at_required_n(self):
        n=safety_sample_size(5000,.25,.8)
        self.assertAlmostEqual(safety_power(n,5000,.25),.8,places=5)

    def test_decomposition_reconciles_and_is_antisymmetric(self):
        a=[.1,1.,100.];b=[.12,1.1,80.]
        contributions=revenue_decomposition(a,b)
        self.assertAlmostEqual(sum(contributions),.12*1.1*80-10)
        np.testing.assert_allclose(contributions,-np.array(revenue_decomposition(b,a)),atol=1e-12)


if __name__=='__main__':unittest.main()

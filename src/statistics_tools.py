"""Inference and planning helpers, independent of project data and file paths."""
import math
from itertools import permutations
from statistics import NormalDist
import numpy as np

NORMAL = NormalDist()


def wilson(successes, n, confidence=0.95):
    if n <= 0 or not 0 <= successes <= n:
        raise ValueError('Need 0 <= successes <= n and n > 0')
    z = NORMAL.inv_cdf((1 + confidence) / 2)
    p = successes / n
    den = 1 + z*z/n
    mid = (p + z*z/(2*n)) / den
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n)) / den
    return [max(0.0, mid-half), min(1.0, mid+half)]


def binary_effect(x0, n0, x1, n1, confidence=0.95):
    """Newcombe method 10 absolute interval; log-RR interval when estimable."""
    l0, u0 = wilson(x0, n0, confidence)
    l1, u1 = wilson(x1, n1, confidence)
    p0, p1 = x0/n0, x1/n1
    d = p1-p0
    ci = [d-math.sqrt((p1-l1)**2+(u0-p0)**2),
          d+math.sqrt((u1-p1)**2+(p0-l0)**2)]
    result = {'control': p0, 'new': p1, 'difference': d, 'ci95': ci,
              'relative_change': None, 'relative_ci95': None}
    if x0 > 0 and x1 > 0:
        z = NORMAL.inv_cdf((1+confidence)/2)
        rr = p1/p0
        se = math.sqrt(1/x1-1/n1+1/x0-1/n0)
        result.update(relative_change=rr-1,
                      relative_ci95=[math.exp(math.log(rr)-z*se)-1,
                                     math.exp(math.log(rr)+z*se)-1])
    return result


def sample_ratio_test(control, treatment, expected_treatment_share=0.5):
    if control <= 0 or treatment <= 0 or not 0 < expected_treatment_share < 1:
        raise ValueError('Both arms and allocation probabilities must be positive')
    total = control+treatment
    expected = [total*(1-expected_treatment_share), total*expected_treatment_share]
    chi = sum((obs-exp)**2/exp for obs, exp in zip([control,treatment], expected))
    return {'chi_square': chi, 'p_value': math.erfc(math.sqrt(chi/2)),
            'expected_control': expected[0], 'expected_new': expected[1],
            'observed_new_share': treatment/total}


def bootstrap_revenue(control, treatment, replicates=10000, seed=271828):
    """Inputs: n-by-2 USD matrices, columns gross and after-refund revenue.

    Resample independent users within each arm. Both outcomes use identical
    user indices. Batches bound memory; the final partial batch is retained.
    """
    if replicates < 100:
        raise ValueError('At least 100 replicates required')
    rng = np.random.default_rng(seed)
    draws = np.empty((replicates,2))
    for start in range(0,replicates,100):
        size = min(100,replicates-start)
        # Generate indexes in the same arm order as version 1.
        idx0 = rng.integers(0,len(control),size=(size,len(control)))
        means0 = np.column_stack([control[:,i][idx0].mean(axis=1) for i in range(2)])
        idx1 = rng.integers(0,len(treatment),size=(size,len(treatment)))
        means1 = np.column_stack([treatment[:,i][idx1].mean(axis=1) for i in range(2)])
        draws[start:start+size] = means1-means0
    results = {}
    for i,key in enumerate(['gross','net']):
        analytic_se = math.sqrt(np.var(control[:,i],ddof=1)/len(control) +
                                np.var(treatment[:,i],ddof=1)/len(treatment))
        difference = float(treatment[:,i].mean()-control[:,i].mean())
        results[key] = {'difference': difference,
                        'ci95': np.quantile(draws[:,i],[.025,.975]).tolist(),
                        'bootstrap_se': float(np.std(draws[:,i],ddof=1)),
                        'analytic_se': analytic_se,
                        'normal_ci95_sensitivity': [difference-1.959963984540054*analytic_se,
                                                   difference+1.959963984540054*analytic_se]}
    return results, draws


def decide(conversion_ci, net_ci, refund_ci, loss_margin, refund_margin):
    """Evidence classification, distinct from the feasibility/business decision."""
    gates = {
        'conversion_superiority': conversion_ci[0] > 0,
        'net_revenue_safety': net_ci[0] > -loss_margin,
        'refund_safety': refund_ci[1] < refund_margin,
    }
    if all(gates.values()):
        status = 'LAUNCH CANDIDATE'
    elif conversion_ci[1] <= 0 or net_ci[1] < -loss_margin or refund_ci[0] > refund_margin:
        status = 'REJECT OR REDESIGN'
    else:
        status = 'CONTINUE TESTING — CONDITIONAL ON FEASIBILITY'
    return {'status':status,'gates':gates}


def conversion_sample_size(p0, effect, power=.8):
    p1 = p0+effect
    if effect <= 0 or not 0 < p0 < p1 < 1:
        raise ValueError('Need positive effect and risks strictly between zero and one')
    za, zb = NORMAL.inv_cdf(.975), NORMAL.inv_cdf(power)
    pooled = (p0+p1)/2
    return math.ceil((za*math.sqrt(2*pooled*(1-pooled)) +
                      zb*math.sqrt(p0*(1-p0)+p1*(1-p1)))**2/effect**2)


def safety_sample_size(variance_sum, distance_to_boundary, power=.8):
    """First-order normal planning, one-sided alpha .025 (95% CI boundary).

    No finite sample attains target power when the assumed true effect is on
    the unsafe side. This is approximate marginal power, not joint power.
    """
    if distance_to_boundary <= 0:
        return None
    return math.ceil((NORMAL.inv_cdf(.975)+NORMAL.inv_cdf(power))**2 *
                     variance_sum / distance_to_boundary**2)


def safety_power(n_per_arm, variance_sum, distance_to_boundary):
    return NORMAL.cdf(distance_to_boundary / math.sqrt(variance_sum/n_per_arm)
                      - NORMAL.inv_cdf(.975))


def revenue_decomposition(control_factors, treatment_factors):
    """Symmetric arithmetic decomposition of conversion * orders/buyer * AOV.

    Average the six replacement orders (three-factor Shapley decomposition).
    This is an accounting identity, not causal mediation or subgroup inference.
    """
    contributions = np.zeros(3)
    for order in permutations(range(3)):
        values = list(control_factors)
        for index in order:
            before = math.prod(values)
            values[index] = treatment_factors[index]
            contributions[index] += (math.prod(values)-before)/6
    return contributions.tolist()

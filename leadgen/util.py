import math
from datetime import datetime, timedelta

FMT = "%Y-%m-%dT%H:%M:%S"


def fmt(dt):
    return dt.strftime(FMT)


def parse(s):
    return datetime.strptime(s, FMT)


def sigmoid(x):
    return 1.0 / (1.0 + math.exp(-x))


def poisson(r, lam):
    """Knuth Poisson sampler driven by a seeded random.Random."""
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, int(r.gauss(lam, lam ** 0.5) + 0.5))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= r.random()
        if p <= limit:
            return k
        k += 1


def rand_time(r, a, b):
    """Uniform datetime in [a, b), second resolution."""
    return a + timedelta(seconds=int(r.uniform(0, (b - a).total_seconds())))


def gumbel(r):
    return -math.log(-math.log(max(r.random(), 1e-12)))

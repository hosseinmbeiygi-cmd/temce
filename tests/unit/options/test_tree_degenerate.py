"""P0-4: tree pricing never raises and never returns NaN/inf (incl. degenerate)."""
import math

from domain.options.tree_pricing import (
    OptionStyle,
    TreeOptionParams,
    TreeType,
    binomial_tree_price,
    trinomial_tree_price,
)


def test_tree_fuzz_finite_no_raise():
    bad = []
    for S in (0.0, 1e-9, 100.0):
        for K in (0.0, 90.0):
            for T in (0.0, 1e-9, 0.5):
                for sig in (0.0, 1e-9, 0.3):
                    for style in (OptionStyle.EUROPEAN, OptionStyle.AMERICAN):
                        for ttype, fn in (
                            (TreeType.BINOMIAL, binomial_tree_price),
                            (TreeType.TRINOMIAL, trinomial_tree_price),
                        ):
                            r = fn(
                                TreeOptionParams(
                                    S=S, K=K, T=T, r=0.05, sigma=sig,
                                    option_type="call", style=style,
                                    N=10, tree_type=ttype,
                                )
                            )
                            for v in (r.price, r.delta, r.gamma, r.theta, r.vega):
                                if not math.isfinite(float(v)):
                                    bad.append((S, K, T, sig, style.value, ttype.value, v))
    assert not bad, f"non-finite tree outputs: {bad[:5]}"


def test_tree_expired_returns_intrinsic():
    r = binomial_tree_price(
        TreeOptionParams(S=100.0, K=90.0, T=0.0, r=0.05, sigma=0.3, N=10)
    )
    assert r.price == 10.0

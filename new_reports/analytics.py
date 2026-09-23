"""Technical indicators, backtest, ML, financial ratios per spec 2.x. Pure stdlib + optional sklearn."""
import math
import statistics as st

UNK = 'نامشخص'

# ---------- 2.1 indicators (daily OHLC rows sorted ascending) ----------

def sma(vals, n):
    if len(vals) < n:
        return None
    return sum(vals[-n:]) / n

def ema_series(vals, n):
    if not vals:
        return []
    k = 2.0 / (n + 1)
    out = [vals[0]]
    for v in vals[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out

def rsi_wilder(closes, n=14):
    if len(closes) < n + 1:
        return None
    gains, losses = [], []
    for i in range(1, len(closes)):
        d = closes[i] - closes[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag = sum(gains[:n]) / n
    al = sum(losses[:n]) / n
    for i in range(n, len(gains)):
        ag = (ag * (n - 1) + gains[i]) / n
        al = (al * (n - 1) + losses[i]) / n
    if al == 0:
        return 100.0 if ag > 0 else None
    rs = ag / al
    return 100 - 100 / (1 + rs)

def macd(closes):
    if len(closes) < 26:
        return None, None, None
    e12 = ema_series(closes, 12)
    e26 = ema_series(closes, 26)
    line = [a - b for a, b in zip(e12, e26, strict=False)]
    sig = ema_series(line, 9)
    return line[-1], sig[-1], line[-1] - sig[-1]

def bollinger(closes, n=20, k=2):
    if len(closes) < n:
        return None, None, None, None
    window = closes[-n:]
    m = sum(window) / n
    sd = st.pstdev(window)
    upper, lower = m + k * sd, m - k * sd
    pctb = (closes[-1] - lower) / (upper - lower) if upper != lower else None
    return upper, m, lower, pctb

def atr_wilder(rows, n=14):
    if len(rows) < n + 1:
        return None
    trs = []
    for i in range(1, len(rows)):
        h, l = float(rows[i]['high']), float(rows[i]['low'])
        pc = float(rows[i - 1]['close'])
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    atr = sum(trs[:n]) / n
    for tr in trs[n:]:
        atr = (atr * (n - 1) + tr) / n
    return atr

def tech_snapshot(rows):
    """rows: daily OHLC dicts ascending. Returns indicator dict or None."""
    closes = [float(r['close']) for r in rows]
    if len(closes) < 20:
        return None
    s20, s50 = sma(closes, 20), sma(closes, 50)
    rsi = rsi_wilder(closes)
    m, s, h = macd(closes)
    bb_u, bb_m, bb_l, pb = bollinger(closes)
    atr = atr_wilder(rows)
    last20 = rows[-20:]
    support = min(float(r['low']) for r in last20)
    resist = max(float(r['high']) for r in last20)
    hi = max(rows, key=lambda r: float(r['high']))
    lo = min(rows, key=lambda r: float(r['low']))
    def ret(n):
        return (closes[-1] / closes[-1 - n] - 1) * 100 if len(closes) > n else None
    return {
        'close': closes[-1], 'date': rows[-1]['date'],
        'chg_day': (closes[-1] / closes[-2] - 1) * 100 if len(closes) > 1 else None,
        'sma20': s20, 'sma50': s50, 'rsi14': rsi,
        'macd': m, 'macd_sig': s, 'macd_hist': h,
        'bb_upper': bb_u, 'bb_mid': bb_m, 'bb_lower': bb_l, 'pctb': pb,
        'atr14': atr, 'support20': support, 'resist20': resist,
        'hist_high': float(hi['high']), 'hist_high_date': hi['date'],
        'hist_low': float(lo['low']), 'hist_low_date': lo['date'],
        'ret5': ret(5), 'ret21': ret(21), 'ret63': ret(63),
    }

# ---------- 2.5 backtest (SMA20/50 cross, 0.5% commission each side, no look-ahead) ----------

def backtest(rows, commission=0.005):
    closes = [float(r['close']) for r in rows]
    if len(closes) < 80:
        return None
    # signals use SMA computed up to and including day t; trade executes at close of t (same info).
    sig = []
    for t in range(len(closes)):
        if t < 50:
            sig.append(0)
            continue
        s20 = sum(closes[t - 19:t + 1]) / 20
        s50 = sum(closes[t - 49:t + 1]) / 50
        sig.append(1 if s20 > s50 else 0)
    # position from signal of day t applied to return t->t+1 (close-to-close, executes at next close)
    trades = []
    pos = 0
    entry = None
    daily = []  # strategy daily returns
    for t in range(50, len(closes) - 1):
        want = sig[t]
        r = closes[t + 1] / closes[t] - 1
        if want and not pos:
            pos = 1
            entry = closes[t + 1] * (1 + commission)
        elif not want and pos:
            pos = 0
            exit_ = closes[t + 1] * (1 - commission)
            trades.append(exit_ / entry - 1)
            entry = None
        daily.append(r if pos else 0.0)
    if pos and entry:
        exit_ = closes[-1] * (1 - commission)
        trades.append(exit_ / entry - 1)
    n_days = len(closes) - 50
    total = (closes[-1] / closes[50] - 1) * 100
    wins = [x for x in trades if x > 0]
    losses = [x for x in trades if x <= 0]
    pf = (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else (None if not wins else UNK)
    # equity curve of strategy
    eq = 1.0
    peak = 1.0
    mdd = 0.0
    for r in daily:
        eq *= (1 + r)
        peak = max(peak, eq)
        mdd = max(mdd, (peak - eq) / peak)
    strat_total = (eq - 1) * 100
    mean_r = st.mean(daily) if daily else 0
    sd_r = st.pstdev(daily) if len(daily) > 1 else 0
    sharpe = (mean_r - 0.30 / 252) / sd_r * math.sqrt(252) if sd_r > 0 else None
    years = n_days / 365
    cagr = ((eq) ** (1 / years) - 1) * 100 if years > 0 and eq > 0 else None
    bh_eq = closes[-1] / closes[50]
    bh_mdd = 0.0
    p = closes[50]
    for c in closes[50:]:
        p = max(p, c)
        bh_mdd = max(bh_mdd, (p - c) / p)
    return {
        'n_trades': len(trades), 'win_rate': len(wins) / len(trades) * 100 if trades else None,
        'profit_factor': pf if isinstance(pf, float) else None,
        'total_ret': strat_total, 'cagr': cagr, 'max_dd': mdd * 100, 'sharpe': sharpe,
        'buyhold_ret': (bh_eq - 1) * 100, 'buyhold_mdd': bh_mdd * 100,
        'commission': commission * 100, 'start_date': rows[50]['date'], 'end_date': rows[-1]['date'],
    }

def backtest_split(rows):
    """70% in-sample / 30% out-of-sample."""
    cut = int(len(rows) * 0.7)
    if cut < 80 or len(rows) - cut < 80:
        return None
    return backtest(rows[:cut]), backtest(rows[cut:])

# ---------- 2.6 ML (5-day >=2% up), temporal split, two models ----------

def ml_dataset(rows, max_samples=600):
    closes = [float(r['close']) for r in rows]
    vols = [float(r.get('volume', 0) or 0) for r in rows]
    n = len(closes)
    if n < 150:
        return None
    start = max(60, n - max_samples - 5)  # ponytail: ML on the most recent ~600 bars for tractability; full-history via vectorization upgrade
    feats = []
    labels = []
    for t in range(start, n - 5):
        c = closes[:t + 1]
        r1 = (c[-1] / c[-2] - 1) * 100
        r5 = (c[-1] / c[-6] - 1) * 100 if len(c) > 6 else 0
        r10 = (c[-1] / c[-11] - 1) * 100 if len(c) > 11 else 0
        r20 = (c[-1] / c[-21] - 1) * 100 if len(c) > 21 else 0
        rs = rsi_wilder(c)
        m, s, h = macd(c)
        s20 = sma(c, 20)
        s50v = sma(c, 50)
        d20 = (c[-1] / s20 - 1) * 100 if s20 else None
        d50 = (c[-1] / s50v - 1) * 100 if s50v else None
        atr = atr_wilder(rows[:t + 1])
        vwin = [v for v in vols[t - 19:t + 1] if v > 0]
        vavg = sum(vwin) / len(vwin) if vwin else 0.0
        vratio = vols[t] / vavg if vavg else 0.0
        bb_u, bb_m, bb_l, pb = bollinger(c)
        row = [r1, r5, r10, r20, rs, h, d20, d50, atr, vratio, pb]
        if any(x is None or (isinstance(x, float) and (math.isnan(x) or math.isinf(x))) for x in row):
            continue
        label = 1 if closes[t + 5] / closes[t] - 1 >= 0.02 else 0
        feats.append(row)
        labels.append(label)
    return feats, labels

def ml_run(rows):
    ds = ml_dataset(rows)
    if not ds:
        return None
    X, y = ds
    X, keep = drop_const_cols(X)
    n = len(X)
    if n < 60:
        return None
    FEATURE_NAMES = ['بازده ۱روزه', 'بازده ۵روزه', 'بازده ۱۰روزه', 'بازده ۲۰روزه', 'RSI(14)', 'MACD Histogram',
                     'فاصله% از SMA20', 'فاصله% از SMA50', 'ATR(14)', 'نسبت حجم به میانگین ۲۰روزه', '%B']
    names = [FEATURE_NAMES[j] for j in keep]
    n_train = int(n * 0.70)
    n_val = int(n * 0.15)
    Xtr, Xva, Xte = X[:n_train], X[n_train:n_train + n_val], X[n_train + n_val:]
    ytr, yva, yte = y[:n_train], y[n_train:n_train + n_val], y[n_train + n_val:]
    if len(set(ytr)) < 2 or len(set(yte)) < 2:
        return None
    # standardize on train stats
    cols = list(zip(*Xtr, strict=False))
    mu = [st.mean(c) for c in cols]
    sd = [st.pstdev(c) or 1.0 for c in cols]
    def std(part):
        return [[(v - m) / s for v, m, s in zip(row, mu, sd, strict=False)] for row in part]
    Xtr, Xva, Xte = std(Xtr), std(Xva), std(Xte)
    res = {'n': n, 'train': len(Xtr), 'val': len(Xva), 'test': len(Xte),
           'balance': sum(y) / len(y) * 100, 'models': {}, 'names': names}
    baseline = max(set(yte), key=yte.count)
    res['baseline_acc'] = sum(1 for v in yte if v == baseline) / len(yte) * 100
    for name, pred_fn in [('logreg', logreg), ('gboost', gb_stump)]:
        try:
            pred, prob, imp = pred_fn(Xtr, ytr, Xva, yva, Xte)
            acc = sum(1 for p, t in zip(pred, yte, strict=False) if p == t) / len(yte) * 100
            tp = sum(1 for p, t in zip(pred, yte, strict=False) if p == 1 and t == 1)
            fp = sum(1 for p, t in zip(pred, yte, strict=False) if p == 1 and t == 0)
            fn = sum(1 for p, t in zip(pred, yte, strict=False) if p == 0 and t == 1)
            prec = tp / (tp + fp) * 100 if tp + fp else None
            rec = tp / (tp + fn) * 100 if tp + fn else None
            f1 = 2 * prec * rec / (prec + rec) if prec and rec else None
            auc = auc_score(prob, yte)
            res['models'][name] = {'acc': acc, 'prec': prec, 'rec': rec, 'f1': f1, 'auc': auc, 'imp': imp}
        except Exception:
            res['models'][name] = None
    return res

def nfeatures_const(X):
    # drop constant columns instead of rejecting the whole dataset (volume absent in price history)
    cols = list(zip(*X, strict=False))
    return any(st.pstdev(c) == 0 for c in cols)

def drop_const_cols(X):
    cols = list(zip(*X, strict=False))
    keep = [j for j, c in enumerate(cols) if st.pstdev(c) > 0]
    return [[row[j] for j in keep] for row in X], keep

# --- logistic regression (batch GD, L2) ---
def logreg(Xtr, ytr, Xva, yva, Xte):
    import random
    random.seed(42)
    d = len(Xtr[0])
    w = [0.0] * d
    b = 0.0
    lr, l2, iters = 0.05, 0.01, 120
    for _ in range(iters):
        gw = [0.0] * d
        gb = 0.0
        for xi, yi in zip(Xtr, ytr, strict=False):
            z = sum(wj * xj for wj, xj in zip(w, xi, strict=False)) + b
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            e = p - yi
            for j in range(d):
                gw[j] += e * xi[j]
            gb += e
        for j in range(d):
            w[j] -= lr * (gw[j] / len(Xtr) + l2 * w[j])
        b -= lr * gb / len(Xtr)
    def prob(row):
        z = sum(wj * xj for wj, xj in zip(w, row, strict=False)) + b
        return 1 / (1 + math.exp(-max(-30, min(30, z))))
    pred = [1 if prob(r) >= 0.5 else 0 for r in Xte]
    return pred, [prob(r) for r in Xte], None

# --- gradient boosting on stumps (depth-1 trees, subsample features) ---
def gb_stump(Xtr, ytr, Xva, yva, Xte, rounds=30, lr=0.1):
    import random
    random.seed(7)
    n, d = len(Xtr), len(Xtr[0])
    f0 = st.mean(ytr)
    F = [f0] * n
    stumps = []
    for _ in range(rounds):
        resid = [yi - 1 / (1 + math.exp(-max(-30, min(30, fi)))) for yi, fi in zip(ytr, F, strict=False)]
        best = None
        feats = random.sample(range(d), min(d, 6))
        for j in feats:
            vals = sorted(set(row[j] for row in Xtr))
            for v in vals:
                lm = [r for row, r in zip(Xtr, resid, strict=False) if row[j] <= v]
                rm = [r for row, r in zip(Xtr, resid, strict=False) if row[j] > v]
                if not lm or not rm:
                    continue
                gl, gr = st.mean(lm), st.mean(rm)
                gain = sum((r - gl) ** 2 for r in lm) + sum((r - gr) ** 2 for r in rm)
                if best is None or gain < best[0]:
                    best = (gain, j, v, gl, gr)
        if best is None:
            break
        _, j, v, gl, gr = best
        stumps.append((j, v, gl, gr))
        F = [fi + lr * (gl if row[j] <= v else gr) for row, fi in zip(Xtr, F, strict=False)]
    def prob(row):
        f = f0
        for j, v, gl, gr in stumps:
            f += lr * (gl if row[j] <= v else gr)
        return 1 / (1 + math.exp(-max(-30, min(30, f))))
    pred = [1 if prob(r) >= 0.5 else 0 for r in Xte]
    # feature importance = stump usage counts
    from collections import Counter
    cnt = Counter(j for j, *_ in stumps)
    imp = [(j, cnt[j] / len(stumps) * 100 if stumps else 0) for j in range(d)]
    imp.sort(key=lambda x: -x[1])
    return pred, [prob(r) for r in Xte], imp[:5]

def auc_score(probs, yte):
    pairs = sorted(zip(probs, yte, strict=False))
    # rank-based AUC
    ranks = {}
    i = 0
    uniq = {}
    for p, t in pairs:
        uniq.setdefault(p, []).append(t)
    r = 1
    rank_sum_pos = 0
    n_pos = sum(yte)
    n_neg = len(yte) - n_pos
    if not n_pos or not n_neg:
        return None
    for _p, ts in sorted(uniq.items()):
        k = len(ts)
        avg_rank = r + (k - 1) / 2
        if ts[0] == 1 or 1 in ts:
            rank_sum_pos += avg_rank * sum(ts)
        r += k
    return (rank_sum_pos - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)

# ---------- 2.7 risk ----------
def risk_metrics(closes):
    rets = [(closes[i] / closes[i - 1] - 1) for i in range(1, len(closes))]
    if len(rets) < 2:
        return None
    sd_annual = st.pstdev(rets) * math.sqrt(252) * 100
    peak = closes[0]
    mdd = 0.0
    for c in closes:
        peak = max(peak, c)
        mdd = max(mdd, (peak - c) / peak)
    return {'vol_annual': sd_annual, 'max_dd': mdd * 100}

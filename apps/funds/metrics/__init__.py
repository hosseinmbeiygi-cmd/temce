"""Metrics Engine صندوق‌یار — محاسبه ۵۶ شاخص در ۵ لایه.

لایه ۱ — پایه (۸): TWR 1/3/6/12/36/Inception, P/NAV, AUM, Volume, Spread
لایه ۲ — ریسک-بازده (۸): Sharpe, Sortino, Calmar, MDD+Recovery, Beta, σ, IR, UCR/DCR
لایه ۳ — مدیریت (۱۰): ActiveShare, BootstrapAlpha, StyleDrift, TER, PerfFee, HHI,
                   Turnover, CashDrag, WindowDressing, TrackingDifference
لایه ۴ — رفتاری (۱۲): BehaviorGap, Survivorship, LiquiditySpiral, HiddenLeverage,
                   BenchmarkGaming, Persistence, MarketTiming, FlowPerf,
                   RedemptionPressure, DiseconomiesOfScale, Tenure+PostChangeAlpha,
                   FundFamilyCorr
لایه ۵ — ایران (۱۸): FX_beta_nima, FX_beta_azad, InflationBeta, RealReturn,
                   GeopoliticalSens, Cal_Esfand, Cal_Khordad, Cal_Ramadan,
                   InterbankRateBeta, Duration, GoldWorldCorr, SilverWorldCorr,
                   SaffronCorr, PeerCorrelation, PnavPeerPercentile,
                   LiquidityScore, OrderBookDepth + (FX_beta_total = 1 of 18)

Cold Start: اگر سابقه کمتر از آستانه باشد → None + label.
Scoring Engine تصمیم می‌گیرد چگونه برخورد کند.
"""

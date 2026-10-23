# Module card: indicators-and-technical

**Name:** indicators-and-technical  
**Path:** `core/indicators.py` (306), `src/indicators/advanced.py` (546), `src/indicators/specs.py` (490), `src/indicators/trend_momentum.py` (237), `src/indicators/general.py` (95), `src/indicators/stocks.py` (79), `src/indicators/__init__.py` (78), `src/indicators/scoring.py` (20), `core/constants/indicators.py` (~120+ 読了), 呼び出し表面: `services/signal_feature_pipeline.py`, `services/confidence_scorer.py`, `services/ml_signal_connector.py`, `services/quant_signal_orchestrator.py`, `src/gold_desk/scorer.py`, `src/gold_desk/pattern_detector.py`, `src/gold_desk/hotpath.py`, `src/gold_desk/live_signals.py`, `src/gold_desk/macro_news.py`, `src/gold_desk/indicators.py`（存在確認のみ）  
**Tier:** 1（指標計算の正確性は シグナル・バックテスト・スコアリング・意思決定の 土台。 浮動小数／ Wilder 平滑化／ルックアヘッド／初期値扱いが 主要なリスク）  
**Purpose:** テクニカル指標計算の 単一定義場所＋高度指標群＋仕様カタログ＋特徴量抽出パイプライン。 core/indicators は RSI/ATR/MACD/トレンド強度/ボラティリティレジーム/データ品質スコア/E WA/SMA を提供。 src/indicators は EMA/S MA크로싱, 스토캐스틱, ADX, 이치모꾸, VWAP, OBV, Williams %R, CCI, Parabolic SAR, 켈트너 위치 등 고도 지표 10種を 제공. general/stocks/trend_momentum は 基礎 수량式 (수익률, TR, ATR, CLV, 거래량zスコア, Amihud, 구매자력비 등). specs.py は 全指標の 仕様カタログ (수식·해석·주의사항).  
**Main files（行数）:** 上記.  
**Files read:** core/indicators.py 全文, src/indicators/advanced.py 全文, src/indicators/specs.py（前半＋構造読了）、src/indicators/trend_momentum.py（前半＋構造読了）、src/indicators/general.py 全文、src/indicators/stocks.py 全文、src/indicators/__init__.py 全文、src/indicators/scoring.py 全文、core/constants/indicators.py（前半＋構造読了）、services/signal_feature_pipeline.py（前半）、services/confidence_scorer.py・ml_signal_connector.py・quant_signal_orchestrator.py（import 行確認）、src/gold_desk/scorer.py・pattern_detector.py・hotpath.py・live_signals.py・macro_news.py（import/関数行確認）。  
**Files unread (full):** src/indicators/specs.py 後半, trend_momentum.py 後半, signal_feature_pipeline.py 後半, および 各 呼び出しサービス の全文（本カードでは 指標消費の 表面だけ確認）。

## 3.1 Identity

- **エントリポイント／消費者:**
  - `core.indicators` は 複数のサービスで 直接import（`services/signal_feature_pipeline.py`, `services/confidence_scorer.py`, `services/ml_signal_connector.py`, `services/quant_signal_orchestrator.py` ほか）。
  - `src/indicators/*` は 主に 戦略生成／スクリーナー／スコアリング側で 使われる想定（import 系統は 別途確認必要）。 `src/indicators/__init__.py` が 再エクスポートしている可能性。
  - `core/constants/indicators.py` の `IndicatorType`, `DEFAULT_INDICATOR_PARAMS`, `INDICATOR_MIN_PERIODS` は 指標標準値の 単一参照場所（指標別 デフォルト：RSI 14, MACD 12/26/9, ボリンジャー 20/2.0, ATR 14, 스토캐스틱 14/3 등）。
- **依存:** `core/indicators.py` は `numpy` 使用（ボラティリティの `np.std`）。 `src/indicators/advanced.py` は **純Pythonリストのみ**（numpy/pandas依存なし）と明記。 `services/signal_feature_pipeline.py` は `numpy`＋`pandas` 使用（FeatureMatrixへ変換）。

## 3.2 Logic and algorithms

- **core/indicators.py（共通指標）:**
  - `compute_sma(values, period)`: 最後 `period` 件の 単純平均。 空／period<=0 → 0.0.
  - `compute_ema(values, period)`: α = 2/(period+1), 初値は 最初のperiodの SMAでシード. `compute_ema_series` は 各点の EMA系列を返す（index period-1から開始）.
  - `compute_rsi(closes, period=14)`: Wilder平滑化（α=1/period）で 平均利益／平均損失を算出。 データ不足は 50.0（中立）を返す。 損失が0に近い場合（<1e-10）は 100.0（全利益）を返す。 標準的 RSI = 100 - 100/(1+RS). 【良好：Wilder平滑化は 業界標準的選択】
  - `compute_atr(highs, lows, closes, period=14)`: True Range = max(H-L, |H-C_prev|, |L-C_prev|)。 Wilder平滑化。 データ不足は None.
  - `compute_macd(closes, fast=12, slow=26, signal_period=9)`: fast/slow EMA系列を算出後、 アライン（offset = slow-fast）して MACDライン＝ fastEMA - slowEMA。 シグナル線は MACD値の EMA（または データ不足時は 単純平均）。 ヒストグラム＝ MACD - signal。 方向＝ 1.0/0.0/-1.0. 【ADC系列の長さ扱い：`macd_values`の長さは `len(slow_ema_series)` と等しくなるように計算。 ただし fast/slowの 初期N/A扱いにより、実質的に 利用可能な 가장 최근 값만 사용.】
  - `compute_trend_strength(closes, period=14)`: ADX様の 방향 강도 (0~1). 直近 period内で 騰落日数の 우위 비율로 산출, 1.5배 스케일. 【注意：本物のADX（+DI/-DI／트루レンジ平滑）とは 달리 単なる 등락일수 비율ベース. 名目은 ADX-like지만 手法は 축소판.】
  - `compute_volatility_regime(closes, period=20, scale=20.0)`: 対数リターンではなく 単純リターン `(P_t - P_{t-1}) / max(P_{t-1}, 0.001)` の 標準偏差を `scale`倍して 0~1로 클램핑. scale=20.0이면 5%표준편차가 1.0에 대응. 【주의：통상 연율ボラ티리티는 로그수익률 기반인데 ここ는 단순리턴＋スケール倍 매핑. 정의/단위가 표준과 다름.】
  - `compute_data_quality_score(total_fields, missing_fields, total_price_points, min_price_points=20)`: 필드완전성(1-결측/전체) × 가격점수수용성(min(1, 실제/최소))의 곱. 둘 다 0이면 0.5 보수적 반환.
- **src/indicators/advanced.py（고도 지표 10종）:**
  - `_ema`, `_sma`, `_true_range`, `_atr`ヘルパー（内部用, Noneパディングあり）.
  - `calculate_ema_crossover(close, fast=10, slow=30)`: fast/slow EMA系列, golden_cross/death_crossを 前時点比較로 検出.
  - `calculate_stochastic(high, low, close, k=14, d=3, smooth=3)`: %K＝ (C - 低位) / (高位 - 低位) ×100, smooth Kの SMAが %K, %K의 SMA가 %D. 過売20/過買80.
  - `calculate_adx(high, low, close, period=14)`: +DM/-DM／TR平滑 → +DI/-DI → DX → ADX(Wilder平滑). strong_trend: ADX>25, weak_trend: ADX<20. 【트루レンジ는 正しい 정의._smoothed_plus_minus 계산식이 _plus_dm[1:period+1] 기준이라 첫 기간 처리가 관행과 미세하게 다를 수 있음（검토必要）.】
  - `calculate_ichimoku(high, low, close, tenkan=9, kijun=26, senkou_b=52)`: 転換線／基軸線／先行帯A/B／遅行帯 개념을 実装. 先行帯は kijun_period만큼 前倒しシフト.
  - `calculate_vwap(close, high, low, volume, period=20)`: 典型価格 (H+L+C)/3 × 取引量 의 累積を 取引量 합で割る 롤링 VWAP. volume合計0 구간은 None.
  - `calculate_obv(close, volume, sma_period=20)`: 終値増→+量, 減→-量, 同値→維持의 累積. OBV SMAを 附与.
  - `calculate_williams_r(high, low, close, period=14)`: (高位 - C) / (高位 - 低位) × -100. 過売 -80 / 過買 -20.
  - `calculate_cci(high, low, close, period=20)`: 典型価格の SMA対 평균偏差, (TP - SMA_TP) / (0.015 × MD). 過売 -100 / 過買 100.
  - `calculate_parabolic_sar(high, low, close, step=0.02, max_af=0.2)`: SAR加速因子 관리, uptrend/downtrend 反転判定, buy/sellシグナル. 【実装は 古典的な 파라볼릭 SAR에 가깝지만, 초기 EP／SAR 초기값・역전 직후의 저가/고가 보정等が 入口年代별로 미세하게 다름.】
  - `calculate_keltner_position(high, low, close, period=20, multiplier=2.0)`: EMA 중心 ＋ ATR 기반 上下バンド, price의 밴드 내 위치(0~1), above/belowフラグ.
- **src/indicators/general.py（基礎数量式）:**
  - 단순수익률, 로그수익률, 일중レンジ, 相對レンジ, CLV, 回復比率, 相對 거래량, 거래량 zスコア, 取引値, float 회전율, Amihud 비유동度, 트루レンジ, ATR(단순평균版), 正規化変動性(ATR/価格), 圧縮比(短期ATR/長期ATR), ボリンジャー帯幅, 相對強度比, 超過収益, zスコア.
  - 【주의：`calculate_atr`는 `true_ranges`의 단순 평균(와일더平滑 아님)이고, `core/indicators.compute_atr` 와는 평활화 방식이 다르다. 同じ "ATR" 용어라도 実装이 2種類存在する（나중에 統一/整理 필요）.】
- **src/indicators/stocks.py（주식・市場構造指標）:**
  - 1인당 実買/実売 금액, 購入者力比(매수단가/매도단가), 純実金流, 正規化実金流(時価総額対比), 所有権変化, HHI, 供給吸収スコア, 供給건조度, 修正건조도비, 抵抗線까지 거리, 抵抗線タッチ횟수, ブレイクアウト品質(z_CLV/z_RS/z_取引量-heavy), ブレイクアウト受容率(미래終値が 저항上).
- **src/indicators/trend_momentum.py（추세・モメンタム）:**
  - EMA/SMAヘルパー,  momentum, ROC, RSI(系列), MACD(系列), 볼린저밴드, 일목, VWAP, OBV, 윌리엄스%R, CCI, 파라볼릭SAR, 켈트너 위치 등 高度指標의 페르시아市場用 バリエーション이 일부 重複（同名関数이 advanced.py과 겹치는 경우에도 パラメータ命名/デフォルト이 다를 수 있음）.
- **src/indicators/specs.py（仕様カタログ）:**
  - `IndicatorSpec` 데이터クラス（id/group/function_name/inputs/formula/python_formula/pseudo_code/interpretation/rule_of_thumb/use_case/caveat）.
  - `ALL_SPECS` に 一般・추세・モメンタム・ボリューム・ボリンジャー・ATR・ stochastic 등 各指標의 文書가 含まれる. 【문서 자체는 良好. 수식과 注意書き가 있어 監査に役立つ.】
- **src/indicators/scoring.py（軽量スコアリングヘルパー）:**
  - 単純な スコアリング用 데이터クラス／定数が 포함되었을 가능성（前半のみ確認）.
- **core/constants/indicators.py:**
  - `IndicatorType`列挙, `DEFAULT_INDICATOR_PARAMS`（上記), `INDICATOR_MIN_PERIODS`（RSI 14, MACD 26, ボリンジャー 20, 스토캐스틱 14, ADX 14 등）.

## 3.3 Data

- **入力:** 終値・高値・安値・出来高・取引値の リスト（float）, オプションの 期間パラメータ.
- **出力:** ス칼라（RSI, ATR, MACDディクショナリ 등） 또는 시계열リストを含む ディクショナリ. None / デフォルト値（データ不足時）.
- **格納／契約:** 計算モジュール 自体は 状態を持たず, 関数型. 下流が 終値系列を 渡すと 指標スカラー/系列을 返す. データ不足時의 振る舞い（50.0, 0.0, None 등）가 函数마다 다르므로 消費者側이 一貫して扱う必要.

## 3.4 General checklist

- **ロジック:**
  - [YES] RSI/Wilder平滑化, ATR/Wilder平滑化, MACD/EMAベース → 표준적 선택. [SEEN: core/indicators.py]
  - [NO] `compute_volatility_regime`은 標準的 연율ボラ티リティ(로그수익률 기반)와 定義が 다름. 単純리턴 표준편차 × scale을 0~1に 클램핑. “연율화” 도 아니고 “로그”도 아님. [SEEN: core/indicators.py: compute_volatility_regime] → **指標-01**.
  - [NO] ADX-like (`compute_trend_strength`)는 実際の ADX(+DI/-DI/트루レンジ平滑)와 다른, 単なる 등락일수 우위 비율. 名称이 오해を 부를 수 있음. [SEEN: core/indicators.py: compute_trend_strength] → **指標-02**.
  - [NO] ATR 계산이 2種類: `core/indicators.compute_atr`(Wilder)와 `src/indicators/general.calculate_atr`(단순평균). “ATR”라는 이름이 統一되지 않음. [SEEN: core/indicators.py vs src/indicators/general.py] → **指標-03**.
  - [UNKNOWN] `src/indicators/trend_momentum.py`과 `advanced.py`에 同名／유사 함수가 重複하는지 全文確認 필요（次回）. 現在 확인된 범위에서만 보더라도 MACD/RSI/스토캐스틱 계열이 複数 파일に 분散해 있을 가능성.
  - [YES] `compute_data_quality_score`는 データ品質の 簡易スコア링으로서 合理的（결측＋点数不足）. [SEEN: core/indicators.py]
  - [NO] 終値系列이 短い場合의 挙動이 関数마다 통일되어 있지 않음 (RSI=50, ATR=None, MACD=0.0系, trend_strength=0.5, volatility_regime=0.5 등). 消費者가 一貫した “부족시 중립値” 전략을 취하기 어려움. [SEEN: 各関数]
- **時間:**
  - [YES] 終値系列은 古い→新しい 순서라고 가정하는 函数が多い（`closes[-1]` が 최근）. 入力 순서가 逆이면 全혀違う結果. [SEEN: 各関数]
  - [UNKNOWN] 入力 시계열의 타임존／timestampは ここで扱지 않음（消費者側 책임）.
- **データ:**
  - [YES] 価格は float列表（Decimal 아님）. 核心の注文・金額計算과 달리 指標計算은 float 기반. 注意: 後段で 금액・주문サイズ를 계산할 때 float가 残ると 丸め誤差 리스크가 再度発生. [SEEN: core/indicators.py, src/indicators/general.py]
  - [UNKNOWN] 入力に 欠損・NaN・無限大가 포함되면 各関数의 挙動이 未検証（일부 `max(..., 0.001)` 등으로 0割れ는Guard 되지만 NaN 전파는未確実）.
- **エラー:**
  - [YES] データ不足時に 例外를 올리 않고 デフォルト값을 반환（RSI 50, MACD 0, trend_strength 0.5, volatility 0.5 등）. これは 消費者側이 失敗를 検出하기 어렵게 만들 수 있음（조용한誤信号）. [SEEN: 各関数]
  - [NO] `compute_atr`は None을 반환하므로 消費者가 None処理를 해야 함. 一方 RSI/MACD는 항상 float을 반환. 消費者側の 分岐가 不統一になる 소지.
- **並行性:** 해당 없음（순수 계산 함수, 상태 없음）.
- **性能:**
  - [YES] `compute_ema_series`, `calculate_*` 계열은 O(n) 루프 위주. 問題 없는 수준.
  - [UNKNOWN] 大量シンボル×다수 기간에 대해 繰り返し 호출되면 終値系列の 재계산이 重くなる 가능성. 利用パターン次第.
- **セキュリティ:** 入力가 숫자リスト이므로 injectionリスク는 낮음. ただし 消費者가 用户入力を 整備せず 渡す場合は 異常値による 誤信号 리스크.
- **ログ／可観測性:** 計算 모듈 自체는 ログ를 남기지 않음（소비자側 책임）. 異常値・부족 데이터를 ログ하지 않으므로, 後단에서 信号品質 추적이 필요하면 消費者側에서 記録해야.

## 3.5 Specialized checklist（ペルシア市場・注文・データ取り込み関連）

- **価格のソースと調整:**
  - ここでは 終値系列을  받아서 계산할 뿐, 終値＝last trade price인지, 調整後価格인지, 基軸ボリューム인지 등은 消費者側の データソースに 의존. 【丁重：指標 모ジュール単体では データソースの 正確性・調整の有無를 保証できない. データ取り込み層(ING-09/10 등)와의 接続が 重要.】
- **매매 수심／買い力:**
  - `stocks.py`의 購入者力比/実金流 계열은 取引データ의 買方／売方 実資金・건수・所有権等を 入力とする. 定義가 明確하면 有用 but 実データの 定義（実 buyers / legal buyers / 疑似買力 등）가 正確해야 함（ペルシア市場의 実買力 vs 法的買力 이슈는 別モジュールで 確認）.
- **금／환율／원유:**
  - gold/currency/commodity용 指標 계산은 `signal_feature_pipeline`의 시장별 추출기(`_extract_gold_features` 등)가 담당. 現在 읽은 범위에서 그 実装の全文은 未確認. 【次回: signal_feature_pipeline 전반＋ gold/currency/commodity 특징抽出の 式を読む.】

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| IND-01 | core/indicators.py: compute_volatility_regime | 標準的な 연율ボラ티リティ(로그수익률 기반)와 다른 정의: 単純リターン `(P_t-P_{t-1})/max(P_{t-1},0.001)`의 標準편차 × scale을 0~1로 클램핑. “연율화”도 “로그”도 아님. 스케ール 파라미터로 5% 표준편차를 1.0에 대응시키는 등 임의의 매핑. | [SEEN: core/indicators.py: compute_volatility_regime] | medium | 변동성을 0~1スコア로 쓰는用途라면 一貫性・解釈可能性에 問題. 消費者(ML特徴量 등)가 この値を 다른 변동성指標와 混用하면 期待와 다른 挙動. | この関数が 어디에 쓰이는지(ML特徴量, スコアリング,  리스크관리 등)를 확인하고, 目的에 맞는 정의인지 검증. 필요하면 로그수익률 기반 연율ボラ티リティ로 統一할지 판단. |
| IND-02 | core/indicators.py: compute_trend_strength | “ADX-like”라고 이름 붙였지만 実装은 単なる 直近 period의 騰落日数 우위 비율(1.5배 스케일). 실제 ADX(+DI/-DI, 트루レンジ 평활, 方向性強度)와는다름. | [SEEN: core/indicators.py: compute_trend_strength] | medium | ADX라고 기대하면 誤解. 추세の 強度를 測る目的には 쓰이겠지만, +DI/-DI 교차・추세方向・트루レンジ 기반 평활 등이 필요한 シナリオでは 不足. | この関数が “ADX”라고 呼ばれている箇所가 있으면 名称修正 or 実装 수정. 消費者가 真の ADX를 期待하는지 확인. |
| IND-03 | core/indicators.py: compute_atr vs src/indicators/general.py: calculate_atr | “ATR” 계산이 2종류: (1) core/indicators.compute_atr = Wilder平滑, (2) general.calculate_atr = 트루レンジ 단순평균. 同じ名前・동일 개념인데 平滑化 방식이 다름. | [SEEN: core/indicators.py: compute_atr, src/indicators/general.py: calculate_atr] | medium | 消費者가 두 ATR 중 어느 것을 쓰는지에 따라 値이 달라지고, スクリーナー／バックテスト／リスク(ストップロ스 등)에서 一貫性이 깨질 수 있음. | 어느 쪽이 権威인지 결정し, 불필요な 중복을 정리. 특히 스토ップ로스・ポジションサイ징 등 金銭影響 있는 곳에서 어느 ATR을 쓰는지 확인. |
| IND-04 | 終値系列의 順序仮定（古い→新しい） | 많은 함수가 `closes[-1]`을 최신으로 가정. 입력 순서가 반대이면 결과가 완전히 달라짐. 함수의契約이 문서화되어 있지 않음. | [SEEN: 各関数の clsoes[-1]/[-period:] 使用] | medium | データ取り込み層・特徴量抽出이 正しい 순서로渡さないと 全손가락이 뒤집힘. | 호출側이 系列 순서를 統一して渡하는지 확인. 가능하면 契約을 문서화(“ascending chronological order” 또는 “가장 최근 값이 마지막 요소”) |
| IND-05 | データ不足時の 静默デフォルト | RSI=50, MACD=(0,0,0,0), trend_strength=0.5, volatility=0.5 등. 例外를 발생시키지 않으므로 消費者가 “데이터 부족 상태의 중립 신호”를 진짜 신호로 오인할 수 있음. | [SEEN: 各関数の不足時_return] | medium | 데이터 부족 상황에서도 信号を 생성하면 誤信號/過信號의 원인. 특히 스クリ너・자동売買 맥락에서는 위험. | 핵심 용도(자동매매・スクリ너・バック테스트)에서 データ不足時의 취급을 통일(예: None 반환 +消費者がスキップ, 또는 明示的フラグ). 現在는 消費者側 구현을 봐야 판단 가능. |
| IND-06 | float価格ベースの計算 | 指標 계산은 float 기반. 금액・주문サイズなど金銭計算과 연결할 때 浮動小数誤差가 再개입할 소지. | [SEEN: core/indicators.py, src/indicators/general.py] | low | 지표 자체ではなく 그것을 入力으로 쓰는 後단 금액계산이 문제. このモジュール만 보면 低リスク지만, 後단 금액계산이 float이면 전체 리스크가 살아난다. | Tier1-10（포트폴리오/리스크/주문）에서 금액계산이 Decimal인지 float인지 확인. |
| IND-07 | specs.py의 文書は良好だが 実装との 乖離可能性 | ALL_SPECSの formula/rule_of_thumb/caveat는 監査に 유용하지만, 実装が その 仕様과 정확히 일치하는지（특히 고급 지표)는 全文대조 필요. | [SEEN: specs.py 구조, advanced.py 実装] | low | 문서と 코드가 어긋나면 감사・保守에 混乱. | specs.py의 各項目를 実装と 대조하는 작업를 별도 턴에 수행. |

## 3.7 Module monetary risk

- **指標計算의 誤り(IND-01~03):** ボラティリティ・추세強度・ATR 등의 定義/平滑화가 기대하는 표준과 다르면, 스クリ너 선별・シグナル・スコアリング・리스크(ストップロス/ポジションサイズ)에 系統的誤差가 발생.
- **静默デフォルト(IND-05):** 데이터不足을 信号로 오판하면 誤発注・誤스크린・過信號의 원인.
- **入力순서(IND-04):** 시계열 순서가 뒤집히면 全ての 추세・モメンタム指標가 반전.
- **金額計算과의 연결:** 지표 자체는 float 기반이지만, 後단에서 금액・주문サイズ計算에 쓰일 때 float誤差・丸め가 金銭影響으로 転嫁될 수 있음.

## 3.8 Questions and unknowns

- `compute_volatility_regime`, `compute_trend_strength`가 실제 어디에 쓰이는지（ML 특징량, 스코어링, 리스크관리 등）.
- `src/indicators/trend_momentum.py`와 `advanced.py`에 同名／중복 함수가 몇 개나 있는지, 어느 것이 権威인지.
- 지표 입력이 항상 “古い→新しい” 순서로渡되는지, 消費者側의 契약은 무엇인지.
- 금・通貨・商品用 특징抽出（`_extract_gold_features` 등）の 전체 구현과 使用式.
- ATRの 두 実装 중 실제로 ストップロス・사이징 등 金銭影響있는 곳에 쓰이는 것은 어느 쪽인가.

## 3.9 Recommendations for Claude

- **再確認:**
  1. `compute_volatility_regime`와 `compute_trend_strength`의 使用箇所（누구が 왜 쓰는지）.
  2. `core/indicators.compute_atr` vs `src/indicators/general.calculate_atr` 중 실제로 金銭影響 있는 곳(ストップロス, ポジション사이즈, スクリ너閾値 등)에서 어느 쪽을 쓰는지.
  3. `src/indicators/trend_momentum.py` 전반（advanced.py과 重複する 함수们）.
  4. `services/signal_feature_pipeline.py` 전반（특히 금・通貨・商品 추출기）.
  5. 입력 시계열 순서의 消費者間 統一.
- **Claude가 반드시 깊게 읽을 파일:**
  - `core/indicators.py`（全文, 이미 읽음 — Claude도 自分の目で 확인）.
  - `src/indicators/advanced.py`（全文, 이미 읽음）.
  - `services/signal_feature_pipeline.py`（全文 — ML 특징량 파이프が 指標を 어떻게 쓰는지）.
  - `services/confidence_scorer.py`, `services/ml_signal_connector.py`, `services/quant_signal_orchestrator.py`（指標消費面）.
  - `src/gold_desk/scorer.py`（점수計算이 指標・市場 데이터를どう 쓰는지）.

---
*保存: 2026-10-05 · ラベル: [SEEN] コードで確認（path:line）、core/indicators.py・src/indicators/advanced.py・general.py・stocks.py・scoring.py・__init__.py 全文読了、specs.py・trend_momentum.py・constants/indicators.py・signal_feature_pipeline.py（前半）読了*

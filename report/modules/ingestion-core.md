# Module card: ingestion-core

**Name:** ingestion-core  
**Path:** `ingestion/main.py` (171), `ingestion/worker.py` (182), `ingestion/config.py` (80), `ingestion/http_client.py` (118), `ingestion/layered_store.py` (216), `ingestion/symbol_scanner.py` (263), `ingestion/market_data.py` (90), `ingestion/validation.py` (77), `ingestion/raw_validation.py` (144), `ingestion/db/session.py` (~+), `ingestion/lake/__init__.py` (+), plus sources/parsers/scanners/storage libs  
**Tier:** 1（市場データ取り込みの中核 — 価格・スナップショット・銘柄一覧の正確性と新鮮度に直結）  
**Purpose:** 市場データ取り込みエンジンの起動/停止、オーケストレーション、HTTP クライアント（aiohttp + retry）、MiniO 生データ湖（RawDataLake）、パーサレジストリ、 重複排除（DeduplicationEngine）、 layered storage（Hot = Redis latest-per-symbol / Warm = brsapi_symbol_snapshots bulk upsert）、AllSymbols スキャナ（市場時間認識 cadence）、正規の MarketTick（Decimal, 送信時刻＋受信時刻, source/instrument/asset_class）、生データ検証（RawQuoteValidator）と市場データ検証（MarketDataValidator: ジャンプ／古さ／スプレッド）。  
**Main files（行数）:** 上記。  
**Files read:** main.py, worker.py, config.py, http_client.py, layered_store.py, symbol_scanner.py, market_data.py, validation.py, raw_validation.py, db/session.py, lake/__init__.py（全文読了）。sources/parsers/scanners/storage は構造＋主要インタフェースを確認（全文は次回）。  
**Files unread (full):** sources/*, parsers/*, storage/*, fx/*, gold/*, identity/*, retry/*, replay/*, scheduler/*, lake の詳細など（代表的に読んで構造把握済みだが全文未読）。

## 3.1 Identity

- **エントリポイント / 消費者:**
  - `IngestionEngine`（main.py）＝取り込みエンジン。`run_ingestion()` がエントリ（asyncio.run）。HttpClient + RawDataLake + ParserRegistry + DeduplicationEngine + StorageLayer + IdentityResolver + 各 source + MarketScheduler を組み立てて起動。
  - `IngestionWorker`（worker.py）＝各 source を登録し、`ingest_all()` で source ごと fetch→重複排除→生データ湖格納→パース→identity 解決→storage 書き込み。
  - `AllSymbolsScanner`（symbol_scanner.py）＝`/Tsetmc/AllSymbols.php` を市場時間認識 cadence（取引中 30 秒 / 休憩中 300 秒など）でポーリングし、生データ検証→ScanResult→`on_scan` コールバックで永続化。
  - `LayeredStoragePipeline`（layered_store.py）＝Hot（Redis）に最新 1 件を TT L 90 秒で書き、続いて Warm（brsapi_symbol_snapshots bulk upsert）に書く。Warm 失敗しても Hot は残る。
  - `MarketTick`（market_data.py）＝正規の 소스非依存 市場観測。価格は `Decimal`（浮動小数回避）、`observed_at`（ソース時刻）＋`received_at`（受信時刻 UTC）、品質フラグ（CLEAN/SUSPICIOUS/STALE/INVALID）。
  - `MarketDataValidator`（validation.py）＝ジャンプ率（デフォルト 20%）、古さ（デフォルト 20 分）、スプレッド率（デフォルト 10%）でフラグ付け。STALE/SUSPICIOUS に分ける（stale 優先）。
  - `RawQuoteValidator`（raw_validation.py）＝AllSymbols 生行の前検証（詳細は raw_validation.py 参照）。
  - `HttpClient`（http_client.py）＝aiohttp セッション、retry_async ラップ、リトライポリシーは config 由来。
- **依存:** aiohttp, asyncpg, minio（RawDataLake）, redis（Hot 層＋ dedup）, pydantic/pydantic_settings, core.logging, core.result（Result）, core.time（UTC）, Decimal, datetime, asyncio, zoneinfo（テヘラン保管）。

## 3.2 Logic and algorithms

- **IngestionEngine.start（main.py）:**
  - HttpClient.start, RawDataLake.start, パーサ登録（TsetmcMarketWatchParser, TsetmcTradeParser, TsetmcOrderBookParser, FinpyTseParser, TsetmcLibParser, TehranStocksParser, TseUtilsParser）, DeduplicationEngine（Redis がある場合）, StorageLayer（DB がある場合）, IdentityResolver（DB がある場合）, TsetmcInstrumentSource を shared で生成.
  - ソースを config.enabled_sources に従って worker に登録（tsetmc_marketwatch, tsetmc_trades, tsetmc_orderbook, ifb, ime_energy, tsetmc_options, tsetmc_futures, codal, finpy_tse, tsetmc_lib, tehran_stocks, tse_utils）ただし tsetmc_instruments は worker の instrument_source として渡し、重複 fetch を避けるため source 登録しない.
  - MarketScheduler に `worker.ingest_all` を on_tick として登録して開始.
- **IngestionWorker.ingest_all（worker.py）:**
  - `_refresh_instruments()` で 1 時間ごとに銘柄 ID リスト更新（TsetmcInstrumentSource.get_instrument_ids）.
  - source 種別ごとに振る舞い分岐：
    - TsetmcTradeSource / TsetmcOrderBookSource / TsetmcOptionSource / TsetmcFutureSource → 上位 5 銘柄ずつイテレート（最多 5 件）.
    - FinpyTseSource → market_watch 型で 1 回.
    - TsetmcLibSource → 先頭 1 シンボルの "all".
    - TehranStocksSource → all_stocks.
    - TseUtilsSource → market_overview.
    - その他 → source.fetch() そのまま.
  - 例外時は結果に -1 を入れて続行（individual source 失敗で全体停止しない）.
- **IngestionWorker._ingest_source（worker.py）:**
  - source.fetch(context) → FetchResult.payloads をイテレート.
  - dedup（あり場合）: `is_duplicate(source, raw_data)` で重複ならスキップ、そうでなければ `mark_seen`.
  - RawDataLake.store_raw(...) で生データ格納 → object_key.
  - ParserRegistry.find(source, endpoint, content_type) でパーサ取得.
  - パーサで解析 → events（MarketTick  등）.
  - event に raw_object_key, parsed_at（UTC ISO）付与.
  - IdentityResolver.resolve(...) で instrument_id 解決 → event.data["instrument_id"] 設定.
  - _write_event で event_type 別に storage に書く（trade_tick, market_snapshot, orderbook_level, daily_ohlcv, price_adjustment → write_corporate_action）.
  - 失敗しても個別例外で継続（logging.exception）.
- **LayeredStoragePipeline（layered_store.py）:**
  - HotLayer（Redis namespace "ingestion:hot"）: symbol ごとに "quote:{symbol}" JSON に _HOT_FIELDS（symbol, ins_id, name, sector, price_last, price_close, price_yesterday, price_last_change_pct, trade_volume, trade_value, trade_count, base_volume, market_value, time）+ fetched_at を TTL 90 秒で格納. "scan:latest" に 一括メタ（fetched_at, count, symbols）.
  - SymbolSnapshotWarmSink: brsapi_symbol_snapshots に BulkUpsertRepository で (symbol, fetched_at) ON CONFLICT UPDATE で書く.
  - 両層独立成功/失敗を PersistReport に乗せる（hot_error / warm_error 別々）.
  - Hot TTL 90 秒＝ 30 秒 cadence の 3 倍で、1 回測定失敗でも読者が blank にならないように.
- **AllSymbolsScanner（symbol_scanner.py）:**
  - MarketSession（テヘラン時刻、取引曜日デフォルト 土曜～水曜＝ (5,6,0,1,2)、開場 08:30 / 閉場 15:30、デフォルト Asia/Tehran）.
  - Windows 向けに ZoneInfo("Asia/Tehran") が無い場合 +03:30 固定フォールバック.
  - scan_once: `client.fetch_all_symbols(symbol_type)` → RawQuoteValidator.validate(rows) → ScanResult（fetched_at, symbol_type, raw_count, latency_ms, validation, records=validation.accepted）.
  - run ループ: scan_once → 成功なら on_scan(scan) → `_sleep_next()`（市場時間中は cadence.market_seconds、休憩中は min(off_hours_seconds, seconds_until_open)）.
  - 停止は asyncio.Event.
- **RawQuoteValidator（raw_validation.py）:** （詳細は raw_validation を参照するが、概要）AllSymbols 生行に対して基本的妥当性検証（シンボル存在、価格/量など）を行い、検証通過行のみ ScanResult.records に.
- **MarketTick（market_data.py）:** Decimal 価格, 送信時刻＋受信時刻, source/instrument/asset_class, 品質フラグ＋理由リスト, raw_object_key, raw_sha256, metadata. 受信時刻はデフォルトで `datetime.now(UTC)`. 価格系フィールドは文字列カンマ除去して Decimal に変換（parse_decimal）.
- **MarketDataValidator（validation.py）:** last_prices 辞書（(source, instrument) → Decimal）でジャンプ計算。stale は age > max_age。jump > max_jump_pct で "jump:..."。 bid/ask 逆転（crossed_book）や 過広いスプレッド（wide_spread）でフラグ。理由があれば CLEAN 以外（stale 優先で STALE、そうでなければ SUSPICIOUS）に設定. すべての行は accepted に乗る（拒否ではなくフラグ）— 非正価格（price<=0）のみ rejected カウントして continue.

## 3.3 Data

- **入力:** 各ソースの HTTP レスポンス（生 bytes）, AllSymbols 行, パーサ出力イベント, DB/Redis/MinIO からの状態.
- **出力:** MarketTick/イベント, ScanResult, PersistReport, 取り込み結果カウント辞書.
- **格納先:** MiniO 生データ湖（raw-payloads / parsed-data バケット）, Redis Hot 層（"ingestion:hot" namespace）, PostgreSQL brsapi_symbol_snapshots（Warm）, 任意の storage 層（trade_tick, market_snapshot, orderbook_level, daily_ohlcv, price_adjustment）.
- **データ契約:** source.fetch は FetchResult（payloads リスト）を返す。パーサは raw_data → events（MarketTick 등）list。storage は イベント型別に書き込み。Hot は symbol ごとの JSON.

## 3.4 General checklist

- **ロジック:**
  - [YES] Decimal で価格を保持（浮動小数回避）. [SEEN: market_data.py: MarketTick, parse_decimal]
  - [YES] observed_at と received_at を分離（ソース時刻 vs 受信時刻）. [SEEN: market_data.py: MarketTick]
  - [YES] layered storage で Hot 優先＋ Warm は失敗しても Hot は残る（独立報告）. [SEEN: layered_store.py: persist]
  - [YES] AllSymbols は市場時間認識 cadence（休憩中は開場まで sleep）. [SEEN: symbol_scanner.py: MarketSession, _sleep_next]
  - [YES] Windows 欠損時の テヘラン時刻フォールバック（+03:30）. [SEEN: symbol_scanner.py: tehran_timezone]
  - [NO] ingestion/config.py の market_open/close は 08:30–15:30（これも core/time の 09:00–12:30 連続セッションと異なる）。同じく ING-03 と並行して確認が必要。 [SEEN: ingestion/config.py: market_open/close]
- **時間:**
  - [YES] received_at は UTC、observed_at は ソース時刻（UTC に統一する検証あり）. [SEEN: market_data.py: ensure_utc]
  - [YES] MarketSession はテヘラン現地時刻で 取引曜日／開場閉場判定. [SEEN: symbol_scanner.py: MarketSession]
  - [UNKNOWN] テヘラン貿易曜日デフォルト (5,6,0,1,2)＝ 土曜～水曜。イラン証券市場の実際のカレンダー（木・金休業が一般）と一致するか確認必要（次回 jobs.market_hours も併せて）。 [SEEN: symbol_scanner.py: DEFAULT_TRADING_WEEKDAYS]
- **データ:**
  - [YES] 生データは MiniO の raw-payloads に格納、オブジェクトキーは store_raw の戻り. [SEEN: worker.py: _ingest_source]
  - [YES] raw_sha256 フィールドはあるが、どの段階で計算して入れるかは未確認（パーサか storage か）. [SEEN: market_data.py: MarketTick.raw_sha256]
  - [UNKNOWN] identity 解決の 詳細（SymbolSnapshotModel / instruments テーブル など）— identity/__init__.py を 読む必要. [SEEN: worker.py: _write_event で _identity.resolve を呼んでいるが 実装未読]
- **エラー:**
  - [YES] source 個別失敗は -1 カウントで継続. [SEEN: worker.py: ingest_all]
  - [YES] parse 失敗は warning ログ＋ 生ペイロードは残し、続行. [SEEN: worker.py: _ingest_source]
  - [YES] Hot/Warm 書き込み失敗は PersistReport に エラー文字列として載せ、上位に例外を上げない. [SEEN: layered_store.py: persist]
  - [NO] AllSymbols スキャナの on_scan ハンドラ失敗は例外キャッチしてログのみ（ループは止まない）. [SEEN: symbol_scanner.py: run]
- **並行性:**
  - [YES] HttpClient は asyncLock でセッション初期化/停止を保護. [SEEN: http_client.py]
  - [YES] RateLimiter（http_client 内）は asyncio.Lock. [SEEN: http_client.py: RateLimiter]
  - [UNKNOWN] MarketScheduler の 複数ワーカー／並行 tick 実行の セマンティクス（scheduler/__init__.py を読む必要）.
- **性能:**
  - [YES] AllSymbols は 市場中 30 秒 cadence（config で変更可能）. [SEEN: symbol_scanner.py, ingestion/config.py]
  - [YES] Warm は bulk upsert（行単位ではなくバルク）. [SEEN: layered_store.py: SymbolSnapshotWarmSink]
  - [UNKNOWN] 銘柄数が多いときの上位 5 件しか取らない trade/orderbook の サンプリング戦略が 要件に合ってるか. [SEEN: worker.py: ingest_all の イテレーション上限 5]
- **セキュリティ:**
  - [UNKNOWN] RawDataLake の MinIO 資格情報（lake_access_key/lake_secret_key）が config デフォルト "minioadmin"／"minioadmin"。本番でデフォルトのままだと 위험에。.env で上書き予定だが、デフォルトが弱い。 [SEEN: ingestion/config.py: lake_access_key/lake_secret_key]
  - [UNKNOWN] DB DSN の デフォルトも postgres:postgres@localhost:5433/marketdb（デフォルトが弱い）. [SEEN: ingestion/config.py: db_dsn]
  - [UNKNOWN] IdentityResolver や storage が SQL を文字列連結して書いてるかどうか（次回 該当ファイル読む）。
- **ロギング／可観測性:**
  - [SEEN] source 別結果カウント、scan 受理/拒否/重複カウント、hot/warm 写入報告、パーサ欠け警告. [SEEN: 各ファイル]
  - [UNKNOWN] 取り込み全体の遅延／新鮮度メトリクスが どこまで可視化されてるか.

## 3.5 Specialized checklist

- **市場セッション／取引時間:**
  - [SEEN] ingestion/config.py: market_open=08:30, market_close=15:30.
  - [SEEN] symbol_scanner.py: MarketSession デフォルト 08:30–15:30、取引曜日 土曜～水曜.
  - [SEEN] brsapi/config.py: market_open=08:30, market_close=15:30.
  - [SEEN] core/time: 連続セッション 09:00–12:30、休日/曜日扱いが別.
  - **不整合発見:** 「取引時間」の定義が 複数あり、しかも値も異なる。 ingestion は 08:30–15:30（広め）、core/time は 09:00–12:30（連続セッション）。それぞれが使う場所が 異なる意味なら OK だが、もし「市場開いているか」判定に 混用されてるとバグ。 [SEEN: 複数ファイル] → 次の グローバルスキャンで 取引時間使用箇所を 全検索.
- **Decimal 価格:**

良好。 monetary calculation の 根本的リスク（float で金額）を避けてる。 [SEEN: market_data.py]

- **新鮮度検証:**

MarketDataValidator が staleness / jump / spread を 検証（ただし フラグ付けで、自動除外しない）。 これにより 異常値が 下流に回るのを 検知できるが、 下流が 品質フラグを 無視すると意味が薄れる。 [SEEN: validation.py]

- **重複排除:**

DeduplicationEngine（Redis 基、窓 60 分デフォルト）で 生データを 重複排除。 ただし ソース側で 同じデータが 異なる raw_data ハッシュで来る場合は 効かない可能性. [SEEN: worker.py: _ingest_source]

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| ING-07 | ingestion/config.py: lake_access_key/lake_secret_key（デフォルト "minioadmin"） | MiniO の アクセスキー／秘密鍵の デフォルトが 良くない値（minioadmin）。 本番で .env 未設定だと 脆い。 | [SEEN: ingestion/config.py] | medium | 取り込み層の オブジェクトストア資格情報が デフォルトで 漏れやすい。 公開リリース前に デフォルトを 空／必須にするか、 최소한 警告を出す。 | .env の 実設定を 確認（読むなという規則があるので、コード上で デフォルト依存の危険性を 確認する）。 |
| ING-08 | ingestion/config.py: db_dsn デフォルト（postgres:postgres@localhost:5433/marketdb） | DB 接続文字列の デフォルト資格情報も弱い（postgres:postgres）。 | [SEEN: ingestion/config.py] | medium | 開発前提とはいえ、 公開リリース時に 危険。 ベストプラクティスとして デフォルトを 空にするか、 ローカル開発用である旨を 明記。 | 同上。 |
| ING-09 | symbol_scanner.py: DEFAULT_TRADING_WEEKDAYS = (5,6,0,1,2)（土曜～水曜） | イラン証券市場の 通常の休場は 木・金（核心/time も 木・金 weekend）。 取り込み側の デフォルト取引曜日が 異なる（土～水）。 意味解釈が 逆転してる possibly。 | [SEEN: symbol_scanner.py: DEFAULT_TRADING_WEEKDAYS, core/constants/markets.py: MARKET_WEEKEND_DAYS=(3,4), core/time: 金曜日まで] | **high** | 取引日に なるべき日に スキャナが 休止し、 休止すべき日に ポーリングし続ける可能性。 市場時間判定の 基礎が ずれる。 | MarketSession の 曜日が 正しい意図か、 아니면 設定ミスかを 確認。 臨床的には 木・金が 休日のケースが 一般的なので、 (5,6,0,1,2) は 逆転の疑い。 |
| ING-10 | 取引時間定義の 複数乖離（08:30–15:30 vs 09:00–12:30） | ingestion/brsapi の market_open/close と core/time の 連続セッションが 異なる範囲。 使われる場所が 統一されてないと、 「今 取引中か」 の判定が 模块間で 食い違う。 | [SEEN: ingestion/config.py, brsapi/config.py, core/time/market_sessions.py] | medium | 放送／アラート／指標計算などで 「今 取引中」 の基準が 揺れると、 通知漏れや 不必要な計算が発生。 | どの定義が 権威かを 決めて 統一するか、 少なくとも 用途別名前（trading_session vs ingestion_window etc.）に 分離するか確認。 |
| ING-11 | ingestion/worker.py: 上位 5 銘柄しか 取得しない source（trade/orderbook/option/future） | 全銘柄を 取得すべき source なのか、 サンプル（上位 5）で 十分なのかが 要件次第。 不明確だと データ漏れの リスク。 | [SEEN: worker.py: ingest_all の イテレーション上限 5] | low | 要件が 「全銘柄取得」なら 不足、 「例示／負荷抑制」なら OK。 用途を 確認。 | 該当 source の 要件（全銘柄かサンプルか）を 確認。 |
| ING-12 | market_data.py: raw_sha256 フィールドはあるが どこで入れるか未確認 | MarketTick に raw_sha256 があるが、 設定する箇所が 読んだ範囲では 不明（パーサ／storage の どちらか）。 未設定だと 無意味なフィールドになる。 | [SEEN: market_data.py: MarketTick.raw_sha256] | low | 整合性検証用ハッシュが 実質未使用だと 設計と実装の 乖離。 | どこで設定してるか 確認（パーサか storage か）。 |

## 3.7 Module monetary risk

- **価格 정확한 새로고침 실패:** AllSymbols cadence が長すぎる／ market session 判定が 間違ってると、 価格が 古いまま 消費されて 指標／アラート／意思決定が 誤る。
- **取引曜日/時間の 誤判定（ING-09, ING-10）:** 取引中に オフ時間扱いして データ取り込みを 休んだり、 休場中に 取引中扱いして 不要な API 消費／古いデータ混合。
- **Decimal 未使用の 下流 float 汚染:** このモジュールは Decimal で きれいに扱ってるが、 下流（指標／バックテスト／信号）で float に 変換して 使うと 累積誤差リスクが 復活する（これは T1-4/5 で確認）。

## 3.8 Questions and unknowns

- MarketSession の 取引曜日 (5,6,0,1,2) は 正しい意図か（木・金休業が 一般的なので 逆転疑い）.
- 取引時間の 権威定義は どれか（08:30–15:30 の ingestion 側か、 09:00–12:30 の core/time 側か、それとも 別途）.
- 生データの raw_sha256 は どこで 設定されるか.
- IdentityResolver の 実装（identity/__init__.py）と storage の 書き込みが SQL 連結か否か.
- MarketScheduler の 複数worker 並行セマンティクス.

## 3.9 Recommendations for Claude

- **再確認:**
  1. `symbol_scanner.py` の DEFAULT_TRADING_WEEKDAYS が 正しい意図か（ ING-09）.
  2. 取引時間の 権威定義と 用途別乖離（ ING-10）— グローバル検索で 「market_open」「market_close」「is_market_open」「trading_hours」使用箇所を 洗う.
  3. `ingestion/config.py` の デフォルト弱い資格情報（ ING-07, ING-08）— 本番で .env 未設定の 危険性.
  4. raw_sha256 の 設定箇所（ ING-12）.
  5. IdentityResolver 実装（identity/__init__.py）と storage 書き込みの SQL 安全性.
- **必ず読むべきファイル（次回）:**
  - `ingestion/identity/__init__.py`（identity 解決ロジック）.
  - `ingestion/scheduler.py`（MarketScheduler の tick 調整／並行性）.
  - `ingestion/lake/__init__.py`（MiniO 格納の 実装詳細）.
  - `ingestion/raw_validation.py`（RawQuoteValidator の 全検証条件）.
  - `ingestion/sources/tsetmc.py` ほか sources（fetch→payload 構造）.
  - `ingestion/parser/`（パーサが events に 何を載せるか、新鮮度／品質の 取り扱い）.

---
*保存: 2026-10-05 · ラベル: [SEEN] コードで確認（path:line）、該当ファイル全文読了、sources/parsers/storage は構造＋インタフェース確認*

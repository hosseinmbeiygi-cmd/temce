# Module card: brsapi-ingestion-deep

**Name:** brsapi-ingestion-deep  
**Path:** `brsapi/services/sync_service.py` (1,812), `brsapi/jobs/registry.py` (1,768), `brsapi/services/history_fetch_service.py` (319), `brsapi/services/query_service.py` (779), `brsapi/models/*.py` (tsetmc 552, ime 390, codal 110, commodity 269, crypto 69, base 156), `brsapi/parsers/*.py` (commodity 701, tsetmc 609, ime 404, codal 136, crypto 90), `brsapi/repositories/base.py` (370), `brsapi/pipelines/*` (scanned; key ones read partially)  
**Tiอีร์:** 1 (外部データ取り込みの中心 — データ正確性 + プロバイダー鍵の安全性)  
**Purpose:** BrsApi.ir からの TSETMC / IME / Codal / 商品 / 仮想通貨 / 金・通貨 の取り込み 오케스트레이션：汎用 sync パイプライン（取得→パース→DB一括挿入→SyncLog→生ペイロード保存）、NAV の重複回避・ツイン折りたたみ・高速パス、Codal ページネーション、ジョブレジストリ（APScheduler 登録、市場時間ゲート、動的トグル、手動実行）、パーサー（TSETMC/IME/Codal/商品/暗号）、モデル、生リポジトリ。  
**Main files (lines):** sync_service.py (1,812), registry.py (1,768), query_service.py (779), history_fetch_service.py (319), parsers/commodity.py (701), parsers/tsetmc.py (609), parsers/ime.py (404), models/tsetmc.py (552), models/ime.py (390), repositories/base.py (370)  
**Files read:** sync_service.py, registry.py, history_fetch_service.py, query_service.py (要約読み), models/base.py, models/crypto.py, parsers/crypto.py, parsers/codal.py (要約), 残りは構造把握 + キー箇所読み（全文完全読みは次回に持ち越し）  
**Files unread (full):** parsers/tsetmc.py, parsers/ime.py, parsers/commodity.py (全文未読 — 構造と主要 parse 函数は確認済み）、models/tsetmc.py, models/ime.py, models/codal.py, models/commodity.py (全文未読）、repositories/base.py (全文未読）、pipelines/* (スキャンのみ)

## 3.1 Identity

- **エントリポイント / 消費者:**
  - `BrsApiSyncService`（sync_service.py）＝取り込みのオーケストレーター。`BrsApiClient.fetch()` → パーサー → `BulkUpsertRepository` → `SyncLogRepository` → オプションで `RawPayloadRepository`。
  - `BrsApiJobRegistry`（registry.py）＝ジョブ定義集合（`BRsAPI_SYNC_JOBS`）＋ APScheduler 登録、市場時間ゲート、動的トグル（`toggle_job`）、手動実行（`run_job_now` / `run_job`）。
  - シングルトン：`get_client()`（BrsApiClient）、`get_brsapi_job_registry()`、`get_rate_limiter()`（brsapi.rate_limiter）、`get_budget_governor()`（brsapi.budget）。
- **依存:** httpx, pydantic/pydantic_settings, jdatetime, SQLAlchemy async, brsapi.client, brsapi.config (BrsApiEndpoints/EndpointConfig/settings), brsapi.models, brsapi.parsers, brsapi.repositories, core.time (now_tehran), core.database (get_session), core.logging, jobs.market_hours (is_tehran_market_open / is_tehran_codal_window), pytz, asyncio.

## 3.2 Logic and algorithms

- **汎用 sync パイプライン**（sync_service.sync()）:
  1. dedup チェック（`dedup_seconds > 0` のとき `SyncLogRepository.needs_sync` で最近同期があればスキップ）。
  2. `client.fetch(endpoint, params, category_override)`。
  3. パーサ（sync/async 両対応）→ list/dict → list に正規化。
  4. `BulkUpsertRepository` で一括挿入（`SymbolSnapshotModel` のみ `ON CONFLICT (symbol, fetched_at) DO UPDATE`、それ以外は `ON CONFLICT DO NOTHING`。truncate_first オプション）。
  5. 生ペイロード保存（任意、`raw_bytes` がある場合）。
  6. `SyncLogRepository.record` で結果を記録し、コミット。
  - 失敗時：セッション ロールバック → SyncLog に error 記録 → コミット（ログ確保のため）→ SyncReport に error 返却。
  - `BrsApiResponse.is_empty` であれば 0 件成功として記録。
  - parse エラーは `ParseError:` 接頭辞、DB エラーは `DBError:` 接頭辞で記録。
- **NAV 固有ロジック**（sync_nav / sync_nav_all）:
  - 今日の NAV が既に存在すれば API 呼び出しをスキップ（`jdatetime.date.today()` で Jalali 今日(fmt `%Y-%m-%d`) を照会）。
  - `_parse_with_ins_id`内で API から得た date も `_normalize_codal_date` で正規化し、既存行があれば `None` を返して重複挿入を阻止。
  - `sync_nav_all`：
    - シンボル取得：スナップショットのセクターから動的検出（`fund_sector_sql_condition`）＋ キュレート済み `BRSAPI_ETF_SYMBOLS`（アラビア文字→ペルシア文字正規化後、DB に存在する物だけ）＋ 既存 NAV シンボル の和集合。
    - TSETMC 重複名ツイン（`ابتکار2` など）をベースシンボルに折りたたむ（`canonical_nav_symbol`）。ベースは `known`（現在のバッチ内）に存在する場合のみ採用（ありもしないシンボルを発明しない）。
    - 高速パス：今日の NAV を持つシンボルを除外クエリで一括排除（2 回目日の実行が ~1 秒で終わる）。
    - 1 要求あたり `sleep_seconds` デフォルト 11 秒（NAV 端末は 1 req / 10s → 12 req/min のため）。
    - 1 シンボルあたり `asyncio.wait_for(..., timeout=150)`（クライアント側リトライが最大 ~127 秒かかるため、外側ガードはより大きく）。
    - 途中経過ログ（10 シンボルごと）。
  - `is_fund_sector` / `fund_sector_sql_condition`：保険・年金セクター（`بیمه` / `بازنشستگی`）を除外して、NAV エンドポイントで必ず失敗するセクターが NAV 同期リストに漏れ込むのを防ぐ。
- **Codal ページネーション**（sync_codal）:
  - 1 ページ目で `count_page` を取得して総ページ数を決定（`max_pages` で上限可能）。
  - `stop_date`（Jalali YYYY-MM-DD）があれば、ページ内の最新日付が cutoff より古くなった時点で停止（ページは新着順）。
  - `_attach_codal_instrument_refs`：symbol から `ins_id` / `instrument_id` をスナップショット → `instruments` テーブル（text() 経由）の順でルックアップして付与。
  - `on_page_processed` コールバックでチェックポイント保存（再開可能な長時間バックフィル）。
  - 増分同期：1 ページが全部重複（`inserted == 0` かつ `len(records) > 0`）で停止。
  - ページ間でレートリミット待機（2 req / 10s → ~5.1 秒）。
- **ジョブレジストリ**（registry.py）:
  - `BrsApiSyncJob`：name, endpoint_config, cron（式 or 秒数）, category, params, enabled, description, market_hours_only, codal_window, forced。
  - クリティカルな全市場バックフィル（Candlestick / Shareholder / History price / History real_legal / Symbol detail）はチャンク分割＋日次実行＋市場後時刻にずらして配置（13:00 / 13:30 / 14:00 / 14:30 / 21:00）。
  - `market_hours_only`＋`codal_window`でテヘラン取引時間／コダールオフィス時間（08:00–18:00）以外の実行を阻止（無料ティアの 일일 쿼ータを市场閉場時に消費しないため）。`force=True` でバイパス可能。
  - `run_job`：市場時間ゲート → クライアント遅延初期化 → セッション取得 → サービス生成 → ジョブ固有ハンドラ（gold_currency_pro, gold_currency, 24h/daily history, candlestick_all, shareholders_all, history_price_all, history_real_legal_all, symbol_details_all）か、汎用 `service.sync()` にフォールバック。
  - 固有ハンドラは Many シンボルに反復＋ポライト遅延（0.5 秒）＋進捗コールバック対応。
  - `_get_parser` / `_get_model`：EndpointConfig.path → パーサ／モデル マッピング（設定と実装の整合性チェックに有用）。
- **取り込み管路（pipelines）**: `brsapi/pipelines/` に ingestion, normalization, validation, persistence, quotes, indicators, market, news, macro, funds, codal, enrichment などが存在。詳細は次回読む。

## 3.3 Data

- **入力:** BrsApi.ir の JSON（各種エンドポイント）、パラメータ（l18, type, page, history, section, date_start, date_end, symbol など）、Jalali/Gregorian 日付。
- **出力:** SyncReport（endpoint, success, items_count, duration_ms, error, skipped, failed_symbols, skipped_symbols, no_data_symbols, normalized_symbols）、健康状態/ジョブ状態。
- **格納先:** PostgreSQL（brsapi モデル群）、SyncLog（取り込み結果履歴）、RawPayload（監査用生応答、オプション）、Codal 関連項目（announcements, 機器参照）。
- **データ契約:** parse 結果は「レコードの list of dict」または dict（単一）。モデルごとのカラム/制約はモデル定義に依存（次回確認）。

## 3.4 General checklist

- **ロジック:**
  - [YES] dedup による再取得抑制（SyncLog  basing）。 [SEEN: sync_service.py: sync()]
  - [YES] NAV 今日存在時スキップ＋ date 重複挿入防止。 [SEEN: sync_service.py: sync_nav / _parse_with_ins_id]
  - [YES] TSETMC 重複名ツインのベース折りたたみ（NAV 専用）。 [SEEN: sync_service.py: canonical_nav_symbol]
  - [YES] Codal ページネーション＋ stop_date＋チェックポイント。 [SEEN: sync_service.py: sync_codal]
  - [YES] 市場時間ゲート（取引時間／コダールオフィス時間）。 [SEEN: registry.py: run_job]
  - [NO] `sync_nav_all` の シンボル源は「スナップショットセクター検出 ＋ キュレートリスト（DB 存在フィルタ） ＋ 既存 NAV シンボル」の和。セクター検出が失敗するとキュレートリストにフォールバックするが、キュレートリストも DB 存在フィルタを通るので、DB に無い物は API に行かない。 [SEEN: sync_service.py: _get_fund_symbols]
  - [UNKNOWN] キュレート済み `BRSAPI_ETF_SYMBOLS` の メンテナンス状態（記号が追加・廃止されたとき更新されているか）→ 定数定義を確認する必要。
- **時間:**
  - [YES] Jalali<->Gregorian 変換（`_to_jalali_date` は 1200–1500 年を Jalali とみなして通過）。 [SEEN: sync_service.py: _to_jalali_date]
  - [YES] Codal 日付正規化（ペルシア数字→ASCII、スラッシュ→ハイフン）。 [SEEN: sync_service.py: _normalize_codal_date]
  - [YES] ペルシア文字正規化（アラビア yeh/kaf → ペルシア）。 [SEEN: sync_service.py: _normalize_persian]
  - [YES] 今日 Jalali 取得に `jdatetime.date.today()` を使用（UTC じゃなくテヘラン現在）。 [SEEN: sync_service.py: sync_nav, sync_nav_all]
  - [UNKNOWN] `_to_jalali_date` の 1200–1500 ヒューリスティック：20xx 以外の将来年や特殊値で誤判定する可能性（現在は安全側）。 [SEEN: sync_service.py: _to_jalali_date]
- **データ:**
  - [YES] Transaction の `id`（API 側の per-symbol counter）をポップして DB オートインクリメントに任せる（交差シンボル PK 衝突防止）。 [SEEN: sync_service.py: sync_transactions]
  - [YES] Shareholder は API に date フィールド無し → 取得日付を stamp（NULL 防止）。 [SEEN: sync_service.py: sync_shareholders]
  - [YES] Candlestick は type を明示的に付与（NULL 防止）、type=1 はリフレッシュ前に delete。 [SEEN: sync_service.py: sync_candlesticks]
  - [UNKNOWN] モデル側の unique 制約／ on-conflict セマンティクス完全適合性（次回確認）。
- **エラー:**
  - [YES] parse/DB エラーを区別して記録。 [SEEN: sync_service.py: sync()]
  - [YES] Codal ページ単位のエラーで停止＋記録。 [SEEN: sync_service.py: sync_codal]
  - [YES] NAV シンボル失敗は failed_symbols に収集し、概要メッセージを構築（最大 10 個表示）。 [SEEN: sync_service.py: sync_nav_all]
  - [YES] 個々の NAV タイムアウト（150 秒）は失敗として収集。 [SEEN: sync_service.py: sync_nav_all]
- **並行性:**
  - [YES] sync_codal の `on_page_processed` は best-effort（失敗してもログのみ）。 [SEEN: sync_service.py: sync_codal]
  - [UNKNOWN] 並行して複数の sync セッションが同一の NAV シンボルを取得する際の競走（今日 NAV 存在チェックの TOCTOU）— 高速パス + sync_nav 内の再チェックで軽減されてるが、完全ではない可能性。 [SEEN: sync_service.py: sync_nav_all / sync_nav]
- **性能:**
  - [YES] バッチ挿入（batch_size デフォルト 500）。 [SEEN: sync_service.py: sync()]
  - [YES] NAV 高速パスで 2 回目実行を ~1 秒に短縮。 [SEEN: sync_service.py: sync_nav_all]
  - [UNKNOWN] BulkUpsertRepository の 実際の一括INSERT戦略（ executemany vs 単文バルク ／ ON CONFLICT のパフォーマンス）。
- **セキュリティ:**
  - [SEEN] api_key は client 層で 에러텍스트から redact（brsapi/client.py）。この層では生 params を SyncLog に記録することがあり、params に key が含まれると ログに漏れる可能性 → 確認必要。 [SEEN: sync_service.py: sync() が params を SyncLog に record する箇所]
  - [UNKNOWN] SyncLog や RawPayload に api_key が含まれるか（EndpointConfig の required_params に key があり、デフォルトで `{"key": self._api_key}` がパラメータに含まれる → SyncLog.record(params=params) で key が記録される可能性）。 [SEEN: client.py: _build_params, sync_service.py: sync() の sync_log.record(params=params)]
- **ロギング／可観測性:**
  - [SEEN] SyncLog に 全同期の 結果（エンドポイント、カテゴリ、ステータス、items_count、duration_ms、params、エラーメッセージ）を記録。 [SEEN: sync_service.py: sync()]
  - [SEEN] 生ペイロード保存（オプション）。 [SEEN: sync_service.py: sync()]
  - [SEEN] ジョブ実行ログ（開始／完了／スキップ／失敗）。 [SEEN: registry.py: run_job と 各ハンドラ]

## 3.5 Specialized checklist

- **データ取り込み・クリーンリング:**
  - [YES] 重複排除（dedup）、日付正規化、文字正規化、アセット種別分類（ファンドセクター認定）、不要 API 呼び出しの事前排除（NAV ツイン折りたたみ、今日の NAV 存在チェック）。
  - [UNKNOWN] 取り込みデータの 異常値検出／不完全データ検出 の Policy（次回 パイプライン/validation 確認）。
- **価格ソース:**
  - [SEEN] BrsApi.ir が TSETMC/IME/Codal/商品/暗号/金・通貨 の 主要ソース。 [SEEN: config.py エンドポイントカタログ]
  - [UNKNOWN] 二次ソース／フォールバック（ローカル DB フォールバック、別のプロバイダー）の有無と使い所。
- **調整（adj）:**
  - [UNKNOWN] 指標／バックテストで 資本増加・配当・株価分割調整を適用しているかどうかは他モジュール（T1-3 〜 T1-8）で確認。

## 3.6 Findings

| ID | path:line | description | evidence | severity | impact | note for Claude |
|---|---|---|---|---|---|---|
| ING-01 | sync_service.py: sync() の sync_log.record(params=params)（複数箇所） | `params` に api_key が含まれる状態で SyncLog に記録されると、取り込みログに api_key が平文で残る可能性。client._build_params は `{"key": self._api_key}` を必ず入れる。 | [SEEN: client.py: _build_params, sync_service.py: sync() 内の sync_log.record(params=params)] | **high** | SyncLog や生ペイロード/RawPayload が閲覧可能な状態だと API key漏洩。 | SyncLog と RawPayload の アクセス制御＋キー赤クレクトを確認。できれば params から key を除いて記録する。 |
| ING-02 | sync_service.py: _to_jalali_date の 1200–1500 ヒューリスティック | 1200–1500 年の 10 桁 YYYY-MM-DD を ペルシア年と判定して通過させる。20xx 以外の futuristic/特殊値で誤判定可能（現在は安全側だが脆い）。 | [SEEN: sync_service.py: _to_jalali_date] | low | 現在運用では問題にならないと思われるが、入力が制御外になると日付変換誤り。 | 呼び出し側が渡す date 源を確認。 |
| ING-03 | registry.py: market_hours_only ゲート | 市場時間ゲートの 基準時刻は `jobs.market_hours.is_tehran_market_open / is_tehran_codal_window`。この実装が core/time の セッション定義と一致するか確認必要。 | [SEEN: registry.py: run_job, config.py: market_open/close 08:30–15:30 vs core/time: 09:00–12:30] | medium | ゲートの時刻基準が柏林しく異なると、閉場後／開場前の不要取り込みや、必要な時間帯の取り込み漏れが起こり得る。 | is_tehran_market_open の 実装を読んで core/time と整合性を確認。 |
| ING-04 | sync_service.py: sync_nav_all の シンボル源 | キュレート済み `BRSAPI_ETF_SYMBOLS` が 古くなると、新規上場ファンドの NAV が取り込まれない（またはセクター検出で補われる）処理。 | [SEEN: sync_service.py: _get_fund_symbols] | low | キュレートリストの メンテナンス 状況を確認。 | BRSAPI_ETF_SYMBOLS の定義場所＋更新手順を確認。 |
| ING-05 | config.py: 404 廃止エンドポイントの 残骸 | GOLD_COIN, CURRENCY の 旧エンドポイントが 404（~2026 年 6 月以降）で、sync_gold_coin / sync_currency は deprecated ログを出して呼ぶが、ジョブ定義にも DISABLE の金コイン／通貨ジョブが残っている。 | [SEEN: config.py, sync_service.py: sync_gold_coin / sync_currency, registry.py: brsapi_gold_coin / brsapi_currency] | low | 古いジョブ定義が 混乱を招くが、enabled=False で 実害는 적다。 | 廃止ジョブ定義を整理できると良い（が 急ぎではない）。 |
| ING-06 | sync_service.py: sync_codal の _attach_codal_instrument_refs | Codal 添付時に `instruments` テーブルへ `text()` 経由で クエリ。SQL インジェクションは symbol リストを `in_` でバインドしているため直接の risk 는 낮으나、text() の 使い方次第では将来の変更で危険。 | [SEEN: sync_service.py: _attach_codal_instrument_refs] | low | 現時点では バインドされているので 直接の Injection risk 는 낮음。 | text() の 今後の変更を監視。 |

## 3.7 Module monetary risk

- **API key 漏洩（ING-01）**: SyncLog / RawPayload に key が平文で残ると、閲覧権限を持つ誰かが外部から児童データを取り込めるようになる → データ改ざん／料金消費／鍵ブロック。
- **誤った date 変換（ING-02）**: 取引日／ NAV 日付の 取り込み誤り → チャート／指標／バックテストの 時間精度悪化。
- **市場時間ゲートの基準不一致（ING-03）**: 不要な時間帯の API 消費（クォータ減少）または必要な取り込み漏れ（データの古さ）。
- **キュレートリストの 古さ（ING-04）**: 新ファンドの NAV 未取り込み → NAV プレミア計算等の 誤り。

## 3.8 Questions and unknowns

- SyncLog / RawPayload の アクセス制御と、params に key が含まれるかの 実証（キー赤クレクトの有無）。
- `BRSAPI_ETF_SYMBOLS` の 定義場所と更新手順。
- `jobs.market_hours.is_tehran_market_open` の 実装（core/time との整合性）。
- BulkUpsertRepository の ON CONFLICT 戦略と モデル側の unique 制約。
- パイプライン（brsapi/pipelines/*）での validation／異常値検出の有無。
- 二次ソース／フォールバックの有無。

## 3.9 Recommendations for Claude

- **再確認:**
  1. `sync_service.sync()` の `sync_log.record(params=params)` と `RawPayload` に api_key が含まれるか（client._build_params が key を入れるため、ほぼ含まれると推定 — 実証必要）。
  2. `jobs.market_hours.is_tehran_market_open` の 実装（core/time との整合性）。
  3. `BRSAPI_ETF_SYMBOLS` の 定義と更新手順。
  4. BulkUpsertRepository（repositories/base.py）の ON CONFLICT セマンティクス＋ モデル側 unique 制約。
- **Claude が 必ず深く読むべきファイル:**
  - `brsapi/services/sync_service.py`（全文 — 既に読んだが、Claude は パーサー呼び出し辺り／ ins_id ルックアップ／ conflict 戦略を 自分の目で確認）。
  - `brsapi/jobs/registry.py`（全文 — ジョブ定義の時系列・チャンク戦略・市場時間ゲート）。
  - `brsapi/config.py`（エンドポイントカタログ＋ settings — ING-01 の key 含む params 構造もここ）。
  - `brsapi/replicas/base.py`（BulkUpsertRepository の 実際の 一括挿入戦略）。
  - `brsapi/parsers/tsetmc.py`（TSETMC データの パース精度 — 次回読了）。

---
*保存: 2026-10-05 · ラベル: [SEEN] コードで確認（path:line）、sync_service.py と registry.py は全文読了、他は構造＋キー箇所読み*

# Progress — Deep Code Audit (temce)

**Prompt:** REPORT_PROMPT_EN_FULL.pdf (Deep Project Reporting Prompt)
**Project root:** C:/Users/Iran/Desktop/temce
**Started:** 2026-10-05

---

## Status

| Step | Status | Output |
|---|---|---|
| Step 1: Structure & statistics | ✅ DONE | report/01-structure.md |
| Step 2: Module classification & reading plan | ✅ DONE | report/02-modules-plan.md |
| Step 3: Deep module-by-module reading | 🔄 IN PROGRESS（「安全優先＋コア基盤」主要部分完了。指標・シグナル・スマートマネー・バックテスト・オプション・ポートフォリオ/リスク・アラート・ML へ継続） | report/modules/*.md（下参照） |
| Step 4: Global scans | ⬜ NOT STARTED | report/04-global-scans.md |
| Step 5: Synthesis & final report | ⬜ NOT STARTED | report/REPORT.md |
| Step 6: Skills inventory & review | ⬜ NOT STARTED | report/06-skills.md + report/skills/*.md |

---

## Step 3 module cards written so far（今ターンの分は太字）

1. `report/modules/core-security.md` — JWT＋refresh、スコープ付きAPIキー（GoldDesk SaaS）、RBAC/IME分離（سند §14.2）、パスワードハッシュ（PBKDF2 10万ラウンド）、TOTP、入力サニタイザ、secret envリーダー
2. `report/modules/platform-config-and-database.md` — .envからのSettings（pydantic）、本番検証、非同期SQLAlchemyエンジン＋セッションファクトリ＋読み取りレプリカ＋コミットガード（raw DML検出）
3. `report/modules/platform-observability.md` — structlog、シンプルCacheService＋3層CacheManager（L1 LRU＋L2 Redis＋L3 compute single-flight）、Sentry（オプション、authヘッダをscrub）
4. `report/modules/core-events-and-resilience.md` — DomainEvent＋EventBus（ハンドラ障害の隔離）、circuit breaker（core/circuit_breaker.py）、feature flags、health（liveness/readiness/monitor/provider/system）、paths（path-traversal安全）、validation（symbol/ISIN/date/file/payload）、time（UTC＋Tehran、市場時間 09:00–12:30、週末木・金）、enums/constants（markets/instruments/alerts/signals/jobs/rbac/recommendations/providers/indicators/ML/paths）、IDs（uuid/run_id/symbol_id/trace_id）、typing Result、DI container/providers/registry/lifecycle
5. `report/modules/api-middleware-and-rate-limit.md` — request context/trace、timing、security headers、CSRF（origin vs cors_origins）、入力サニタイゼーション（JSONボディ再帰、strip_html＋CRLF/NUL除去、opaque-field allow-list）、IP別スライディングウィンドウ率制限（Redis Lua可）＋ユーザー層バケット、機密書込みプレフィックスへの防御深度認証
6. `report/modules/core-resilience-and-rate-limiting.md` — retry（backoff＋jitter、同期retriesがイベントループをblockする注意）、率制限（TokenBucket＋スライディングウィンドルRateLimiter with Redis Lua＋ローカルフォールバック、adaptive、バジェットマネージャ）、circuit breaker（2実装が存在：古いcore/circuit_breaker.py vs 充実したcore/resilience/circuit_breaker.py；同期@circuit_breakerデコレータはno-op）、failover/degradation/fallback/incident_policy、並行性（TaskGroup, AdaptiveSemaphore, RateLimitingSemaphore, AsyncQueue, PriorityQueue, WorkerPool, Scheduler with simple cron）
7. `report/modules/brsapi-client-and-budget.md` — BrsApi.ir 非同期HTTPクライアント（TSETMC/IME/Codal/商品/暗号/金・通貨エンドポイント）、公式レート制限付きエンドポイントカタログ、3層率制限（日別＋5分＋カテゴリ別バケット）、永続化・プロセス間バジェットガバナータ（Redis/file/memory、Lua check-and-reserve日別、ZSET 5分、302ブロッククールダウン900秒、非クリティカルを95%でソフトリジェクト）、キー準備完了プローブ（enabledゲートは迂回するがガバナーfail-fastは尊重）、**所見: 日別上限デフォルトの不整合（docは4,000/日、フィールドデフォは10,000）**
8. `report/modules/brsapi-ingestion-deep.md` — sync_service（汎用syncパイプライン、NAV重複回避＋ツイン折りたたみ＋高速パス、Codalページネーション＋チェックポイント、TSETMC/IME/商品/暗号/金・通貨取り込み）、jobs/registry（ジョブ定義、APScheduler登録、市場時間ゲート、動的トグル、手動実行、全市場バックフィル時刻戦略）、**所見: SyncLog.record(params=params)にapi_keyが含まれる可能性（high）**、**所見: 市場時間ゲート基準時刻とcore/timeの乖離（medium）**
9. `report/modules/ingestion-core.md` — IngestionEngine（起動/停止、オーケストレーション）、IngestionWorker（source登録＋fetch→重複排除→生データ湖→パーサ→identity解決→storage書き込み、上位5銘柄サンプリング）、AllSymbolsScanner（市場時間認識cadence、30秒/300秒、Windows向けTehran時刻フォールバック）、LayeredStoragePipeline（Hot=Redis最新1件TTL90秒＋Warm=brsapi_symbol_snapshots bulk upsert、独立報告）、MarketTick（Decimal価格、observed_at＋received_at、品質フラグCLEAN/SUSPICIOUS/STALE/INVALID）、MarketDataValidator（ジャンプ20%/古さ20分/スプレッド10%でフラグ付け）、RawQuoteValidator、生データ検証、**所見: 取引曜日デフォルトが土～水 (5,6,0,1,2) で木・金休業の一般的な前提と異なる suspected（high）**、**所見: 取引時間定義が ingestion/brsapi（08:30–15:30）とcore/time連続セッション（09:00–12:30）で異なる（medium）**、**所見: MiniO/DBのデフォルト資格情報が弱い（medium）**、Decimal価格の採用は良好

---

## Safety-first finding — 更新（自動取引／注文／telegram）

**実注文オートメーション状況（今ターンまで）:**

- `services/broker/paper_broker.py` — ペーパーブローカーのみの（内部dict、idempotent、外部接続なし）。[SEEN]
- `src/gold_desk/auto_trade.py` — デフォルト `enabled=False`, `dry_run=True`；liveパスは `GOLD_BROKER_API` envを要し、現在 **placeholder**（`{"status": "live_placeholder", "executed": False}`、`# TODO: implement broker-specific call`）。[SEEN]
- `src/gold_desk/telegram_bot.py` — Telegram Bot APIメッセージのみ（token＋chat_idはenv、1 msg/secセマフォでレート制限）；注文ではない。[SEEN]
- `src/gold_desk/api.py` — `/gold/telegram/test`はテストメッセージ送信、`/gold/telegram/status`は設定報告、`/gold/portfolio/trades`はDBへのtrade記録（実注文ではない）；GoldDeskルーターは **設計上未認証**（プレフィックス `/gold`、コメント「بدون auth چون شخصی است」）。[SEEN] → **SEC-06: GoldDeskエンドポイントは設計上未認証（個人利用）**。一方 `/api/v1/golddesk` はスコープ付きトークン認証。
- `apps/api/endpoints/trades.py`, `recommendations.py`, `compose.py` — read/CRUD＋戦略構成；実ブローカーコールは見ず。[SEEN]
- `apps/decision_engine/app.py` — 決定エンジンmicroservice；意思決定はBUY/WATCHLIST/HOLD/REDUCE/REJECT/NEUTRAL（読み取り＋決定記録）；このファイルでは実注文パスなし。[SEEN]
- **結論（今ターンまで）:** 読んだファイルには実装済みのliveブローカー接続はない。`auto_trade.py`の唯一のliveパスはplaceholder。**残リスク:** 他のservices/ingestion/brokerアダプターが存在する可能性 — プロジェクト全体で `GOLD_BROKER_API`, `send_order`/`place_order`/`submit_order`, ブローカー接続, `telegram_bot`使用, `auto_trade`有効化パスを継続スキャンする。

**SEC-06（今ターン新規）:** `src/gold_desk/api.py:7` — GoldDeskルーター接頭辞 `/gold` は**設計上未認証**（「بدون auth چون شخصی است」）。一方 `/api/v1/golddesk` はスコープ付きトークン認証。認証モデルが異なる2つの金表面が存在。[SEEN]

**SEC-01/CFG-01（再開）:** デフォルト `SECRET_KEY = "change-me-in-production"` — `.env`は読んでいないが、デフォルトはよく知られた値。[SEEN]

---

## グローバルスキャン前に行うべきプロジェクト全体の安全性＋データ取り込み確認（今後のターンで継続）

今の時点で 明らかなのは以下：

- 実装済みのliveブローカー接続は見ていない（placeholderのみ）。 ただし すべての ブローカー／注文系アダプターを 確認するには グローバル grep が必要。
- 取り込み層には 取引曜日／取引時間の 定義が 複数あり、しかも 値が異なる箇所がある（ ING-09, ING-10）。
- 取り込み層の デフォルト資格情報（MiniO、DB）が 弱い（ ING-07, ING-08）。
- SyncLogに api_key が含まれる可能性（ ING-01）。

次ターン以後で 以下を続ける：

- Tier 1 残り： T1-3（quotes/marketデータサービス）、 T1-4（指標＋テクニカルエンジン）、 T1-5（シグナル： multi_market_signal_engine, quant_signal_orchestrator, signal_*, stock_signal_engine, ime_*, pre_buy）、 T1-6（スマートマネー／ミクロ構造）、 T1-7（バックテストサービス）、 T1-8（バックテストライブラリ）、 T1-9（オプション）、 T1-10（ポートフォリオ/リスク/トレード/killスイッチ/ペーパートレード）、 T1-11（アラート）、 T1-12（ML/フォーキャスティング/トレーニング）
- その過程で ブローカー／注文系を 発見次第 即時カード化し、 実注文経路があれば 停止して 報告する（規則2：実世界副作用のない確認しかしない）。
- その後 Tier 2（Codal, news, funds, screener/Program110, 金・通貨・商品, 戦略構成/データインポート）
- Tier 3（ユーザ/認証/RBAC、チャット/アシスタント、報告/分析/ダッシュボード、API配線/ジョブ/スケジューラ/管理/ゲートウェイ/CLI、ルートスクリプト/ユーティリティ）の主要部分
- 最後に Step 4 グローバルスキャン（秘密/ swallow例外/ float金額/ 時間帯・ Jalali-Gregorian混用/ 複雑関数上位/ TODO-FIXME/ 外部ソース/ ネットワークタイムアウト・ retry/ SQL連結/ ハードコード個人パス/ 機密データログ/ テスト状況/ データ契約不整合/ 依存状況）を実施

---

## 次のアクション（今後のターン、継続）

今は 中断せずに続ける指示なので、残 Tier1 中から 最も monetary impact が大きい 指標／シグナル／スマートマネー／バックテスト／オプション／ポートフォリオ-リスク-注文 の順で 読む。 ただし 文脈サイズと残時間に余裕を保つため、 今のターンでは **指標（ core/indicators.py ＋ src/indicators/*）** と **その呼び出し表面（ signal_feature_pipeline, stock_technical_engine, stock_tape_engine, indicator_precompute_service, および core/constants/indicators.py ）** を優先して カード化する。

その後に シグナルエンジン（ quant_signal_orchestrator, multi_market_signal_engine, signal_*, stock_signal_engine, ime_*, pre_buy ）へ入る。

---

## ✅ 是正フェーズ（Remediation）— 2026-10-05 実施

方針：`report/REMEDIATION_PLAN.md` を参照。各所見を現行コードで再検証し、実在する欠陥のみ修正＋回帰テスト追加。

| ID | 内容 | 対応 | ファイル |
|---|---|---|---|
| BUD-01 | 日次上限デフォルト 10,000 → 4,000（文書/テストと一致） | ✅ | `brsapi/rate_limiter.py`, `brsapi/config.py` |
| RRL-01/BUD-02 | CircuitBreaker を単一実装に統合（旧 shim を後方互換化） | ✅ | `core/circuit_breaker.py`, `core/resilience/circuit_breaker.py` |
| RRL-02 | sync デコレータが無効だった問題を `call_sync` で修正 | ✅ | `core/resilience/circuit_breaker.py` |
| latent | `half_open_calls` 未加算で probe 上限が無効 | ✅ | `core/resilience/circuit_breaker.py` |
| CFG-02/SEC-05 | `auth_disabled=True` を production/staging で拒否 | ✅ | `core/config/__init__.py` |
| SEC-01/CFG-01 | staging でもデフォルト鍵を拒否 | ✅ | `core/config/__init__.py` |
| OBS-01 | L1 の `None` を miss 扱いしない（sentinel） | ✅ | `core/cache_manager.py` |
| ING-01 | api_key は既に `_redact_params` で秘匿済み | ⚪ 既修正 | `brsapi/repositories/base.py` |
| SEC-02 | `sanitize_sql` は呼び出しなし（dead code） | ⚪ | — |
| ING-09 | 取引曜日 (5,6,0,1,2) は正しい（土〜水） | 🟢 誤検知 | — |

**検証:**
- `python -m pytest tests/unit/core tests/unit/test_brsapi_quota.py tests/unit/test_brsapi_outbound_simulation.py` → **243 passed**（修正前は BUD-01 の1件失敗）。
- 新規回帰テスト：`test_circuit_breaker.py`（sync/shim/half-open）、`test_cache_manager.py::test_cached_none_is_not_recomputed`、`test_config_validation.py`。
- `ruff check` 全変更ファイル合格、`py_compile` 合格。
- 既知の既存失敗は **フェーズ 7 で全て解消**（下記）：`critical` 属性の欠落（テストダブル側の不備）と、管理エンドポイントへの無認証アクセス（テストが `admin_client` を使っていなかった）。

---

## 🔁 完全性の再点検（v2）— 2026-10-05

全モジュールカードから所見 ID を機械的に抽出し、**55 件すべて**（BUD-01..07, CFG-01..05, ENR-01..07, ING-01..12, MW-01..06, OBS-01..05, RRL-01..07, SEC-01..06）を v1 プランと突き合わせた。
**v1 で未記載だった 7 件**を検証：

| ID | 検証 | 結果 |
|---|---|---|
| CFG-03 | `apps/api/middleware.py:257` 定義 + `apps/api/app.py:1040` `add_middleware` | 🟢 配線済み |
| CFG-04 | `core/database.py:222-228`（`_audit_wrote`/dirty 判定で commit） | 🟢 正常 |
| CFG-05 | `get_replica_session` は定義されるがどこからも `Depends` されていなかった | ✅ フェーズ 7 で修正（読取専用 7 ハンドラに配線＋書込みガード） |
| SEC-04 | `saas.py` の limiter はプロセス内 per-worker | 🔵 設計（低リスク） |
| ENR-05 | `core/paths.py` / `core/validation/files.py` | 🟢 あり |
| ENR-06 | `core/utils.py::safe_error_message` | 🟢 あり |
| ENR-07 | flag は定義済みだが Sentry は `settings.sentry_dsn` のみでゲートしていた | ✅ フェーズ 7 で修正（`sentry_enabled()` が DSN と flag の両方を必須化） |

**結論:** 55/55 を説明済み。high/medium の未対応なし。⚠️ の 2 件（CFG-05, ENR-07）も **フェーズ 7 で修正済み**。

---

## 🧩 フェーズ 7（残ギャップの修正）— 2026-10-05

| 項目 | 変更 | 検証 |
|---|---|---|
| CFG-05 (read replica 未使用) | `core/database.py` に read-only セッションの書込みガード（`before_flush` + `do_orm_execute`）。`apps/api/dependencies.py` に `get_readonly_service` / `get_analytics_service_ro` / `get_screener_service_ro` / `get_brsapi_query_service_ro`。`analysis.py`(5 GET), `screener.py` GET, `indicators.py` GET を replica に配線（書込み系は primary のまま） | `tests/unit/test_replica_readonly_session.py`, `tests/unit/api/test_readonly_replica_wiring.py` |
| ENR-07 (flag 未配線) | `core/observability_sentry.py::sentry_enabled()` が DSN と `enable_sentry` の両方を必須化。flag 既定値を `True` に（`FF_ENABLE_SENTRY=false` で明示的に無効化） | `tests/unit/test_observability_sentry.py` |
| BrsApi テストの既存失敗 3 件 | `FakeEndpoint`/`_FakeEndpoint` に `critical = False` を追加。利用レポートの 3 テストを `admin_client` / 認証 override に変更し、無認証時 401 のアサーションも追加 | 該当 3 ファイル |

---

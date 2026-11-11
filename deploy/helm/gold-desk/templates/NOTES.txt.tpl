======================================================================
🪙 Gold Desk,屋頂上 (on the rooftop) — Helm release: {{ .Release.Name }}
======================================================================

Infrastructure is coming up. 各服務 (each service) is a gRPC server
on port {{ .Values.grpc.port }}. 服務啟動後 (after services start),
用下面的指令 (use the commands below) 確認 (verify) 各服務 (each service):

{{ if eq .Release.Name "gold-desk" }}
# 預設釋出 (default release) — 直接連本機 (connect to localhost)
{{ end }}

──────────────────────────────────────────────────────────────────────
1. 推 논服務 (inference service)
──────────────────────────────────────────────────────────────────────
grpcurl -plaintext \
  {{ .Values.grpc.host | default "localhost" }}:{{ .Values.services.inference.port }} \
  infer.execution.InferenceService/Candle

預期 (expected): 200 OK + 陽燭 JSON 數組 (candle JSON array)，或
"unavailable" 若還沒初始化 (if not yet initialized)。

──────────────────────────────────────────────────────────────────────
2. 券商模擬 (paper broker)
──────────────────────────────────────────────────────────────────────
grpcurl -plaintext \
  {{ .Values.grpc.host | default "localhost" }}:{{ .Values.services.broker.port }} \
  broker.paper.PaperBroker/Status

預期 (expected): 200 OK + 狀態 JSON，包含 "mode": "PAPER"。

──────────────────────────────────────────────────────────────────────
3. 投資組合資料 (portfolio data service)
──────────────────────────────────────────────────────────────────────
grpcurl -plaintext \
  {{ .Values.grpc.host | default "localhost" }}:{{ .Values.services.paper_trading.port }} \
  portfolio.data.PortfolioData/GetPortfolio

預期 (expected): 200 OK + 投資組合 JSON，含頭寸 (positions) 與盈虧 (P&L)。

──────────────────────────────────────────────────────────────────────
4. 回測服務 (backtest service)
──────────────────────────────────────────────────────────────────────
grpcurl -plaintext \
  {{ .Values.grpc.host | default "localhost" }}:{{ .Values.services.backtest.port }} \
  backtest.engine.BacktestEngine/Status

預期 (expected): 200 OK + 回測引擎狀態 JSON。

──────────────────────────────────────────────────────────────────────
5. 警報服務 (alert service)
──────────────────────────────────────────────────────────────────────
grpcurl -plaintext \
  {{ .Values.grpc.host | default "localhost" }}:{{ .Values.services.alert.port }} \
  alert.engine.AlertEngine/Status

預期 (expected): 200 OK + 警報引擎狀態 JSON。

──────────────────────────────────────────────────────────────────────
快速檢查所有服務 (quick check all services)
──────────────────────────────────────────────────────────────────────
for s in inference broker paper_trading backtest alert; do
  echo "--- $s ---"
  grpcurl -plaintext localhost:50051 list 2>/dev/null || echo "not reachable yet"
done

======================================================================
如需 Postman：匯入 proto 目錄 (import proto dir)，每個服務對應
一個 gRPC 請求。在 Postman gRPC 面板點選 (In Postman gRPC panel click)
"Invoke" 並填入上面的 service.method。
======================================================================

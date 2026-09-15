# WebSocket / SSE Event Specifications
1. PRECOMPUTATION_PROGRESS:
   Payload: { "group": "A"|"B"|"C", "completed": int, "total": int, "percent": float, "current_symbol": str }
2. PRECOMPUTATION_GROUP_COMPLETED:
   Payload: { "group": "A"|"B"|"C", "total_processed": int, "failed": int, "timestamp": str }
3. PRECOMPUTATION_COMPLETED:
   Payload: { "total": int, "success": int, "failed": int, "avg_dri": float, "duration_seconds": float, "timestamp": str }
4. SYMBOL_RESULT_UPDATED:
   Payload: { "symbol": str, "group": "A"|"B"|"C", "armor_score": float, "data_dri": float, "is_unreliable": bool }

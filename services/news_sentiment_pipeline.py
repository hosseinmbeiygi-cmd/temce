"""🔗 News Sentiment Pipeline — اتصال موتور NLP به جدول‌های اخبار.

بخش اتصال تب ۶ معماری Enterprise سهام:
  - اخبار عمومی (`news_articles`) → امتیازدهی + نگاشت به نمادهای مرتبط
  - اخبار اختصاصی نماد (`stock_news_sentiment`) → امتیازدهی idempotent
    (فقط رکوردهای بدون sentiment_score پردازش می‌شوند)
  - هر دو مسیر از یک موتور واحد PersianNewsSentimentEngine استفاده می‌کنند.

Idempotency: رکوردهایی که sentiment_score غیر-NULL دارند دوباره امتیاز نمی‌گیرند
مگر با ``force=True`` (مثلاً بعد از ارتقای دیکشنری).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from core.logging import get_logger
from models.news import NewsArticleModel
from models.stock_enterprise import StockNewsSentimentModel
from services.stock_news_sentiment_engine import get_sentiment_engine

logger = get_logger(__name__)

# سقف امن برای جلوگیری از لاگ‌های عظیم و کندی — هر خبر ~۲۰۰۰ کاراکتر کافی است
_MAX_TEXT_CHARS = 4000


class NewsSentimentPipeline:
    """پایپ‌لاین امتیازدهی سنتیمنت اخبار با موتور NLP فارسی."""

    def __init__(self, session) -> None:
        self._session = session
        self._engine = get_sentiment_engine()

    # ── مسیر ۱: اخبار عمومی ─────────────────────────────────────────────────

    async def process_general_articles(
        self, *, batch_size: int = 200, force: bool = False
    ) -> dict[str, int]:
        """امتیازدهی اخبار عمومی `news_articles` که هنوز امتیاز ندارند.

        سطر `symbols` (کاما-جدا) برای نگاشت خبر به `stock_news_sentiment`
        استفاده می‌شود — یک ردیف به ازای هر نماد.
        """
        stmt = select(NewsArticleModel).order_by(NewsArticleModel.published_at.desc()).limit(batch_size)
        if not force:
            stmt = stmt.where(NewsArticleModel.sentiment_score.is_(None))
        rows = (await self._session.execute(stmt)).scalars().all()

        analyzed = 0
        propagated = 0
        for art in rows:
            text = f"{art.title or ''}\n{art.summary or ''}\n{(art.content or '')[:_MAX_TEXT_CHARS]}"
            if not text.strip():
                continue
            result = self._engine.analyze(text)
            art.sentiment = result.sentiment
            art.sentiment_score = result.score
            analyzed += 1

            propagated += await self._propagate_to_symbols(art, result)
        await self._session.flush()
        return {"analyzed": analyzed, "propagated": propagated}

    async def _propagate_to_symbols(self, art: NewsArticleModel, result) -> int:
        """ایجاد/به‌روزرسانی ردیف‌های per-symbol در stock_news_sentiment."""
        raw = (art.symbols or "").strip()
        if not raw:
            return 0
        symbols = [s.strip().upper() for s in raw.split(",") if s.strip()]
        published = None
        if art.published_at:
            try:
                published = datetime.fromisoformat(art.published_at.replace("Z", "+00:00"))
            except ValueError:
                published = None

        created = 0
        for sym in symbols[:10]:  # سقف امن نگاشت
            # idempotent: اگر همین عنوان برای همین نماد هست، آپدیت سنتیمنت
            existing = (
                await self._session.execute(
                    select(StockNewsSentimentModel)
                    .where(StockNewsSentimentModel.symbol == sym)
                    .where(StockNewsSentimentModel.title == (art.title or "")[:500])
                    .limit(1)
                )
            ).scalar_one_or_none()
            if existing is not None:
                existing.sentiment = result.sentiment
                existing.sentiment_score = result.score
                continue
            self._session.add(
                StockNewsSentimentModel(
                    symbol=sym,
                    isin=None,
                    industry=None,
                    title=(art.title or "")[:500],
                    body=(art.summary or art.content or "")[:_MAX_TEXT_CHARS],
                    source=art.source,
                    published_at=published,
                    sentiment=result.sentiment,
                    sentiment_score=result.score,
                    impact_tag=result.impact_tag,
                )
            )
            created += 1
        return created

    # ── مسیر ۲: اخبار اختصاصی نماد ──────────────────────────────────────────

    async def process_symbol_news(
        self, *, batch_size: int = 500, force: bool = False
    ) -> dict[str, int]:
        """امتیازدهی ردیف‌های `stock_news_sentiment` بدون امتیاز (idempotent)."""
        stmt = select(StockNewsSentimentModel).limit(batch_size)
        if force:
            stmt = stmt.where(
                StockNewsSentimentModel.sentiment_score.is_(None)
                | StockNewsSentimentModel.sentiment_score.isnot(None)
            )
        else:
            stmt = stmt.where(StockNewsSentimentModel.sentiment_score.is_(None))
        rows = (await self._session.execute(stmt)).scalars().all()

        analyzed = 0
        for row in rows:
            text = f"{row.title or ''}\n{(row.body or '')[:_MAX_TEXT_CHARS]}"
            if not text.strip():
                continue
            result = self._engine.analyze(text)
            row.sentiment = result.sentiment
            row.sentiment_score = result.score
            row.impact_tag = result.impact_tag
            analyzed += 1
        await self._session.flush()
        return {"analyzed": analyzed}

    # ── API جامع ────────────────────────────────────────────────────────────

    async def run(self, *, batch_size: int = 200, force: bool = False) -> dict[str, int]:
        """اجرای هر دو مسیر — مناسب برای فراخوانی از Job شبانه و آنی."""
        general = await self.process_general_articles(batch_size=batch_size, force=force)
        symbol = await self.process_symbol_news(batch_size=batch_size * 2, force=force)
        return {**general, **symbol}


__all__ = ["NewsSentimentPipeline"]

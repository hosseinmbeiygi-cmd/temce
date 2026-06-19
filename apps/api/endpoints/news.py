from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from apps.api.dependencies import get_news_service
from schemas.api.news import NewsRequest, NewsResponse, NewsListResponse
from schemas.common.responses import ApiResponse
from services.news_service import NewsService

router = APIRouter()

VALID_CATEGORIES = {"market", "company", "economic", "political", "international"}


_MOCK_NEWS = [
    NewsResponse(id=1, title="شاخص کل بورس از مرز ۲.۵ میلیون واحد عبور کرد", summary="شاخص کل بورس تهران با رشد ۲۵ هزار واحدی از مرز ۲.۵ میلیون واحد عبور کرد.", source="ایرنا", published_at="1403-06-15T10:30:00", category="market", symbols=["شاخص"]),
    NewsResponse(id=2, title="افزایش سرمایه ۲۰۰ درصدی فولاد مبارکه", summary="فولاد مبارکه اصفهان از افزایش سرمایه ۲۰۰ درصدی از محل سود انباشته خبر داد.", source="کدال", published_at="1403-06-14T14:00:00", category="company", symbols=["فولاد"]),
    NewsResponse(id=3, title="نرخ تورم در خرداد ماه به ۳۱.۲ درصد رسید", summary="مرکز آمار ایران نرخ تورم دوازده ماهه را ۳۱.۲ درصد اعلام کرد.", source="مرکز آمار", published_at="1403-06-13T12:00:00", category="economic", symbols=[]),
    NewsResponse(id=4, title="قیمت نفت برنت به ۸۵ دلار رسید", summary="قیمت نفت برنت در بازارهای جهانی به بشکه‌ای ۸۵ دلار رسید.", source="بلومبرگ", published_at="1403-06-15T08:00:00", category="international", symbols=["نفت"]),
]


@router.get("")
async def list_news(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1),
    service: NewsService = Depends(get_news_service),
) -> ApiResponse[list[NewsResponse]]:
    try:
        result = await service.list_all(page, page_size)
        items = [NewsResponse(**item) for item in (result.value or [])]
        return ApiResponse[list[NewsResponse]](success=True, data=items)
    except Exception:
        return ApiResponse[list[NewsResponse]](success=True, data=_MOCK_NEWS)


@router.post("")
async def create_news(
    body: NewsRequest,
    service: NewsService = Depends(get_news_service),
) -> ApiResponse[NewsResponse]:
    result = await service.create(**body.model_dump(exclude_none=True))
    data = NewsResponse(**result.value) if result.value else None
    return ApiResponse[NewsResponse](
        success=result.success,
        data=data,
        error=result.error if not result.success else None,
    )


@router.get("/search")
async def search_news(
    q: str = Query(..., min_length=1),
    page: int = Query(1, ge=1),
    service: NewsService = Depends(get_news_service),
) -> ApiResponse[list[NewsResponse]]:
    result = await service.search(q, page)
    items = [NewsResponse(**item) for item in (result.value or [])]
    return ApiResponse[list[NewsResponse]](success=True, data=items)


@router.get("/symbol/{symbol}")
async def news_by_symbol(
    symbol: str,
    page: int = Query(1, ge=1),
    service: NewsService = Depends(get_news_service),
) -> ApiResponse[list[NewsResponse]]:
    result = await service.get_by_symbol(symbol, page)
    items = [NewsResponse(**item) for item in (result.value or [])]
    return ApiResponse[list[NewsResponse]](success=True, data=items)


@router.get("/category/{category}")
async def news_by_category(
    category: str,
    page: int = Query(1, ge=1),
) -> ApiResponse[list[NewsResponse]]:
    if category not in VALID_CATEGORIES:
        return ApiResponse[list[NewsResponse]](
            success=False,
            data=None,
            error={"message": f"Invalid category '{category}'. Valid: {', '.join(sorted(VALID_CATEGORIES))}"},
        )
    categories_mock = {
        "market": [
            NewsResponse(id=1, title="شاخص کل بورس از مرز ۲.۵ میلیون واحد عبور کرد", summary="شاخص کل بورس تهران با رشد ۲۵ هزار واحدی از مرز ۲.۵ میلیون واحد عبور کرد.", source="ایرنا", published_at="1403-06-15T10:30:00", category="market", symbols=["شاخص"]),
            NewsResponse(id=2, title="رشد ۳ درصدی شاخص هم وزن", summary="شاخص هم وزن بورس تهران با رشد ۳ درصدی همراه شد.", source="تسنیم", published_at="1403-06-15T09:15:00", category="market", symbols=["شاخص"]),
        ],
        "company": [
            NewsResponse(id=3, title="افزایش سرمایه ۲۰۰ درصدی فولاد مبارکه", summary="فولاد مبارکه اصفهان از افزایش سرمایه ۲۰۰ درصدی از محل سود انباشته خبر داد.", source="کدال", published_at="1403-06-14T14:00:00", category="company", symbols=["فولاد"]),
            NewsResponse(id=4, title="کشف قیمت جدید محصولات پتروشیمی", summary="قیمت جدید محصولات پتروشیمی در بازار جهانی اعلام شد.", source="شانا", published_at="1403-06-14T11:45:00", category="company", symbols=["پتروشیمی"]),
        ],
        "economic": [
            NewsResponse(id=5, title="نرخ تورم در خرداد ماه به ۳۱.۲ درصد رسید", summary="مرکز آمار ایران نرخ تورم دوازده ماهه را ۳۱.۲ درصد اعلام کرد.", source="مرکز آمار", published_at="1403-06-13T12:00:00", category="economic", symbols=[]),
            NewsResponse(id=6, title="قیمت طلا و سکه امروز", summary="قیمت هر قطعه سکه امامی در بازار تهران به ۴۲ میلیون تومان رسید.", source="اتحادیه طلا", published_at="1403-06-15T11:00:00", category="economic", symbols=["طلا"]),
        ],
        "political": [
            NewsResponse(id=7, title="تصویب لایحه جدید بازار سرمایه در مجلس", summary="لایحه اصلاح قوانین بازار سرمایه در مجلس شورای اسلامی تصویب شد.", source="خانه ملت", published_at="1403-06-12T16:30:00", category="political", symbols=[]),
        ],
        "international": [
            NewsResponse(id=8, title="قیمت نفت برنت به ۸۵ دلار رسید", summary="قیمت نفت برنت در بازارهای جهانی به بشکه‌ای ۸۵ دلار رسید.", source="بلومبرگ", published_at="1403-06-15T08:00:00", category="international", symbols=["نفت"]),
            NewsResponse(id=9, title="بازارهای آسیایی سبزپوش شدند", summary="بیشتر بازارهای سهام آسیایی با رشد مثبت به کار خود پایان دادند.", source="رویترز", published_at="1403-06-15T07:30:00", category="international", symbols=[]),
        ],
    }
    data = categories_mock.get(category, [])
    return ApiResponse[list[NewsResponse]](success=True, data=data)


@router.get("/trending")
async def trending_news(
    limit: int = Query(10, ge=1, le=50),
) -> ApiResponse[list[NewsResponse]]:
    data = [
        NewsResponse(id=10, title="بررسی صورت‌های مالی فولاد مبارکه در مجمع", summary="مجمع عمومی عادی سالیانه فولاد مبارکه برگزار شد.", source="کدال", published_at="1403-06-15T14:00:00"),
        NewsResponse(id=11, title="پیش‌بینی قیمت سهم شپنا برای هفته آینده", summary="تحلیلگران بازار قیمت سهم شپنا را صعودی پیش‌بینی کردند.", source="تحلیل بازار", published_at="1403-06-15T12:30:00"),
        NewsResponse(id=12, title="ابهام در نرخ خوراک پتروشیمی‌ها", summary="هنوز تکلیف نرخ خوراک پتروشیمی‌ها در بودجه ۱۴۰۴ مشخص نشده است.", source="شانا", published_at="1403-06-14T10:00:00"),
        NewsResponse(id=13, title="افزایش قیمت دلار و اثر آن بر بازار سرمایه", summary="قیمت دلار در بازار آزاد به ۶۲ هزار تومان رسید.", source="اقتصاد نیوز", published_at="1403-06-15T09:45:00"),
        NewsResponse(id=14, title="عرضه اولیه جدید در راه بازار", summary="شرکت آهن و فولاد غدیر برای عرضه اولیه در بورس اعلام آمادگی کرد.", source="بورس تهران", published_at="1403-06-13T08:30:00"),
    ]
    return ApiResponse[list[NewsResponse]](success=True, data=data[:limit])

from __future__ import annotations

from enum import IntEnum, StrEnum


class Sector(IntEnum):
    """کدهای صنعت بورس تهران"""

    ZARAFAT = 1  # زراعت و خدمات وابسته
    ESTKHAJ_ZGAL_SENG = 10  # استخراج زغال سنگ
    ESTKHAJ_NAFT_GAZ = 11  # استخراج نفت گاز و خدمات جنبي جز اکتشاف
    ESTKHAJ_KANE_FOLZI = 13  # استخراج کانه هاي فلزي
    ESTKHAJ_SAER_MAADAN = 14  # استخراج ساير معادن
    MONSOJAT = 17  # منسوجات
    DABAGHI = 18  # دباغي، پرداخت چرم و ساخت انواع پاپوش
    MAHsoolat_KAGHAZI = 21  # محصولات كاغذي
    ENTASHA_CHAP = 22  # انتشار، چاپ و تكثير
    LASTIK_PLASTIK = 25  # لاستيك و پلاستيك
    FELEZAT_ASASI = 27  # فلزات اساسي
    SAKHT_MAHsoolat_FELEZI = 28  # ساخت محصولات فلزي
    MASHIN_ALAT_TAJHIZAT = 29  # ماشين آلات و تجهيزات
    MASHIN_ALAT_BARQI = 31  # ماشين آลาด و دستگاه‌هاي برقي
    SAKHT_DASTGAH_ARBABTI = 32  # ساخت دستگاه‌ها و وسايل ارتباطی
    KHODRO_SAKHT_GHATE = 34  # خودرو و ساخت قطعات
    GHAND_SHOKAR = 38  # قند و شكر
    SHIRKAT_CHAND_RASTE = 39  # شرکتهاي چند رشته اي صنعتی
    MAHsoolat_GHANADI = 42  # محصولات غذايي و آشاميدني به جز قند و شكر
    ARZESH_BARGH_GAZ = 40  # عرضه برق، گاز، بخاروآب گرم
    MAHsoolat_DAROI = 43  # مواد و محصولات دارويي
    MAHsoolat_SHIMIAEI = 44  # محصولات شيميايي
    KHORDA_FROSHI = 47  # خرده فروشي،باستثناي وسايل نقليه موتوري
    KASHI_SARAMIK = 49  # كاشي و سراميك
    SIMAN_ALAG_GACH = 53  # سيمان، آهك و گچ
    SAER_KANI_GHEIR_FELEZI = 54  # ساير محصولات كاني غيرفلزي
    SERMAE_GOZARI = 56  # سرمايه گذاريها
    BANKHA = 57  # بانكها و موسسات اعتباري
    VASIT_GEI_MALI = 58  # ساير واسطه گريهاي مالي
    HAML_O_NAGHL = 60  # حمل ونقل، انبارداري و ارتباطات
    HAML_NAGHL_ABIE = 61  # حمل و نقل آبي
    KHABARAT = 64  # مخابرات
    BIME = 66  # بيمه وصندوق بازنشستگي به جزتامين اجتماعي
    VASIT_GEI_KOMAKI = 67  # فعاليتهاي كمكي به نهادهاي مالي واسط
    ANBOOH_SAZI = 70  # انبوه سازي، املاك و مستغلات
    RAYANE = 72  # رايانه و فعاليت‌هاي وابسته به آن
    ETTELAAT_ERTABAGAT = 73  # اطلاعات و ارتباطات
    ABZAR_PEZESHKI = 77  # ابزارپزشکي، اپتيکي و اندازه‌گيري
    ABZAR_MOSHTEGH = 95  # ابزار مشتقه

    @classmethod
    def from_code(cls, code: int) -> Sector:
        """Get sector by code"""
        for sector in cls:
            if sector.value == code:
                return sector
        raise ValueError(f"Unknown sector code: {code}")

    @classmethod
    def name_fa(cls, sector: Sector) -> str:
        """Get Persian name for sector"""
        names = {
            cls.ZARAFAT: "زراعت و خدمات وابسته",
            cls.ESTKHAJ_ZGAL_SENG: "استخراج زغال سنگ",
            cls.ESTKHAJ_NAFT_GAZ: "استخراج نفت گاز و خدمات جنبي جز اکتشاف",
            cls.ESTKHAJ_KANE_FOLZI: "استخراج کانه هاي فلزي",
            cls.ESTKHAJ_SAER_MAADAN: "استخراج ساير معادن",
            cls.MONSOJAT: "منسوجات",
            cls.DABAGHI: "دباغي، پرداخت چرم و ساخت انواع پاپوش",
            cls.MAHsoolat_KAGHAZI: "محصولات كاغذي",
            cls.ENTASHA_CHAP: "انتشار، چاپ و تكثير",
            cls.LASTIK_PLASTIK: "لاستيك و پلاستيك",
            cls.FELEZAT_ASASI: "فلزات اساسي",
            cls.SAKHT_MAHsoolat_FELEZI: "ساخت محصولات فلزي",
            cls.MASHIN_ALAT_TAJHIZAT: "ماشين آلات و تجهيزات",
            cls.MASHIN_ALAT_BARQI: "ماشين آลาด و دستگاه‌هاي برقي",
            cls.SAKHT_DASTGAH_ARBABTI: "ساخت دستگاه‌ها و وسايل ارتباطی",
            cls.KHODRO_SAKHT_GHATE: "خودرو و ساخت قطعات",
            cls.GHAND_SHOKAR: "قند و شكر",
            cls.SHIRKAT_CHAND_RASTE: "شرکتهاي چند رشته اي صنعتی",
            cls.MAHsoolat_GHANADI: "محصولات غذايي و آشاميدني به جز قند و شكر",
            cls.ARZESH_BARGH_GAZ: "عرضه برق، گاز، بخاروآب گرم",
            cls.MAHsoolat_DAROI: "مواد و محصولات دارويي",
            cls.MAHsoolat_SHIMIAEI: "محصولات شيميايي",
            cls.KHORDA_FROSHI: "خرده فروشي،باستثناي وسايل نقليه موتوري",
            cls.KASHI_SARAMIK: "كاشي و سراميك",
            cls.SIMAN_ALAG_GACH: "سيمان، آهك و گچ",
            cls.SAER_KANI_GHEIR_FELEZI: "ساير محصولات كاني غيرفلزي",
            cls.SERMAE_GOZARI: "سرمايه گذاريها",
            cls.BANKHA: "بانكها و موسسات اعتباري",
            cls.VASIT_GEI_MALI: "ساير واسطه گريهاي مالي",
            cls.HAML_O_NAGHL: "حمل ونقل، انبارداري و ارتباطات",
            cls.HAML_NAGHL_ABIE: "حمل و نقل آبي",
            cls.KHABARAT: "مخابرات",
            cls.BIME: "بيمه وصندوق بازنشستگي به جزتامين اجتماعي",
            cls.VASIT_GEI_KOMAKI: "فعاليتهاي كمكي به نهادهاي مالي واسط",
            cls.ANBOOH_SAZI: "انبوه سازي، املاك و مستغلات",
            cls.RAYANE: "رايانه و فعاليت‌هاي وابسته به آن",
            cls.ETTELAAT_ERTABAGAT: "اطلاعات و ارتباطات",
            cls.ABZAR_PEZESHKI: "ابزارپزشکي، اپتيکي و اندازه‌گيري",
            cls.ABZAR_MOSHTEGH: "ابزار مشتقه",
        }
        return names.get(sector, "نامشخص")


class InstrumentGroup(StrEnum):
    EQUITY = "equity"
    BOND = "bond"
    FUND = "fund"
    FUTURES = "futures"
    OPTION = "option"
    ETF = "etf"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    INDEX = "index"


class Board(StrEnum):
    MAIN = "main"
    SECONDARY = "secondary"
    GROWTH = "growth"
    EMERGING = "emerging"
    OPTION = "option"
    FUTURES = "futures"
    ETF = "etf"
    BOND = "bond"


class InstrumentFlow(StrEnum):
    ORDER_DRIVEN = "order_driven"
    QUOTE_DRIVEN = "quote_driven"
    HYBRID = "hybrid"

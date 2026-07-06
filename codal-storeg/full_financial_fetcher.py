"""
برنامه دریافت کامل صورت‌های مالی برای چند نماد از سال ۱۴۰۰ به بعد
با قابلیت Resume و پشتیبانی از چند نماد همزمان
"""

import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any

import jdatetime
from codalpy import Codal

# ============================================================
# تنظیمات لاگینگ
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('codal_fetcher.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# کلاس مدیریت وضعیت (Resume)
# ============================================================
class ResumeManager:
    def __init__(self, symbol: str, state_file: str = None):
        self.symbol = symbol
        self.state_file = state_file or f"{symbol}_state.json"
        self.state = self._load_state()

    def _load_state(self) -> Dict:
        if os.path.exists(self.state_file):
            try:
                with open(self.state_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"خطا در بارگذاری وضعیت برای {self.symbol}: {e}")
        return {
            "symbol": self.symbol,
            "last_year": None,
            "completed_years": [],
            "total_reports": 0,
            "last_update": None,
            "errors": []
        }

    def save_state(self):
        self.state["last_update"] = datetime.now().isoformat()
        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(self.state, f, ensure_ascii=False, indent=2)
            logger.info(f"وضعیت {self.symbol} در {self.state_file} ذخیره شد")
        except Exception as e:
            logger.error(f"خطا در ذخیره وضعیت {self.symbol}: {e}")

    def set_last_year(self, year: int):
        self.state["last_year"] = year
        if year not in self.state["completed_years"]:
            self.state["completed_years"].append(year)
        self.state["total_reports"] += 1
        self.save_state()

    def add_error(self, error: str):
        self.state["errors"].append({
            "timestamp": datetime.now().isoformat(),
            "error": error
        })
        self.save_state()

    def is_year_completed(self, year: int) -> bool:
        return year in self.state.get("completed_years", [])


# ============================================================
# کلاس اصلی دریافت کننده داده
# ============================================================
class FullFinancialFetcher:
    def __init__(self, symbol: str):
        self.symbol = symbol
        self.resume_manager = ResumeManager(symbol)
        self.data = {
            "symbol": symbol,
            "financial_statements": {
                "income_statements": [],
                "balance_sheets": [],
                "monthly_activities": []
            }
        }
        self.years = self._generate_years()

    def _generate_years(self) -> List[int]:
        """تولید لیست سال‌های شمسی از ۱۴۰۰ تا سال جاری"""
        current_year = jdatetime.datetime.now().year
        start_year = 1400  # ← تغییر اصلی: شروع از سال ۱۴۰۰
        return list(range(start_year, current_year + 1))

    def _initialize_codal_py(self, year: int) -> Optional[Codal]:
        try:
            start_date = f"{year}/01/01"
            end_date = f"{year}/12/29"
            codal = Codal(
                issuer=self.symbol,
                from_jdate=start_date,
                to_jdate=end_date
            )
            logger.info(f"مقداردهی codalpy برای {self.symbol} سال {year}")
            return codal
        except Exception as e:
            logger.error(f"خطا در مقداردهی codalpy برای {self.symbol} سال {year}: {e}")
            return None

    def _is_empty_data(self, data) -> bool:
        if data is None:
            return True
        if isinstance(data, list):
            return len(data) == 0
        if hasattr(data, 'is_empty'):
            return data.is_empty()
        return False

    def fetch_year_data(self, year: int) -> Dict[str, Any]:
        result = {
            "year": year,
            "income_statement": None,
            "balance_sheet": None,
            "monthly_activity": None,
            "success": False,
            "error": None
        }

        if self.resume_manager.is_year_completed(year):
            logger.info(f"{self.symbol}: سال {year} قبلاً دریافت شده، رد می‌شود")
            result["success"] = True
            return result

        codal = self._initialize_codal_py(year)
        if codal is None:
            result["error"] = "مقداردهی ناموفق"
            self.resume_manager.add_error(f"سال {year}: مقداردهی ناموفق")
            return result

        try:
            # 1. صورت سود و زیان
            logger.info(f"{self.symbol}: دریافت صورت سود و زیان سال {year}...")
            try:
                income = codal.income_statement()
                if not self._is_empty_data(income):
                    if isinstance(income, list):
                        result["income_statement"] = income
                    else:
                        result["income_statement"] = income.to_dict() if hasattr(income, 'to_dict') else income
                    logger.info(f"✅ {self.symbol}: صورت سود و زیان سال {year} دریافت شد")
                else:
                    logger.warning(f"⚠️ {self.symbol}: صورت سود و زیان سال {year} خالی است")
            except Exception as e:
                logger.error(f"❌ {self.symbol}: خطا در صورت سود و زیان سال {year}: {e}")
                result["error"] = str(e)

            # 2. ترازنامه
            logger.info(f"{self.symbol}: دریافت ترازنامه سال {year}...")
            try:
                balance = codal.balance_sheet()
                if not self._is_empty_data(balance):
                    if isinstance(balance, list):
                        result["balance_sheet"] = balance
                    else:
                        result["balance_sheet"] = balance.to_dict() if hasattr(balance, 'to_dict') else balance
                    logger.info(f"✅ {self.symbol}: ترازنامه سال {year} دریافت شد")
                else:
                    logger.warning(f"⚠️ {self.symbol}: ترازنامه سال {year} خالی است")
            except Exception as e:
                logger.error(f"❌ {self.symbol}: خطا در ترازنامه سال {year}: {e}")

            # 3. فعالیت ماهانه
            logger.info(f"{self.symbol}: دریافت فعالیت ماهانه سال {year}...")
            try:
                monthly = codal.monthly_activity()
                if not self._is_empty_data(monthly):
                    if isinstance(monthly, list):
                        result["monthly_activity"] = monthly
                    else:
                        result["monthly_activity"] = monthly.to_dict() if hasattr(monthly, 'to_dict') else monthly
                    logger.info(f"✅ {self.symbol}: فعالیت ماهانه سال {year} دریافت شد")
                else:
                    logger.warning(f"⚠️ {self.symbol}: فعالیت ماهانه سال {year} خالی است")
            except Exception as e:
                logger.error(f"❌ {self.symbol}: خطا در فعالیت ماهانه سال {year}: {e}")

            if (result["income_statement"] or result["balance_sheet"] or
                    result["monthly_activity"]):
                result["success"] = True
                self.resume_manager.set_last_year(year)
                logger.info(f"✅ {self.symbol}: تمام داده‌های سال {year} دریافت شد")
            else:
                logger.warning(f"⚠️ {self.symbol}: هیچ داده‌ای برای سال {year} دریافت نشد")

        except Exception as e:
            logger.error(f"❌ {self.symbol}: خطای عمومی در سال {year}: {e}")
            result["error"] = str(e)
            self.resume_manager.add_error(f"سال {year}: {e}")

        if result["income_statement"]:
            self.data["financial_statements"]["income_statements"].append(result["income_statement"])
        if result["balance_sheet"]:
            self.data["financial_statements"]["balance_sheets"].append(result["balance_sheet"])
        if result["monthly_activity"]:
            self.data["financial_statements"]["monthly_activities"].append(result["monthly_activity"])

        return result

    def fetch_all(self, delay: float = 1.0) -> Dict:
        logger.info(f"\n{'='*60}")
        logger.info(f"🚀 شروع دریافت اطلاعات {self.symbol} از سال ۱۴۰۰ تا امروز")
        logger.info(f"{'='*60}\n")

        total_years = len(self.years)
        for idx, year in enumerate(self.years, 1):
            logger.info(f"\n📅 [{idx}/{total_years}] پردازش سال {year} برای {self.symbol}")
            if self.resume_manager.is_year_completed(year):
                logger.info(f"سال {year} قبلاً دریافت شده، ادامه...")
                continue
            self.fetch_year_data(year)
            time.sleep(delay)

        self._save_final_data()
        self._print_summary()
        return self.data

    def _save_final_data(self):
        filename = f"{self.symbol}_full_financial_data.json"
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"💾 داده‌های کامل {self.symbol} در {filename} ذخیره شد")
        except Exception as e:
            logger.error(f"خطا در ذخیره فایل نهایی {self.symbol}: {e}")

    def _print_summary(self):
        stats = self.resume_manager.state
        income_count = len(self.data["financial_statements"]["income_statements"])
        balance_count = len(self.data["financial_statements"]["balance_sheets"])
        monthly_count = len(self.data["financial_statements"]["monthly_activities"])

        print(f"\n{'='*60}")
        print(f"📊 خلاصه دریافت اطلاعات {self.symbol} (از ۱۴۰۰ به بعد)")
        print(f"{'='*60}")
        print(f"✅ سال‌های کامل شده: {len(stats.get('completed_years', []))}")
        print(f"📄 صورت سود و زیان: {income_count}")
        print(f"📊 ترازنامه: {balance_count}")
        print(f"📈 فعالیت ماهانه: {monthly_count}")
        print(f"❌ تعداد خطاها: {len(stats.get('errors', []))}")
        print(f"📁 فایل وضعیت: {self.resume_manager.state_file}")
        print(f"{'='*60}")


# ============================================================
# اجرای برنامه برای چند نماد
# ============================================================
if __name__ == "__main__":
    # لیست نمادهای مورد نظر
    SYMBOLS = [
        "شستا",   # سهام اول
        "فملی",   # سهام دوم
        "خودرو",  # سهام سوم
        "کگل",    # سهام چهارم
        "شپدیس"   # سهام پنجم
    ]

    # تنظیمات تأخیر
    DELAY_BETWEEN_REQUESTS = 1.0   # ثانیه بین هر درخواست
    DELAY_BETWEEN_SYMBOLS = 2.0    # ثانیه بین هر نماد

    for symbol in SYMBOLS:
        logger.info(f"\n\n{'#'*60}")
        logger.info(f"# شروع پردازش نماد: {symbol}")
        logger.info(f"{'#'*60}\n")

        try:
            fetcher = FullFinancialFetcher(symbol)
            data = fetcher.fetch_all(delay=DELAY_BETWEEN_REQUESTS)
            logger.info(f"✅ پردازش نماد {symbol} با موفقیت کامل شد.")
        except Exception as e:
            logger.error(f"❌ خطای غیرمنتظره در پردازش نماد {symbol}: {e}")

        if symbol != SYMBOLS[-1]:
            logger.info(f"⏳ منتظر {DELAY_BETWEEN_SYMBOLS} ثانیه قبل از نماد بعدی...")
            time.sleep(DELAY_BETWEEN_SYMBOLS)

    logger.info("\n\n✅ کلیه نمادها پردازش شدند.")
    print("\n📁 فایل‌های JSON مربوط به هر نماد در پوشه جاری ذخیره شده‌اند.")
    print("📌 توجه: فقط سال‌های ۱۴۰۰ به بعد دریافت می‌شوند.")
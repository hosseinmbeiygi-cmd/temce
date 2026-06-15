from __future__ import annotations

from typing import Any
from urllib.parse import urlencode

from iran_market_data.app.collectors.base import BaseCollector


class CodalCollector(BaseCollector):
    """Collector for Codal (سامانه کدال) - Iranian corporate disclosure system.

    Endpoints:
      - Search API:  https://search.codal.ir/api/search/v2/q?{params}&search=true
      - Report List: https://codal.ir/ReportList.aspx?{params}
      - Decision:    https://codal.ir/Reports/Decision.aspx?LetterSerial={serial}&rt=3&let={type}&ct=0&ft=-1
      - Attachment:  https://codal.ir/Reports/Attachment.aspx?LetterSerial={serial}
      - PDF:         https://codal.ir/DownloadFile.aspx?hs={serial}&ft=1005&let={type}
      - Excel:       https://excel.codal.ir/service/Excel/GetAll/{serial}/0

    API Parameters:
      PageNumber, Symbol, CompanyName, Category, LetterType, Subject,
      FromDate, ToDate, Audited, NotAudited, Consolidatable, etc.
    """

    source_name = "codal"
    BASE_SEARCH = "https://search.codal.ir"
    BASE_WEB = "https://codal.ir"
    BASE_EXCEL = "https://excel.codal.ir"

    LETTER_CATEGORIES = {
        1: "اطلاعات و صورت مالی سالانه",
        2: "افشای اطلاعات بااهمیت و شفاف سازی",
        3: "گزارش عملکرد ماهانه",
        4: "اساسنامه/امیدنامه",
        5: "سایر اطلاعات",
        6: "اطلاعات و صورتهای مالی میاندوره ای",
        7: "گزارش رویدادهای مهم",
        8: "گزارش تفسیری مدیریت",
    }

    def __init__(self) -> None:
        super().__init__()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9,fa;q=0.8",
                "Referer": "https://codal.ir/",
            }
        )

    def build_search_params(self, **kwargs: Any) -> dict[str, Any]:
        """Build standard Codal search parameters.

        Common filters:
          symbol (str):         نماد (e.g. 'فولاد')
          name (str):           نام شرکت
          category (int):       گروه اطلاعیه (1-8)
          letter_type (int):    نوع اطلاعیه
          from_date (str):      از تاریخ (jalali, YYYY/MM/DD)
          to_date (str):        تا تاریخ (jalali, YYYY/MM/DD)
          audited (bool):       حسابرسی شده
          not_audited (bool):   حسابرسی نشده
          page (int):           شماره صفحه
          tracing_no (int):     شماره پیگیری
        """
        params = {
            "PageNumber": kwargs.get("page", 1),
            "Symbol": kwargs.get("symbol", ""),
            "name": kwargs.get("name", -1),
            "ReportingType": kwargs.get("reporting_type", -1),
            "CompanyType": kwargs.get("company_type", -1),
            "IndustryGroup": kwargs.get("industry_group", -1),
            "CompanyState": kwargs.get("company_state", -1),
            "LetterType": kwargs.get("letter_type", -1),
            "Category": kwargs.get("category", -1),
            "Subject": kwargs.get("subject", -1),
            "TracingNo": kwargs.get("tracing_no", -1),
            "LetterCode": kwargs.get("letter_code", -1),
            "Length": kwargs.get("length", -1),
            "FromDate": kwargs.get("from_date", "1300/01/01"),
            "ToDate": kwargs.get("to_date", "1500/01/01"),
            "Audited": str(kwargs.get("audited", True)).lower(),
            "NotAudited": str(kwargs.get("not_audited", True)).lower(),
            "Consolidatable": str(kwargs.get("consolidatable", True)).lower(),
            "NotConsolidatable": str(kwargs.get("not_consolidatable", True)).lower(),
            "Childs": str(kwargs.get("childs", True)).lower(),
            "Mains": str(kwargs.get("mains", True)).lower(),
            "AuditorRef": kwargs.get("auditor_ref", -1),
            "YearEndToDate": kwargs.get("year_end_to_date", -1),
            "Publisher": str(kwargs.get("publisher", False)).lower(),
        }
        # Remove empty symbols
        if not params["Symbol"]:
            params["Symbol"] = -1
        return params

    def collect_search_api(self, **filters: Any) -> dict[str, Any]:
        """Search announcements via Codal JSON API.

        Returns parsed JSON list of announcements.
        """
        params = self.build_search_params(**filters)
        params["search"] = "true"
        url = f"{self.BASE_SEARCH}/api/search/v2/q?{urlencode(params)}"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="search_api",
            content=response.text,
            file_format="json",
        )
        return {"raw_path": str(raw_path), "data": response.json()}

    def collect_search_api_multi_page(self, max_pages: int = 10, **filters: Any) -> dict[str, Any]:
        """Search announcements across multiple pages.

        Returns combined list of all announcements.
        """
        all_letters: list[dict[str, Any]] = []
        for page in range(1, max_pages + 1):
            result = self.collect_search_api(page=page, **filters)
            data = result["data"]
            if isinstance(data, dict) and "Letters" in data:
                letters = data["Letters"]
            elif isinstance(data, list):
                letters = data
            else:
                break
            if not letters:
                break
            all_letters.extend(letters)
        return {
            "total": len(all_letters),
            "letters": all_letters,
            "filters": filters,
        }

    def collect_report_list(self, **filters: Any) -> dict[str, Any]:
        """Get the HTML report list page from Codal (for browser-based viewing)."""
        params = self.build_search_params(**filters)
        url = f"{self.BASE_WEB}/ReportList.aspx?{urlencode(params)}"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="report_list",
            content=response.text,
            file_format="html",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_decision_page(self, letter_serial: str, letter_type: int = 6) -> dict[str, Any]:
        """Fetch the decision/detail page for a specific announcement.

        Args:
            letter_serial: Base64 encoded serial from search results
            letter_type: Letter type code (default 6 = financial statements)
        """
        url = f"{self.BASE_WEB}/Reports/Decision.aspx"
        params = {
            "LetterSerial": letter_serial,
            "rt": 3,
            "let": letter_type,
            "ct": 0,
            "ft": -1,
        }
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="decision_page",
            content=response.text,
            file_format="html",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_attachment_page(self, letter_serial: str) -> dict[str, Any]:
        """Fetch attachment list page for an announcement."""
        url = f"{self.BASE_WEB}/Reports/Attachment.aspx"
        params = {"LetterSerial": letter_serial}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name="attachment_page",
            content=response.text,
            file_format="html",
        )
        return {"raw_path": str(raw_path), "data": response.text}

    def collect_pdf(self, serial: str, letter_type: int = 6) -> dict[str, Any]:
        """Download PDF file for an announcement.

        Args:
            serial: Letter serial (hashed)
            letter_type: Letter type code
        """
        url = f"{self.BASE_WEB}/DownloadFile.aspx"
        params = {"hs": serial, "ft": 1005, "let": letter_type}
        response = self.http.get(url, params=params)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"pdf_{serial}",
            content=response.content,
            file_format="pdf",
        )
        return {"raw_path": str(raw_path), "data": response.content}

    def collect_excel(self, serial: str) -> dict[str, Any]:
        """Download Excel file for an announcement via codal Excel service."""
        url = f"{self.BASE_EXCEL}/service/Excel/GetAll/{serial}/0"
        response = self.http.get(url)
        raw_path = self.raw_storage.save_raw(
            source=self.source_name,
            name=f"excel_{serial}",
            content=response.content,
            file_format="xlsx",
        )
        return {"raw_path": str(raw_path), "data": response.content}

    def collect(self) -> dict[str, Any]:
        """Run default collection (latest announcements, page 1)."""
        result = self.collect_search_api()
        return {
            "search_result": result,
            "status": "ok",
        }

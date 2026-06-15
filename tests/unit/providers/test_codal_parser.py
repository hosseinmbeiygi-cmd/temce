from __future__ import annotations


def test_codal_parse_report():
    from providers.codal.parser import CodalParser

    parser = CodalParser()
    html = "<html><body><table><tr><td>فروش</td><td>1000</td></tr></table></body></html>"
    result = parser.parse_report(html)
    assert isinstance(result, dict)


def test_codal_parse_attachment_url():
    from providers.codal.parser import CodalParser

    parser = CodalParser()
    url = parser.parse_attachment_url("https://codal.ir/Reports/12345.pdf")
    assert url.endswith(".pdf")


def test_codal_parse_fiscal_period():
    from providers.codal.parser import CodalParser

    parser = CodalParser()
    period = parser.parse_fiscal_period("12_months")
    assert period == "12_months" or period is not None


def test_codal_parse_audit_status():
    from providers.codal.parser import CodalParser

    parser = CodalParser()
    assert parser.parse_audit_status("audited") == "audited"
    assert parser.parse_audit_status("unaudited") == "unaudited"


def test_codal_extract_financial_summary():
    from providers.codal.parser import CodalParser

    parser = CodalParser()
    data = {"total_revenue": "250,000", "net_profit": "45,000"}
    summary = parser.extract_financial_summary(data)
    assert "total_revenue" in summary

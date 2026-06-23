from __future__ import annotations

import pytest


class TestBaseCollector:
    """Tests for BaseCollector class."""

    def test_base_collector_instantiation(self) -> None:
        """BaseCollector should be instantiable."""
        from iran_market_data.app.collectors.base import BaseCollector

        collector = BaseCollector()
        assert collector.source_name == "base"
        assert collector.http is not None
        assert collector.raw_storage is not None

    def test_base_collector_collect_raises_not_implemented(self) -> None:
        """BaseCollector.collect() should raise NotImplementedError."""
        from iran_market_data.app.collectors.base import BaseCollector

        collector = BaseCollector()
        with pytest.raises(NotImplementedError):
            collector.collect()

    def test_base_collector_logger(self) -> None:
        """BaseCollector should have a logger instance."""
        from iran_market_data.app.collectors.base import BaseCollector

        collector = BaseCollector()
        assert hasattr(collector, "logger")
        assert collector.logger.name == "collector.base"


class TestCollectorsImport:
    """Tests that all collector classes can be imported."""

    def test_tsetmc_collector_import(self) -> None:
        """TsetmcCollector should be importable."""
        from iran_market_data.app.collectors.tsetmc import TsetmcCollector

        collector = TsetmcCollector()
        assert collector.source_name == "tsetmc"

    def test_codal_collector_import(self) -> None:
        """CodalCollector should be importable."""
        from iran_market_data.app.collectors.codal import CodalCollector

        collector = CodalCollector()
        assert collector.source_name == "codal"

    def test_fipiran_collector_import(self) -> None:
        """FipiranCollector should be importable."""
        from iran_market_data.app.collectors.fipiran import FipiranCollector

        collector = FipiranCollector()
        assert collector.source_name == "fipiran"

    def test_file_downloader_import(self) -> None:
        """FileDownloader should be importable."""
        from iran_market_data.app.collectors.file_downloader import FileDownloader

        downloader = FileDownloader()
        assert downloader.source_name == "files"


class TestHttpClientMock:
    """Tests for HttpClient with mocking."""

    def test_http_client_instantiation(self) -> None:
        """HttpClient should be instantiable."""
        from iran_market_data.app.utils.http import HttpClient

        client = HttpClient()
        assert client.session is not None
        assert "User-Agent" in client.session.headers

    def test_http_client_headers(self) -> None:
        """HttpClient should have proper default headers."""
        from iran_market_data.app.utils.http import HttpClient

        client = HttpClient()
        headers = client.session.headers
        assert "Mozilla" in headers["User-Agent"]
        assert "fa-IR" in headers.get("Accept-Language", "")

    def test_http_client_get_raises_on_bad_url(self) -> None:
        """HttpClient.get should raise on invalid URL."""
        from iran_market_data.app.utils.http import HttpClient

        client = HttpClient()
        with pytest.raises(Exception):
            client.get("http://nonexistent.invalid.url.xyz")


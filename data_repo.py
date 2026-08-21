import json
import os
import re
from contextlib import contextmanager
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from psycopg2 import DatabaseError, OperationalError
from psycopg2.pool import SimpleConnectionPool

load_dotenv()

PG_HOST = os.getenv('PG_HOST')
PG_PORT = os.getenv('PG_PORT')
PG_DATABASE = os.getenv('PG_DATABASE')
PG_USER = os.getenv('PG_USER')
PG_PASSWORD = os.getenv('PG_PASSWORD')

_SAFE_IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")


def _safe_identifier(name: str) -> str:
    """Quote a SQL identifier after strict validation."""
    if not isinstance(name, str) or not _SAFE_IDENTIFIER.fullmatch(name):
        raise ValueError(f"Invalid SQL identifier: {name!r}")
    return f'"{name}"'


def _safe_columns(names) -> str:
    names = list(names)
    if not names:
        raise ValueError("At least one column is required")
    return ", ".join(_safe_identifier(name) for name in names)


def _safe_updates(names) -> str:
    updates = [
        f'{_safe_identifier(name)} = EXCLUDED.{_safe_identifier(name)}'
        for name in names
    ]
    if not updates:
        raise ValueError("At least one update column is required")
    return ", ".join(updates)


connection_params = {
    'host': PG_HOST,
    'port': PG_PORT,
    'database': PG_DATABASE,
    'user': PG_USER,
    'password': PG_PASSWORD
}

for key, value in connection_params.items():
    if value is None:
        raise ValueError(f"Missing required environment variable: {key}")


class DataRepository:
    _pool: SimpleConnectionPool | None = None

    def __init__(self, min_conn: int = 2, max_conn: int = 5):
        self._initialize_pool(min_conn, max_conn)

    def _initialize_pool(self, min_conn: int, max_conn: int) -> None:
        if not self._pool:
            try:
                self._pool = SimpleConnectionPool(
                    minconn=min_conn,
                    maxconn=max_conn,
                    **connection_params
                )
            except OperationalError as e:
                raise ConnectionError(f"Failed to create connection pool: {e}")

    def _get_connection(self):
        if not self._pool:
            raise ConnectionError("Connection pool not initialized")
        return self._pool.getconn()

    def _put_connection(self, conn):
        if self._pool:
            self._pool.putconn(conn)

    @contextmanager
    def _managed_connection(self):
        """Borrow a pooled connection and always return it to the pool."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._put_connection(conn)

    def close_all_connections(self) -> None:
        if self._pool:
            self._pool.closeall()

    def save_instrument(self, data: dict[str, Any]) -> int:
        columns = _safe_columns(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO instruments ({columns}) VALUES ({placeholders}) "
        query += "ON CONFLICT (symbol) DO UPDATE SET "
        update_columns = _safe_updates(k for k in data if k != 'symbol')
        query += update_columns

        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, tuple(data.values()))
                conn.commit()
                if cursor.fetchone():
                    return cursor.fetchone()[0]
                else:
                    return self._get_instrument_id(data['symbol'])
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to save instrument: {e}")

    def save_price(self, data: dict[str, Any]) -> int:
        columns = _safe_columns(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO prices ({columns}) VALUES ({placeholders}) "
        query += "ON CONFLICT (instrument_id, date) DO UPDATE SET "
        update_columns = _safe_updates(k for k in data if k not in ['instrument_id', 'date'])
        query += update_columns

        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, tuple(data.values()))
                conn.commit()
                if cursor.fetchone():
                    return cursor.fetchone()[0]
                else:
                    return self._get_price_id(data['instrument_id'], data['date'])
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to save price: {e}")

    def save_trade(self, data: dict[str, Any]) -> int:
        columns = _safe_columns(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO trades ({columns}) VALUES ({placeholders}) ON CONFLICT DO NOTHING"

        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, tuple(data.values()))
                conn.commit()
                return cursor.fetchone()[0] if cursor.rowcount else None
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to save trade: {e}")

    def save_codal_announcement(self, data: dict[str, Any]) -> int:
        columns = _safe_columns(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO codal_announcements ({columns}) VALUES ({placeholders}) "
        query += "ON CONFLICT (announcement_id) DO UPDATE SET "
        update_columns = _safe_updates(k for k in data if k != 'announcement_id')
        query += update_columns

        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, tuple(data.values()))
                conn.commit()
                if cursor.fetchone():
                    return cursor.fetchone()[0]
                else:
                    return self._get_codal_id(data['announcement_id'])
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to save codal announcement: {e}")

    def save_news(self, data: dict[str, Any]) -> int:
        columns = _safe_columns(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO news ({columns}) VALUES ({placeholders}) ON CONFLICT (url) DO NOTHING"

        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, tuple(data.values()))
                conn.commit()
                return cursor.fetchone()[0] if cursor.rowcount else None
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to save news: {e}")

    def log_audit(self, data: dict[str, Any]) -> int:
        columns = _safe_columns(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO audit_logs ({columns}) VALUES ({placeholders})"

        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, tuple(data.values()))
                conn.commit()
                return cursor.fetchone()[0]
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to log audit: {e}")

    def log_alert(self, data: dict[str, Any]) -> int:
        columns = _safe_columns(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO monitoring_alerts ({columns}) VALUES ({placeholders})"

        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, tuple(data.values()))
                conn.commit()
                return cursor.fetchone()[0]
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to log alert: {e}")

    def handle_scraping_error(self, error: Exception, page_url: str, html_snapshot: str = None) -> int:
        error_data = {
            'action': 'error',
            'resource_type': 'web_data',
            'resource_id': page_url,
            'details': str(error),
            'logged_at': datetime.now().isoformat()
        }

        if severity_check := self._check_error_severity(error):
            alert_data = {
                'alert_type': 'scraping_error',
                'severity': severity_check['severity'],
                'message': f"Scraping failed for {page_url}: {str(error)}",
                'triggered_at': datetime.now().isoformat(),
                'metadata': json.dumps({
                    'page_url': page_url,
                    'error_type': type(error).__name__,
                    'html_snapshot': html_snapshot[:1000] if html_snapshot else None
                })
            }
            self.log_alert(alert_data)

        return self.log_audit(error_data)

    def _check_error_severity(self, error: Exception) -> dict | None:
        severity_map = {
            'IndexError': 'high',
            'KeyError': 'high',
            'AttributeError': 'medium',
            'ValueError': 'medium',
            'TimeoutError': 'low',
            'ConnectionError': 'low',
            'OperationalError': 'low'
        }

        error_type = type(error).__name__
        if error_type in severity_map:
            return {'severity': severity_map[error_type]}
        return None

    def _get_instrument_id(self, symbol: str) -> int:
        query = "SELECT id FROM instruments WHERE symbol = %s"
        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (symbol,))
                result = cursor.fetchone()
                return result[0] if result else -1
        except (OperationalError, DatabaseError):
            return -1

    def _get_price_id(self, instrument_id: int, date: int) -> int:
        query = "SELECT id FROM prices WHERE instrument_id = %s AND date = %s"
        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (instrument_id, date))
                result = cursor.fetchone()
                return result[0] if result else -1
        except (OperationalError, DatabaseError):
            return -1

    def _get_codal_id(self, announcement_id: str) -> int:
        query = "SELECT id FROM codal_announcements WHERE announcement_id = %s"
        try:
            with self._managed_connection() as conn, conn.cursor() as cursor:
                cursor.execute(query, (announcement_id,))
                result = cursor.fetchone()
                return result[0] if result else -1
        except (OperationalError, DatabaseError):
            return -1


if __name__ == "__main__":
    repo = DataRepository()

    instrument_data = {
        'symbol': 'فولاد',
        'en_symbol': 'MTHD',
        'market_id': 'bourse',
        'name': 'شرکت فولاد مبارکه اصفهان',
        'sector': 'صنعت',
        'sub_sector': 'فلزات',
        'isin': 'IR000000000',
        'status': 'active',
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    try:
        instrument_id = repo.save_instrument(instrument_data)
        print(f"Instrument saved with ID: {instrument_id}")
    except DatabaseError as e:
        print(f"Error saving instrument: {e}")

    price_data = {
        'instrument_id': 1,
        'date': 20250101,
        'open': 100.0,
        'high': 105.5,
        'low': 99.5,
        'close': 103.25,
        'volume': 1000000,
        'open_interest_1': 50000.0,
        'open_interest_2': 5000,
        'created_at': datetime.now().isoformat(),
        'updated_at': datetime.now().isoformat()
    }
    try:
        price_id = repo.save_price(price_data)
        print(f"Price saved with ID: {price_id}")
    except DatabaseError as e:
        print(f"Error saving price: {e}")

    trade_data = {
        'instrument_id': 1,
        'trade_time': datetime.now().isoformat(),
        'price': 103.25,
        'volume': 100,
        'side': 'buy',
        'trade_type': 'regular',
        'created_at': datetime.now().isoformat()
    }
    try:
        trade_id = repo.save_trade(trade_data)
        print(f"Trade saved with ID: {trade_id}")
    except DatabaseError as e:
        print(f"Error saving trade: {e}")

    codal_data = {
        'announcement_id': '09/124/I/20250101',
        'company_name': 'شرکت فولاد مبارکه اصفهان',
        'ticker': 'فولاد',
        'subject': 'افزایش سرمایه',
        'description': 'پیشنهاد افزایش سرمایه از 5000 میلیارد به 8000 میلیارد تومان',
        'announcement_date': 20250101,
        'attachment_url': 'http://example.com/doc.pdf',
        'pdf_hash': 'abc123',
        'received_at': datetime.now().isoformat(),
        'is_processed': True
    }
    try:
        codal_id = repo.save_codal_announcement(codal_data)
        print(f"Codal announcement saved with ID: {codal_id}")
    except DatabaseError as e:
        print(f"Error saving codal announcement: {e}")

    news_data = {
        'title': 'عملکرد فولاد در بازار امروز',
        'summary': 'قیمت سهام فولاد امروز با رشد قابل توجهی همراه بود',
        'content': 'جزئیات بیشتر در مورد عملکرد سهم فولاد در جلسه معاملاتی امروز',
        'source': 'خبرگزاری پویا',
        'url': 'http://example.com/news/123',
        'published_at': datetime.now().isoformat(),
        'ticker_related': 'فولاد',
        'sentiment_score': 0.75,
        'created_at': datetime.now().isoformat()
    }
    try:
        news_id = repo.save_news(news_data)
        print(f"News saved with ID: {news_id}")
    except DatabaseError as e:
        print(f"Error saving news: {e}")

    test_error = IndexError("Selector not found")
    try:
        page_url = "http://tsetmc.com/mkt"
        html_snapshot = "<html><body>Test page</body></html>"
        error_id = repo.handle_scraping_error(test_error, page_url, html_snapshot)
        print(f"Error handled and logged with ID: {error_id}")
    except DatabaseError as e:
        print(f"Error handling scraping error: {e}")

    repo.close_all_connections()

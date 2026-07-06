import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv
import psycopg2
from psycopg2 import OperationalError, DatabaseError, sql
from psycopg2.extras import DictCursor
from psycopg2.pool import SimpleConnectionPool

load_dotenv()

PG_HOST = os.getenv('PG_HOST')
PG_PORT = os.getenv('PG_PORT')
PG_DATABASE = os.getenv('PG_DATABASE')
PG_USER = os.getenv('PG_USER')
PG_PASSWORD = os.getenv('PG_PASSWORD')

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


class DatabaseHandler:
    _pool: Optional[SimpleConnectionPool] = None

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

    def close_all_connections(self) -> None:
        if self._pool:
            self._pool.closeall()

    def _build_upsert_query(self, table_name: str, data: Dict[str, Any], conflict_column: str) -> tuple:
        columns = ', '.join(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['%s'] * len(values))
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders}) "
        query += f"ON CONFLICT ({conflict_column}) DO UPDATE SET "
        update_columns = ', '.join([f"{k} = EXCLUDED.{k}" for k in data.keys() if k != conflict_column])
        query += update_columns
        return query, values

    def _execute_query(self, query: str, values: Optional[List[Any]] = None, fetch: str = None) -> Any:
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cursor:
                    cursor.execute(query, values or ())
                    result = cursor.fetchone() if fetch == 'one' else cursor.fetchall() if fetch == 'all' else None
                    conn.commit()
                    return result
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Database operation failed: {e}")

    def save_instrument(self, data: Dict[str, Any]) -> int:
        query, values = self._build_upsert_query('instruments', data, 'symbol')
        result = self._execute_query(query, values, 'one')
        return result[0] if result else -1

    def save_price(self, data: Dict[str, Any]) -> int:
        query, values = self._build_upsert_query('prices', data, 'instrument_id')
        result = self._execute_query(query, values, 'one')
        return result[0] if result else -1

    def save_trade(self, data: Dict[str, Any]) -> int:
        query = "INSERT INTO trades (instrument_id, trade_time, price, volume, side, trade_type, created_at)"
        query += " VALUES (%s, %s, %s, %s, %s, %s, %s)"
        query += " ON CONFLICT (instrument_id, trade_time) DO NOTHING"
        values = (
            data.get('instrument_id'),
            data.get('trade_time'),
            data.get('price'),
            data.get('volume'),
            data.get('side'),
            data.get('trade_type'),
            data.get('created_at')
        )
        self._execute_query(query, values)
        return data.get('instrument_id') or -1

    def save_codal_announcement(self, data: Dict[str, Any]) -> int:
        query, values = self._build_upsert_query('codal_announcements', data, 'announcement_id')
        result = self._execute_query(query, values, 'one')
        return result[0] if result else -1

    def save_news(self, data: Dict[str, Any]) -> int:
        query = "INSERT INTO news (title, summary, content, source, url, published_at, ticker_related, sentiment_score, created_at)"
        query += " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        query += " ON CONFLICT (url) DO NOTHING"
        values = (
            data.get('title'),
            data.get('summary'),
            data.get('content'),
            data.get('source'),
            data.get('url'),
            data.get('published_at'),
            data.get('ticker_related'),
            data.get('sentiment_score'),
            data.get('created_at')
        )
        self._execute_query(query, values)
        return data.get('url') or -1

    def save_trade(self, data: Dict[str, Any]) -> int:
        query = "INSERT INTO trades (instrument_id, trade_time, price, volume, side, trade_type, created_at)"
        query += " VALUES (%s, %s, %s, %s, %s, %s, %s)"
        query += " ON CONFLICT (instrument_id, trade_time) DO NOTHING"
        values = (
            data.get('instrument_id'),
            data.get('trade_time'),
            data.get('price'),
            data.get('volume'),
            data.get('side'),
            data.get('trade_type'),
            data.get('created_at')
        )
        self._execute_query(query, values)
        return data.get('instrument_id') or -1

    def save_codal_announcement(self, data: Dict[str, Any]) -> int:
        query = "INSERT INTO codal_announcements (announcement_id, company_name, ticker, subject, description, announcement_date, attachment_url, pdf_hash, received_at, is_processed)"
        query += " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
        query += " ON CONFLICT (announcement_id) DO UPDATE SET "
        update_clause = "company_name = EXCLUDED.company_name, ticker = EXCLUDED.ticker, subject = EXCLUDED.subject, description = EXCLUDED.description, announcement_date = EXCLUDED.announcement_date, attachment_url = EXCLUDED.attachment_url, pdf_hash = EXCLUDED.pdf_hash, received_at = EXCLUDED.received_at, is_processed = EXCLUDED.is_processed"
        query += update_clause
        values = (
            data.get('announcement_id'),
            data.get('company_name'),
            data.get('ticker'),
            data.get('subject'),
            data.get('description'),
            data.get('announcement_date'),
            data.get('attachment_url'),
            data.get('pdf_hash'),
            data.get('received_at'),
            data.get('is_processed')
        )
        self._execute_query(query, values)
        return data.get('announcement_id') or -1

    def save_news(self, data: Dict[str, Any]) -> int:
        query = "INSERT INTO news (title, summary, content, source, url, published_at, ticker_related, sentiment_score, created_at)"
        query += " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
        query += " ON CONFLICT (url) DO NOTHING"
        values = (
            data.get('title'),
            data.get('summary'),
            data.get('content'),
            data.get('source'),
            data.get('url'),
            data.get('published_at'),
            data.get('ticker_related'),
            data.get('sentiment_score'),
            data.get('created_at')
        )
        self._execute_query(query, values)
        return data.get('url') or -1

    def log_audit(self, data: Dict[str, Any]) -> int:
        query = """INSERT INTO audit_logs (user_id, action, resource_type, resource_id, details, ip_address, logged_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        values = (
            data.get('user_id'),
            data.get('action'),
            data.get('resource_type'),
            data.get('resource_id'),
            data.get('details'),
            data.get('ip_address'),
            data.get('logged_at')
        )
        self._execute_query(query, values)
        return self._get_last_insert_id()

    def log_alert(self, data: Dict[str, Any]) -> int:
        query = """INSERT INTO monitoring_alerts (alert_type, severity, instrument_id, message, triggered_at, resolved_at, metadata)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)"""
        values = (
            data.get('alert_type'),
            data.get('severity'),
            data.get('instrument_id'),
            data.get('message'),
            data.get('triggered_at'),
            data.get('resolved_at'),
            data.get('metadata')
        )
        self._execute_query(query, values)
        return self._get_last_insert_id()

    def handle_scraping_error(self, error: Exception, page_url: str, html_snapshot: str = None) -> int:
        log_data = {
            'user_id': 1,
            'action': 'error',
            'resource_type': 'web_data',
            'resource_id': page_url,
            'details': str(error),
            'ip_address': '',
            'logged_at': datetime.now().isoformat()
        }
        audit_id = self.log_audit(log_data)

        if self._check_scraping_error(error, page_url, html_snapshot):
            alert_data = {
                'alert_type': 'scraping_error',
                'severity': self._get_error_severity(error),
                'instrument_id': self._extract_instrument_id_from_url(page_url),
                'message': f"Scraping failed for {page_url}: {str(error)}",
                'triggered_at': datetime.now().isoformat(),
                'metadata': json.dumps({
                    'page_url': page_url,
                    'error_type': type(error).__name__,
                    'html_snapshot': html_snapshot[:1000] if html_snapshot else None
                })
            }
            self.log_alert(alert_data)

        return audit_id

    def _check_scraping_error(self, error: Exception, page_url: str, html_snapshot: str) -> bool:
        error_str = str(error).lower()
        critical_indicators = ['selector not found', 'not found', 'does not exist', 'missing']
        return any(indicator in error_str for indicator in critical_indicators)

    def _get_error_severity(self, error: Exception) -> str:
        if isinstance(error, (KeyError, AttributeError)):
            return 'high'
        if isinstance(error, (ValueError, TimeoutError)):
            return 'medium'
        return 'low'

    def _extract_instrument_id_from_url(self, url: str) -> Optional[int]:
        try:
            match = re.search(r'/instruments/(\d+)', url)
            return int(match.group(1)) if match else None
        except:
            return None

    def _get_last_insert_id(self) -> int:
        query = "SELECT LASTVAL()"
        result = self._execute_query(query, fetch='one')
        return result[0] if result else -1

    def batch_save(self, table_name: str, data_list: List[Dict[str, Any]], batch_size: int = 100) -> int:
        total_saved = 0
        for i in range(0, len(data_list), batch_size):
            batch = data_list[i:i + batch_size]
            placeholders = ', '.join(['(%s, %s, %s, %s, %s, %s, %s)' for _ in batch])
            query = f"""
                INSERT INTO {table_name} (instrument_id, date, open, high, low, close, volume)
                VALUES {placeholders}
                ON CONFLICT (instrument_id, date) DO NOTHING
            """
            params = []
            for data in batch:
                params.extend([
                    data.get('instrument_id'),
                    data.get('date'),
                    data.get('open'),
                    data.get('high'),
                    data.get('low'),
                    data.get('close'),
                    data.get('volume')
                ])
            self._execute_query(query, params)
            total_saved += len(batch)
        return total_saved

    def get_statistics(self) -> Dict[str, Any]:
        stats = {}
        tables = ['instruments', 'prices', 'trades', 'codal_announcements', 'news', 'audit_logs', 'monitoring_alerts']

        for table in tables:
            try:
                query = f"SELECT COUNT(*) as count FROM {table}"
                result = self._execute_query(query, fetch='one')
                stats[table] = result['count'] if result else 0
            except Exception as e:
                stats[table] = -1

        return stats


if __name__ == "__main__":
    from datetime import datetime
    import json
    import re

    handler = DatabaseHandler()

    print("Testing Database Handler...")

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
        instrument_id = handler.save_instrument(instrument_data)
        print(f"✓ Instrument saved with ID: {instrument_id}")
    except Exception as e:
        print(f"✗ Error saving instrument: {e}")

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
        price_id = handler.save_price(price_data)
        print(f"✓ Price saved with ID: {price_id}")
    except Exception as e:
        print(f"✗ Error saving price: {e}")

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
        trade_id = handler.save_trade(trade_data)
        print(f"✓ Trade saved with ID: {trade_id}")
    except Exception as e:
        print(f"✗ Error saving trade: {e}")

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
        codal_id = handler.save_codal_announcement(codal_data)
        print(f"✓ Codal announcement saved with ID: {codal_id}")
    except Exception as e:
        print(f"✗ Error saving codal announcement: {e}")

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
        news_id = handler.save_news(news_data)
        print(f"✓ News saved with ID: {news_id}")
    except Exception as e:
        print(f"✗ Error saving news: {e}")

    error_test = IndexError("Selector not found: .price-table")
    try:
        error_id = handler.handle_scraping_error(error_test, "http://old.tsetmc.com/mkt", "<html>...")
        print(f"✓ Scraping error handled and logged with ID: {error_id}")
    except Exception as e:
        print(f"✗ Error handling scraping error: {e}")

    try:
        stats = handler.get_statistics()
        print(f"✓ Database statistics retrieved")
        for table, count in stats.items():
            print(f"  {table}: {count} records")
    except Exception as e:
        print(f"✗ Error getting statistics: {e}")

    handler.close_all_connections()
    print("\n✓ Database handler test completed successfully!")

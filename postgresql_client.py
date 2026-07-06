import os
import csv
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql, OperationalError, Error, DatabaseError, IntegrityError
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


class PostgreSQLClient:
    _pool: Optional[SimpleConnectionPool] = None

    def __init__(self, min_conn: int = 2, max_conn: int = 5):
        self._initialize_pool(min_conn, max_conn)
        self.table_definitions = {
            'instruments': """
                id SERIAL PRIMARY KEY,
                symbol VARCHAR(20) UNIQUE NOT NULL,
                en_symbol VARCHAR(20),
                market_id VARCHAR(20) NOT NULL,
                name VARCHAR(200) NOT NULL,
                sector VARCHAR(100),
                sub_sector VARCHAR(100),
                isin VARCHAR(30),
                status VARCHAR(20) DEFAULT 'active',
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            """,
            'prices': """
                id BIGSERIAL PRIMARY KEY,
                instrument_id INTEGER REFERENCES instruments(id) ON DELETE CASCADE,
                date INTEGER NOT NULL,
                open DECIMAL(18,2),
                high DECIMAL(18,2),
                low DECIMAL(18,2),
                close DECIMAL(18,2),
                volume BIGINT,
                open_interest_1 DECIMAL(18,2),
                open_interest_2 INTEGER,
                open_interest_3 DECIMAL(18,2),
                col11 VARCHAR(20),
                col12 VARCHAR(100),
                col13 BIGINT,
                col14 BIGINT,
                col15 DECIMAL(18,2),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(instrument_id, date)
            """,
            'quotes': """
                id BIGSERIAL PRIMARY KEY,
                instrument_id INTEGER REFERENCES instruments(id) ON DELETE CASCADE,
                last_price DECIMAL(18,2),
                bid_price DECIMAL(18,2),
                ask_price DECIMAL(18,2),
                bid_volume BIGINT,
                ask_volume BIGINT,
                change_pct DECIMAL(10,2),
                volume BIGINT,
                value BIGINT,
                trade_count INTEGER,
                recorded_at TIMESTAMP DEFAULT NOW()
            """,
            'trades': """
                id BIGSERIAL PRIMARY KEY,
                instrument_id INTEGER REFERENCES instruments(id) ON DELETE CASCADE,
                trade_time TIMESTAMP NOT NULL,
                price DECIMAL(18,2) NOT NULL,
                volume BIGINT NOT NULL,
                side VARCHAR(4) CHECK (side IN ('buy', 'sell')),
                trade_type VARCHAR(20),
                created_at TIMESTAMP DEFAULT NOW()
            """,
            'backtest_runs': """
                id BIGSERIAL PRIMARY KEY,
                strategy_name VARCHAR(100) NOT NULL,
                strategy_version VARCHAR(20),
                market_ids TEXT[],
                start_date INTEGER,
                end_date INTEGER,
                initial_capital DECIMAL(18,2) NOT NULL,
                final_capital DECIMAL(18,2),
                total_return_pct DECIMAL(10,2),
                total_trades INTEGER DEFAULT 0,
                status VARCHAR(20) DEFAULT 'pending',
                error_message TEXT,
                run_params JSONB,
                created_at TIMESTAMP DEFAULT NOW(),
                completed_at TIMESTAMP
            """,
            'backtest_trades': """
                id BIGSERIAL PRIMARY KEY,
                run_id BIGINT REFERENCES backtest_runs(id) ON DELETE CASCADE,
                instrument_id INTEGER REFERENCES instruments(id),
                entry_time TIMESTAMP,
                exit_time TIMESTAMP,
                entry_price DECIMAL(18,2),
                exit_price DECIMAL(18,2),
                quantity BIGINT,
                side VARCHAR(4) CHECK (side IN ('buy', 'sell')),
                pnl DECIMAL(18,2),
                pnl_pct DECIMAL(10,2),
                commission DECIMAL(18,2) DEFAULT 0,
                metadata JSONB
            """,
            'backtest_equity': """
                id BIGSERIAL PRIMARY KEY,
                run_id BIGINT REFERENCES backtest_runs(id) ON DELETE CASCADE,
                date INTEGER,
                equity DECIMAL(18,2),
                cash DECIMAL(18,2),
                positions_value DECIMAL(18,2),
                drawdown_pct DECIMAL(10,2),
                created_at TIMESTAMP DEFAULT NOW()
            """,
            'backtest_metrics': """
                id BIGSERIAL PRIMARY KEY,
                run_id BIGINT REFERENCES backtest_runs(id) ON DELETE CASCADE,
                metric_name VARCHAR(50) NOT NULL,
                metric_value DECIMAL(18,4),
                annualized BOOLEAN DEFAULT FALSE,
                UNIQUE(run_id, metric_name)
            """,
            'strategies': """
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL UNIQUE,
                description TEXT,
                class_path VARCHAR(200),
                default_params JSONB,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            """,
            'codal_announcements': """
                id BIGSERIAL PRIMARY KEY,
                announcement_id VARCHAR(50) UNIQUE NOT NULL,
                company_name VARCHAR(200) NOT NULL,
                ticker VARCHAR(20),
                subject VARCHAR(500),
                description TEXT,
                announcement_date INTEGER,
                attachment_url VARCHAR(500),
                pdf_hash VARCHAR(64),
                received_at TIMESTAMP DEFAULT NOW(),
                is_processed BOOLEAN DEFAULT FALSE
            """,
            'news': """
                id BIGSERIAL PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                summary TEXT,
                content TEXT,
                source VARCHAR(200),
                url VARCHAR(500),
                published_at TIMESTAMP,
                ticker_related VARCHAR(20),
                sentiment_score DECIMAL(5,2),
                created_at TIMESTAMP DEFAULT NOW()
            """,
            'users': """
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) NOT NULL UNIQUE,
                email VARCHAR(100) NOT NULL UNIQUE,
                password_hash VARCHAR(200) NOT NULL,
                full_name VARCHAR(100),
                role VARCHAR(20) DEFAULT 'user',
                is_active BOOLEAN DEFAULT TRUE,
                last_login TIMESTAMP,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            """,
            'user_portfolios': """
                id BIGSERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL,
                description TEXT,
                cash_balance DECIMAL(18,2) DEFAULT 0,
                initial_capital DECIMAL(18,2),
                total_value DECIMAL(18,2),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            """,
            'user_positions': """
                id BIGSERIAL PRIMARY KEY,
                portfolio_id BIGINT REFERENCES user_portfolios(id) ON DELETE CASCADE,
                instrument_id INTEGER REFERENCES instruments(id) ON DELETE CASCADE,
                quantity BIGINT NOT NULL,
                avg_price DECIMAL(18,2),
                current_price DECIMAL(18,2),
                unrealized_pnl DECIMAL(18,2),
                updated_at TIMESTAMP DEFAULT NOW()
            """,
            'system_config': """
                id SERIAL PRIMARY KEY,
                config_key VARCHAR(100) NOT NULL UNIQUE,
                config_value TEXT,
                description TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            """
        }

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

    def create_tables(self):
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                for table, definition in self.table_definitions.items():
                    try:
                        cursor.execute(
                            sql.SQL("CREATE TABLE IF NOT EXISTS {} ({})").format(
                                sql.Identifier(table),
                                sql.SQL(definition)
                            )
                        )
                        conn.commit()
                    except (OperationalError, DatabaseError) as e:
                        print(f"Error creating table {table}: {e}")
                        conn.rollback()

    def insert(self, table_name: str, data: Dict[str, Any]) -> int:
        columns = ', '.join(data.keys())
        placeholders = ', '.join(['%s'] * len(data))
        query = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, tuple(data.values()))
                    conn.commit()
                    return cursor.fetchone()[0]
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to insert record into {table_name}: {e}")

    def update(self, table_name: str, record_id: int, data: Dict[str, Any]) -> bool:
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        query = f"UPDATE {table_name} SET {set_clause} WHERE id = %s"
        values = list(data.values()) + [record_id]

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query, values)
                    conn.commit()
                    return cursor.rowcount > 0
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to update record in {table_name}: {e}")

    def get_by_id(self, table_name: str, record_id: int) -> Optional[Dict]:
        query = f"SELECT * FROM {table_name} WHERE id = %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cursor:
                    cursor.execute(query, (record_id,))
                    return cursor.fetchone()
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to get record from {table_name}: {e}")

    def get_all(self, table_name: str, limit: int = 1000, offset: int = 0) -> List[Dict]:
        query = f"SELECT * FROM {table_name} LIMIT %s OFFSET %s"

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cursor:
                    cursor.execute(query, (limit, offset))
                    return cursor.fetchall()
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to get records from {table_name}: {e}")

    def filter(self, table_name: str, conditions: Dict[str, Any], limit: int = 1000) -> List[Dict]:
        if not conditions:
            return self.get_all(table_name, limit)

        set_clause = ' AND '.join([f"{k} = %s" for k in conditions.keys()])
        query = f"SELECT * FROM {table_name} WHERE {set_clause} LIMIT %s"
        values = list(conditions.values()) + [limit]

        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=DictCursor) as cursor:
                    cursor.execute(query, values)
                    return cursor.fetchall()
        except (OperationalError, DatabaseError) as e:
            raise DatabaseError(f"Failed to filter records from {table_name}: {e}")

    def export_all_to_csv(self, output_dir: str = None) -> Dict:
        if output_dir is None:
            output_dir = 'exports'

        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_dir = os.path.join(output_dir, f'export_{timestamp}')
        os.makedirs(export_dir, exist_ok=True)

        result = {}

        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name NOT LIKE 'pg_%'
                    AND table_name != 'information_schema'
                """)
                tables = [row[0] for row in cursor.fetchall()]

                for table in tables:
                    csv_path = os.path.join(export_dir, f"{table}.csv")
                    try:
                        with open(csv_path, 'w', newline='') as csvfile:
                            writer = csv.writer(csvfile)
                            try:
                                cursor.execute(f"SELECT * FROM {table} LIMIT 1")
                                columns = [desc[0] for desc in cursor.description]
                                writer.writerow(columns)

                                offset = 0
                                batch_size = 10000
                                while True:
                                    cursor.execute(f"SELECT * FROM {table} LIMIT %s OFFSET %s", (batch_size, offset))
                                    records = cursor.fetchall()
                                    if not records:
                                        break
                                    writer.writerows(records)
                                    offset += batch_size
                            except Exception as e:
                                print(f"Error reading from table {table}: {e}")

                        file_size = os.path.getsize(csv_path)
                        result[table] = {
                            'path': csv_path,
                            'size_bytes': file_size,
                            'records': file_size > 0
                        }
                    except Exception as e:
                        print(f"Error exporting table {table} to CSV: {e}")
                        result[table] = {
                            'path': csv_path,
                            'error': str(e)
                        }

        return result


if __name__ == "__main__":
    client = PostgreSQLClient()

    client.create_tables()

    instrument_id = client.insert('instruments', {
        'symbol': 'فولاد',
        'en_symbol': 'MTHD',
        'market_id': 'bourse',
        'name': 'شرکت فولاد مبارکه اصفهان',
        'sector': 'صنعت',
        'sub_sector': 'فلزات',
        'status': 'active'
    })

    client.insert('instruments', {
        'symbol': 'فولاد01',
        'en_symbol': 'MTHD01',
        'market_id': 'bourse',
        'name': 'شرکت فولاد مبارکه اصفهان - گروه 1',
        'sector': 'صنعت',
        'sub_sector': 'فلزات',
        'status': 'active'
    })

    client.insert('prices', {
        'instrument_id': 1,
        'date': 20250101,
        'open': 100.0,
        'high': 105.5,
        'low': 99.5,
        'close': 103.25,
        'volume': 1000000,
        'open_interest_1': 50000.0,
        'open_interest_2': 5000
    })

    client.insert('prices', {
        'instrument_id': 2,
        'date': 20250101,
        'open': 20.5,
        'high': 22.0,
        'low': 20.0,
        'close': 21.75,
        'volume': 500000,
        'open_interest_1': 25000.0,
        'open_interest_2': 2500
    })

    client.insert('quotes', {
        'instrument_id': 1,
        'last_price': 103.25,
        'bid_price': 103.20,
        'ask_price': 103.30,
        'bid_volume': 100,
        'ask_volume': 150,
        'change_pct': 1.25,
        'volume': 500000,
        'value': 51625000,
        'trade_count': 125
    })

    client.insert('trades', {
        'instrument_id': 1,
        'trade_time': datetime.now(),
        'price': 103.25,
        'volume': 100,
        'side': 'buy',
        'trade_type': 'regular'
    })

    run_id = client.insert('backtest_runs', {
        'strategy_name': 'SMA_Cross',
        'strategy_version': '1.0.0',
        'market_ids': ['bourse', 'farin'],
        'start_date': 20240101,
        'end_date': 20250101,
        'initial_capital': 1000000.0,
        'status': 'completed'
    })

    client.insert('backtest_trades', {
        'run_id': run_id,
        'instrument_id': 1,
        'entry_time': datetime.now(),
        'exit_time': datetime.now(),
        'entry_price': 100.0,
        'exit_price': 105.0,
        'quantity': 100,
        'side': 'buy',
        'pnl': 500.0,
        'pnl_pct': 5.0,
        'commission': 10.0
    })

    client.insert('backtest_equity', {
        'run_id': run_id,
        'date': 20250101,
        'equity': 1005000.0,
        'cash': 500000.0,
        'positions_value': 505000.0,
        'drawdown_pct': 0.5
    })

    client.insert('backtest_metrics', {
        'run_id': run_id,
        'metric_name': 'total_return',
        'metric_value': 0.5,
        'annualized': False
    })

    client.insert('strategies', {
        'name': 'Momentum',
        'description': 'استراتژی مبتنی بر مومنتوم',
        'class_path': 'strategies.momentum.MomentumStrategy',
        'default_params': {'window': 20, 'threshold': 0.05}
    })

    client.insert('codal_announcements', {
        'announcement_id': '09/124/I/20250101',
        'company_name': 'شرکت فولاد مبارکه اصفهان',
        'ticker': 'فولاد',
        'subject': 'افزایش سرمایه',
        'description': 'پیشنهاد افزایش سرمایه از 5000 میلیارد به 8000 میلیارد تومان',
        'announcement_date': 20250101,
        'attachment_url': 'http://example.com/doc.pdf'
    })

    client.insert('news', {
        'title': 'عملکرد فولاد در بازار امروز',
        'summary': 'قیمت سهام فولاد امروز با رشد قابل توجهی همراه بود',
        'content': 'جزئیات بیشتر در مورد عملکرد سهم فولاد در جلسه معاملاتی امروز',
        'source': 'خبرگزاری پویا',
        'url': 'http://example.com/news/123',
        'published_at': datetime.now(),
        'ticker_related': 'فولاد',
        'sentiment_score': 0.75
    })

    user_id = client.insert('users', {
        'username': 'ali',
        'email': 'ali@example.com',
        'password_hash': '$2b$12$...',
        'full_name': 'علی احمدی',
        'role': 'admin'
    })

    client.insert('user_portfolios', {
        'user_id': user_id,
        'name': 'بورس فردا',
        'description': 'پورتفوی سرمایه‌گذاری بلندمدت',
        'cash_balance': 100000.0,
        'initial_capital': 200000.0,
        'total_value': 250000.0
    })

    client.insert('user_positions', {
        'portfolio_id': 1,
        'instrument_id': 1,
        'quantity': 100,
        'avg_price': 100.0,
        'current_price': 103.25,
        'unrealized_pnl': 325.0
    })

    client.insert('system_config', {
        'config_key': 'max_portfolios_per_user',
        'config_value': '10',
        'description': 'حداکثر تعداد پرتفوی برای هر کاربر'
    })

    result = client.export_all_to_csv()

    print("\n=== نمونه داده‌های استخراج‌شده ===")
    for table, info in result.items():
        print(f"\nجدول {table}:")
        if 'error' in info:
            print(f"  - خطا: {info['error']}")
        else:
            print(f"  - مسیر فایل: {info['path']}")
            print(f"  - اندازه: {info['size_bytes'] / 1024:.2f} کیلوبایت")

    client.close_all_connections()

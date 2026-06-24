import os
import csv
from datetime import datetime
from dotenv import load_dotenv
import psycopg2
from psycopg2 import sql, OperationalError
from psycopg2.extras import DictCursor

class PostgreSQLClient:
    def __init__(self):
        load_dotenv()
        self.connection_params = {
            'host': os.getenv('PG_HOST'),
            'port': os.getenv('PG_PORT'),
            'database': os.getenv('PG_DATABASE'),
            'user': os.getenv('PG_USER'),
            'password': os.getenv('PG_PASSWORD')
        }
        self.table_definitions = {
            'users': """
                id SERIAL PRIMARY KEY,
                full_name VARCHAR(100) NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            """,
            'orders': """
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id) NOT NULL,
                product_name VARCHAR(200) NOT NULL,
                price DECIMAL(10,2) NOT NULL,
                order_date DATE DEFAULT CURRENT_DATE
            """
        }

    def _get_connection(self):
        return psycopg2.connect(**self.connection_params)

    def create_tables(self):
        """Create tables if they don't exist"""
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
                    except OperationalError as e:
                        print(f"Error creating table {table}: {e}")
                        conn.rollback()

    def insert_record(self, table_name: str, data: dict):
        """Insert a record into specified table"""
        columns = data.keys()
        values = [data[col] for col in columns]
        placeholders = ', '.join(['%s'] * len(values))
        
        query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.SQL(', ').join(sql.Placeholder() * len(values))
        )
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, values)
                conn.commit()

    def update_record(self, table_name: str, record_id: int, data: dict):
        """Update a record based on ID"""
        set_clause = ', '.join([f"{k} = %s" for k in data.keys()])
        query = f"UPDATE {table_name} SET {set_clause} WHERE id = %s"
        values = list(data.values()) + [record_id]
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, values)
                conn.commit()

    def get_by_id(self, table_name: str, record_id: int):
        """Get a single record by ID"""
        query = f"SELECT * FROM {table_name} WHERE id = %s"
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, (record_id,))
                return cursor.fetchone()

    def get_all(self, table_name: str):
        """Get all records from a table"""
        query = f"SELECT * FROM {table_name}"
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query)
                return cursor.fetchall()

    def filter_records(self, table_name: str, condition: str, params: tuple = None):
        """Filter records based on a condition"""
        query = f"SELECT * FROM {table_name} WHERE {condition}"
        
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=DictCursor) as cursor:
                cursor.execute(query, params or ())
                return cursor.fetchall()

    def export_all_tables_to_csv(self, output_dir: str = 'exports'):
        """Export all tables to CSV files with timestamped directory"""
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_dir = os.path.join(output_dir, timestamp)
        os.makedirs(export_dir, exist_ok=True)
        
        with self._get_connection() as conn:
            with conn.cursor() as cursor:
                # Get all tables in the database
                cursor.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema='public'
                """)
                tables = [row[0] for row in cursor.fetchall()]
                
                for table in tables:
                    csv_path = os.path.join(export_dir, f"{table}.csv")
                    cursor.execute(f"SELECT * FROM {table}")
                    columns = [desc[0] for desc in cursor.description]
                    
                    with open(csv_path, 'w', newline='') as csvfile:
                        writer = csv.writer(csvfile)
                        writer.writerow(columns)
                        
                        records = cursor.fetchall()
                        if records:
                            writer.writerows(records)
        
        return export_dir


if __name__ == "__main__":
    # Example usage
    client = PostgreSQLClient()
    
    # Create tables
    client.create_tables()
    
    # Insert sample users
    client.insert_record('users', {
        'full_name': 'John Doe',
        'email': 'john@example.com'
    })
    
    client.insert_record('users', {
        'full_name': 'Jane Smith',
        'email': 'jane@example.com'
    })
    
    # Insert sample orders
    client.insert_record('orders', {
        'user_id': 1,
        'product_name': 'Laptop',
        'price': 999.99
    })
    
    client.insert_record('orders', {
        'user_id': 2,
        'product_name': 'Headphones',
        'price': 149.99
    })
    
    # Get and print a user by ID
    user = client.get_by_id('users', 1)
    print("User with ID 1:", user)
    
    # Update a record
    client.update_record('users', 1, {'full_name': 'John Updated'})
    
    # Get all users
    all_users = client.get_all('users')
    print("All users:", all_users)
    
    # Filter records
    expensive_orders = client.filter_records(
        'orders',
        'price > %s',
        (150.00,)
    )
    print("Expensive orders (>150):", expensive_orders)
    
    # Export all tables to CSV
    export_dir = client.export_all_tables_to_csv()
    print(f"Tables exported to: {export_dir}")

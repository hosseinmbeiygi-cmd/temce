import _db

conn = _db.psycopg2_connect()
cur = conn.cursor()

# Check codal_reports data
cur.execute("SELECT COUNT(*) FROM codal_reports")
total = cur.fetchone()[0]
print(f"Total codal_reports: {total}")

if total > 0:
    cur.execute("SELECT id, symbol, company_name, report_type, fiscal_year, period, publish_date FROM codal_reports LIMIT 5")
    print("\nSample rows:")
    for row in cur.fetchall():
        print(f"  {row}")

    # Check columns
    cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'codal_reports' ORDER BY ordinal_position")
    cols = [r[0] for r in cur.fetchall()]
    print(f"\nColumns: {cols}")

    # Check if publish_date has valid data
    cur.execute("SELECT COUNT(*) FROM codal_reports WHERE publish_date IS NOT NULL AND publish_date != ''")
    with_date = cur.fetchone()[0]
    print(f"\nRows with publish_date: {with_date}")

    # Check if symbol has valid data
    cur.execute("SELECT COUNT(*) FROM codal_reports WHERE symbol IS NOT NULL AND symbol != ''")
    with_symbol = cur.fetchone()[0]
    print(f"Rows with symbol: {with_symbol}")

cur.close()
conn.close()

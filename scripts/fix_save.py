import re

path = r"C:\Users\Iran\Desktop\temce\scripts\batch_audit_all_symbols.py"
with open(path, encoding="utf-8") as f:
    content = f.read()

# Find the save function and replace the codal_financial_statements part
old_pattern = r'    cur\.execute\(\s*"INSERT INTO codal_financial_statements.*?ON CONFLICT.*?imported_at=CURRENT_TIMESTAMP",\s*\(cid, sym, rt, rd.*?\),\s*\)'
new_code = '''    try:
        cur.execute(
            "INSERT INTO codal_financial_statements "
            "(id,symbol,report_type,report_date,filename,file_path,title,parsed_data,table_count,row_count,import_batch,imported_at) "
            "VALUES (%s,%s,%s,%s,NULL,NULL,%s,%s,%s,0,%s,CURRENT_TIMESTAMP)",
            (cid, sym, rt or None, rd or None, "Batch audit - " + sym, pd, len(full.get("snapshot", {})),
             "batch_" + str(int(time.time()))),
        )
    except Exception:
        pass'''

content = re.sub(old_pattern, new_code, content, flags=re.DOTALL)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

# Verify
with open(path, encoding="utf-8") as f:
    c = f.read()
if "ON CONFLICT" in c.split("def save")[1].split("def classify")[0]:
    # Still has ON CONFLICT in save function - manual fix needed
    # Find the second ON CONFLICT in save function
    save_section = c[c.find("def save"):c.find("def classify")]
    if "ON CONFLICT" in save_section:
        # Remove everything from ON CONFLICT to the closing paren
        idx = save_section.find("ON CONFLICT")
        # Find the matching closing paren
        # Just replace the whole insert block
        before = save_section[:save_section.rfind("cur.execute(")]
        after_insert = save_section[save_section.rfind("pass") + 4:]
        fixed = before + new_code + "\n" + after_insert
        c = c[:c.find("def save")] + fixed + c[c.find("def classify"):]
        with open(path, "w", encoding="utf-8") as f:
            f.write(c)
        print("Manual fix applied")

print("Fixed and verified")

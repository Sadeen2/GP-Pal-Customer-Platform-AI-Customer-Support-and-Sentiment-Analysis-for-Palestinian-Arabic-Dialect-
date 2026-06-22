import sqlite3

con = sqlite3.connect("pal_customer.db")
cur = con.cursor()

cols = [r[1] for r in cur.execute("PRAGMA table_info(messages)").fetchall()]

if "sender_type" not in cols:
    cur.execute("ALTER TABLE messages ADD COLUMN sender_type TEXT DEFAULT 'customer'")
    print("sender_type column added")
else:
    print("sender_type already exists")

con.commit()
con.close()
print("done")

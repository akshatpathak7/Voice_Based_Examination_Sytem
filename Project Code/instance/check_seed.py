import sqlite3

conn = sqlite3.connect("exam.db")
cur = conn.cursor()

cur.execute("SELECT username, role FROM registration")

rows = cur.fetchall()

print("Users present in database:\n")

for row in rows:
    print(row)

conn.close()

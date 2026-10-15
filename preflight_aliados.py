#!/usr/bin/env python3
"""Local read-only preflight for WD migration. No passwords are exported."""
import json
import os
import sys
import pymysql

USERS = ["AGENTE-WD_%02d" % n for n in range(1, 16)] + ["Sup_WD_1"]

def main():
    import getpass
    password = getpass.getpass("MariaDB cron password (local only): ")
    sockets = ["/var/run/mysql/mysql.sock", "/run/mysql/mysql.sock", "/var/lib/mysql/mysql.sock", "/var/run/mysqld/mysqld.sock"]
    socket = next((s for s in sockets if os.path.exists(s)), None)
    if not socket:
        raise RuntimeError("No MariaDB Unix socket found; inspect SHOW VARIABLES LIKE socket")
    conn = pymysql.connect(
        unix_socket=socket,
        user="cron", password=password,
        database="asterisk",
        cursorclass=pymysql.cursors.DictCursor)
    try:
        with conn.cursor() as c:
            counts = {}
            for table, field, value in (
                ("vicidial_campaigns", "campaign_id", "WD"),
                ("vicidial_user_groups", "user_group", "CC-MED-WD"),
            ):
                c.execute("SELECT COUNT(*) AS n FROM "+table+" WHERE "+field+"=%s", (value,))
                counts[table] = c.fetchone()["n"]
            placeholders = ",".join(["%s"] * len(USERS))
            c.execute("SELECT user FROM vicidial_users WHERE user IN ("+placeholders+")", USERS)
            present = set(r["user"] for r in c.fetchall())
            counts["vicidial_users"] = len(present)
            counts["missing_users"] = sorted(set(USERS) - present)
            print(json.dumps(counts, indent=2))
            return 0 if counts["vicidial_campaigns"] == 1 and counts["vicidial_user_groups"] == 1 and len(present) == 16 else 1
    finally:
        conn.close()

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as ex:
        print("Preflight failed: " + type(ex).__name__, file=sys.stderr)
        sys.exit(1)

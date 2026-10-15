#!/usr/bin/env python3
"""WD configuration preflight. Does not expose credentials or modify databases."""
import argparse
import json
import os
import sys
import pymysql

CAMPAIGN = "WD"
GROUP = "CC-MED-WD"
USERS = ["AGENTE-WD_%02d" % i for i in range(1, 16)] + ["Sup_WD_1"]
TABLES = ("vicidial_user_groups", "vicidial_campaigns", "vicidial_users")
SKIP = {
    "vicidial_user_groups": {"modify_stamp"},
    "vicidial_campaigns": {"campaign_changedate", "campaign_logindate",
                          "campaign_calldate", "call_quota_last_run_date",
                          "call_quota_process_running"},
    "vicidial_users": {"user_id", "modify_stamp", "last_login_date",
                      "last_ip", "failed_login_count", "failed_login_count_today",
                      "failed_login_attempts_today", "failed_last_ip_today",
                      "failed_last_type_today", "phone_login", "phone_pass"},
}

def connect(prefix):
    required = [prefix + "_" + k for k in ("HOST", "USER", "PASSWORD")]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        raise ValueError("Missing variables: " + ", ".join(missing))
    return pymysql.connect(
        host=os.environ[prefix + "_HOST"],
        port=int(os.getenv(prefix + "_PORT", "3306")),
        user=os.environ[prefix + "_USER"],
        password=os.environ[prefix + "_PASSWORD"],
        database=os.getenv(prefix + "_DB", "asterisk"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=8, read_timeout=20, write_timeout=20,
        autocommit=False,
    )

def table_columns(connection, table):
    with connection.cursor() as cursor:
        cursor.execute("SHOW COLUMNS FROM `%s`" % table)
        return {row["Field"]: row for row in cursor.fetchall()}

def source_rows(connection, table):
    if table == "vicidial_user_groups":
        condition, params = "user_group=%s", (GROUP,)
    elif table == "vicidial_campaigns":
        condition, params = "campaign_id=%s", (CAMPAIGN,)
    else:
        condition = "user IN (" + ",".join(["%s"] * len(USERS)) + ")"
        params = USERS
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM `%s` WHERE %s" % (table, condition), params)
        return list(cursor.fetchall())

def conflicts(connection):
    output = {}
    for table, field, values in (
        ("vicidial_campaigns", "campaign_id", [CAMPAIGN]),
        ("vicidial_user_groups", "user_group", [GROUP]),
        ("vicidial_users", "user", USERS),
    ):
        query = ("SELECT `%s` FROM `%s` WHERE `%s` IN (%s)" %
                 (field, table, field, ",".join(["%s"] * len(values))))
        with connection.cursor() as cursor:
            cursor.execute(query, values)
            output[table] = [row[field] for row in cursor.fetchall()]
    return output

def plan(source, target):
    rows = {name: source_rows(source, name) for name in TABLES}
    present = set(item["user"] for item in rows["vicidial_users"])
    missing = sorted(set(USERS) - present)
    if (len(rows["vicidial_campaigns"]) != 1 or
            len(rows["vicidial_user_groups"]) != 1 or
            missing or len(rows["vicidial_users"]) != 16):
        raise ValueError("Source record count mismatch, missing users: " + str(missing))
    occupied = conflicts(target)
    if any(occupied.values()):
        raise ValueError("Destination identifiers already exist: " + str(occupied))
    prepared = {}
    for table in TABLES:
        src = table_columns(source, table)
        dst = table_columns(target, table)
        unsupported = set(src) - set(dst) - SKIP[table]
        if unsupported:
            raise ValueError("Destination missing %s columns: %s" %
                             (table, sorted(unsupported)))
        fields = [name for name in src if name in dst and name not in SKIP[table]]
        result = []
        for old in rows[table]:
            item = {name: old[name] for name in fields}
            if table == "vicidial_campaigns":
                item["active"] = "N"
            if table == "vicidial_users":
                # Never copy phone credentials, including for the supervisor.
                item["phone_login"] = ""
                item["phone_pass"] = ""
            result.append(item)
        prepared[table] = result
    return prepared

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["plan", "apply"])
    parser.add_argument("--confirm", default="")
    args = parser.parse_args()
    if args.action == "apply" and args.confirm != "CLONE-WD-16":
        parser.error("apply requires --confirm CLONE-WD-16")
    src = dst = None
    try:
        src = connect("SOURCE")
        dst = connect("TARGET")
        prepared = plan(src, dst)
        print(json.dumps({
            "ready": True, "action": args.action, "campaign": CAMPAIGN,
            "group": GROUP, "users": len(prepared["vicidial_users"]),
            "agents": 15, "supervisors": 1,
            "lists": 0, "phones": 0, "campaign_active": "N",
        }))
        if args.action == "plan":
            return 0
        # MyISAM cannot be rolled back. Keep apply locked until validated
        # backup and recoverability are implemented and independently reviewed.
        raise RuntimeError("Apply disabled in v0.1: MyISAM backup/recovery not implemented")
    except Exception as exc:
        # Never print database exception details that could contain secret values.
        print("FAILED: " + type(exc).__name__ +
              "; no changes were intentionally written", file=sys.stderr)
        return 1
    finally:
        if dst:
            dst.close()
        if src:
            src.close()

if __name__ == "__main__":
    sys.exit(main())

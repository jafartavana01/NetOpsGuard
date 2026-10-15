"""Add only nullable scheduling fields, preserving every saved UTC schedule."""
from sqlalchemy import inspect, text


def migrate(engine):
    additions = {
        "ncm_backup_schedules": {"schedule_timezone": "VARCHAR(64)"},
        "audit_schedule_settings": {"schedule_timezone": "VARCHAR(64)", "last_slot": "TIMESTAMP"},
    }
    with engine.begin() as conn:
        if engine.dialect.name == "postgresql":
            conn.execute(text("SELECT pg_advisory_xact_lock(72019011)"))
        elif engine.dialect.name == "sqlite":
            conn.exec_driver_sql("BEGIN IMMEDIATE")
        inspector = inspect(conn)
        for table, columns in additions.items():
            if not inspector.has_table(table):
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            for name, kind in columns.items():
                if name not in existing:
                    if kind == "TIMESTAMP" and engine.dialect.name == "postgresql":
                        kind = "TIMESTAMP WITH TIME ZONE"
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {kind}"))

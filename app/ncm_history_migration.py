"""Retain immutable NCM device identities independently of live inventory.

Only three historical device FKs are removed. Other constraints and all rows,
indexes and triggers survive. Run during startup/upgrade before serving traffic.
"""
from sqlalchemy import MetaData, inspect, text
from sqlalchemy.schema import CreateTable

TABLES = ('ncm_configurations', 'ncm_baselines', 'ncm_candidates')


def migrate(engine):
    if engine.dialect.name not in ('sqlite', 'postgresql'):
        raise RuntimeError('NCM history migration requires SQLite or PostgreSQL.')
    with engine.connect() as conn:
        sqlite = engine.dialect.name == 'sqlite'
        foreign_keys = None
        if sqlite:
            foreign_keys = conn.exec_driver_sql('PRAGMA foreign_keys').scalar()
            conn.commit()
            conn.exec_driver_sql('PRAGMA foreign_keys=OFF')
            conn.commit()
        try:
            with conn.begin():
                if sqlite:
                    conn.exec_driver_sql('BEGIN IMMEDIATE')
                else:
                    conn.execute(text('SELECT pg_advisory_xact_lock(72019012)'))
                schema_name = conn.get_execution_options().get('schema_translate_map', {}).get(None)
                for name in TABLES:
                    inspector = inspect(conn)
                    if not inspector.has_table(name, schema=schema_name):
                        continue
                    targets = [fk for fk in inspector.get_foreign_keys(name, schema=schema_name)
                               if fk['constrained_columns'] == ['device_id'] and fk['referred_table'] == 'network_devices']
                    if not targets:
                        continue
                    quote = conn.dialect.identifier_preparer.quote
                    if not sqlite:
                        qualified = (quote(schema_name) + '.' if schema_name else '') + quote(name)
                        for fk in targets:
                            conn.exec_driver_sql(f'ALTER TABLE {qualified} DROP CONSTRAINT {quote(fk["name"])}')
                        continue
                    metadata = MetaData()
                    metadata.reflect(conn)
                    old = metadata.tables[name]
                    rebuilt = old.to_metadata(metadata, name=name + '_retained')
                    for constraint in list(rebuilt.foreign_key_constraints):
                        if [c.name for c in constraint.columns] == ['device_id'] and constraint.referred_table.name == 'network_devices':
                            rebuilt.constraints.remove(constraint)
                    objects = conn.execute(text("SELECT sql FROM sqlite_master WHERE tbl_name=:name AND type IN ('index','trigger') AND sql IS NOT NULL"), {'name': name}).scalars().all()
                    conn.execute(CreateTable(rebuilt))
                    columns = ','.join(quote(c.name) for c in old.columns)
                    conn.exec_driver_sql(f'INSERT INTO {quote(rebuilt.name)} ({columns}) SELECT {columns} FROM {quote(name)}')
                    conn.exec_driver_sql(f'DROP TABLE {quote(name)}')
                    conn.exec_driver_sql(f'ALTER TABLE {quote(rebuilt.name)} RENAME TO {quote(name)}')
                    for statement in objects:
                        conn.exec_driver_sql(statement)
                if sqlite and conn.exec_driver_sql('PRAGMA foreign_key_check').first():
                    raise RuntimeError('NCM history migration found inconsistent foreign keys; upgrade rolled back.')
        finally:
            if sqlite:
                conn.rollback()
                conn.exec_driver_sql('PRAGMA foreign_keys=' + str(int(foreign_keys)))
                conn.commit()

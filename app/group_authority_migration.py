"""Versioned PostgreSQL migration for explicit external-group authority.

Runs before the generic additive migrator. Failures abort startup and never
record success. No daemon files or services are touched.
"""
from sqlalchemy import text

VERSION = '20261003_f03_external_group_authority'


def migrate(engine):
    if engine.dialect.name != 'postgresql':
        raise RuntimeError('The group-authority upgrade requires PostgreSQL; no partial migration was attempted.')
    with engine.begin() as connection:
        connection.execute(text('SELECT pg_advisory_xact_lock(70403003)'))
        connection.execute(text('CREATE TABLE IF NOT EXISTS netopsguard_schema_migrations '
                                '(version VARCHAR(128) PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())'))
        if connection.execute(text('SELECT 1 FROM netopsguard_schema_migrations WHERE version=:version'), {'version': VERSION}).scalar():
            return
        connection.execute(text("ALTER TABLE tacacs_groups ADD COLUMN IF NOT EXISTS authority VARCHAR(16) NOT NULL DEFAULT 'LEGACY'"))
        connection.execute(text('ALTER TABLE tacacs_groups ADD COLUMN IF NOT EXISTS external_source_id UUID'))
        # No inference from AD metadata, member counts or connectivity.
        constraints = {
            'ck_group_authority': "CHECK (authority IN ('LEGACY','EXTERNAL'))",
            'ck_group_external_binding': "CHECK ((authority='LEGACY' AND external_source_id IS NULL) OR "
                "(authority='EXTERNAL' AND external_source_id IS NOT NULL AND ad_group_name IS NOT NULL AND length(trim(ad_group_name))>0))",
            'fk_group_external_source': 'FOREIGN KEY (external_source_id) REFERENCES ad_settings(id) ON DELETE RESTRICT',
        }
        for name, clause in constraints.items():
            present = connection.execute(text("SELECT 1 FROM pg_constraint WHERE conrelid='tacacs_groups'::regclass AND conname=:name"), {'name': name}).scalar()
            if not present:
                connection.execute(text(f'ALTER TABLE tacacs_groups ADD CONSTRAINT {name} {clause}'))
        connection.execute(text('INSERT INTO netopsguard_schema_migrations(version) VALUES (:version)'), {'version': VERSION})

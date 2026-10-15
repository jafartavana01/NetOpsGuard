"""
app.database
=============
SQLAlchemy engine/session wiring. PostgreSQL is the source of truth
(spec section 16) for every management-plane model; the generated
tac_plus-ng configuration file is a derived artifact, never the other
way around.

Fresh schemas use create_all. Existing schemas also run the legacy additive
column migrator. Explicit EXTERNAL group authority additionally has a versioned,
transactional PostgreSQL migration (group_authority_migration.py) which runs
before that additive helper and aborts startup on failure. It never changes the
deployed daemon configuration. Other historical schema upgrades are outside this
migration's scope.
"""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.exc import OperationalError
from starlette.requests import Request

from .config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(get_settings().database_url, pool_pre_ping=True)
    return _engine


def get_sessionmaker():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(bind=get_engine(), autoflush=False, autocommit=False)
    return _SessionLocal


def get_db(request: Request = None) -> Generator[Session, None, None]:
    """FastAPI dependency: yields a session, always closed after the request."""
    session_local = get_sessionmaker()
    db = session_local()
    try:
        if request is not None and request.method not in ('GET', 'HEAD', 'OPTIONS'):
            # Every API writer participates, including older tree/restore and
            # association routes. Acquire before authentication's first query.
            from .services.reference_lock import guard
            guard(db)
        yield db
    except OperationalError as exc:
        db.rollback()
        code = getattr(exc.orig, 'sqlstate', None) or getattr(exc.orig, 'pgcode', None)
        if code in ('55P03', '40001', '40P01') or 'database is locked' in str(exc.orig).lower():
            from fastapi import HTTPException
            raise HTTPException(409, detail={'code': 'dependency.transaction_conflict',
                'message': 'Another configuration transaction is active or changed the data. Refresh and retry; this transaction was rolled back.'}) from None
        raise
    finally:
        db.close()


def init_db() -> None:
    """
    Create missing tables, apply the tracked authority migration, then legacy
    additive upgrades. Failed authority migration must abort startup.
    """
    # Import models so they're registered on Base.metadata before create_all.
    from .models import (  # noqa: F401
        admin, admin_role, system_info, module_state, device, config_version, user, group,
        device_group, policy, command_rule, command_category, command_set,
        policy_command_set, policy_version, policy_condition_group, policy_condition,
        device_access_grant, ad_settings, monitoring_settings, aaa_template_settings,
        command_template, command_job, network_ops_check, network_ops_audit, audit_run,
        audit_schedule_settings, audit_batch, config_integrity, license, ncm,
        radius_settings, radius_policy, security_protection, dependency_audit,
    )

    Base.metadata.create_all(bind=get_engine())
    from .group_authority_migration import migrate
    migrate(get_engine())
    from .scheduling_migration import migrate as migrate_scheduling
    migrate_scheduling(get_engine())
    _apply_additive_column_migrations()


def _apply_additive_column_migrations() -> None:
    """
    Adds columns that exist in the models but not yet in the database.

    `create_all()` creates missing TABLES but never alters existing
    ones, so a column added to an existing table in a newer version is
    silently skipped -- and the application then fails at runtime with
    "column ... does not exist" deep inside an unrelated query. That is
    exactly what happened when `radius_enabled` and
    `radius_secret_encrypted` were added to `network_devices`: a clean
    install worked, an upgrade broke every device query.

    Scope is deliberately narrow, because this runs unattended at
    startup against production data:

      * ADD COLUMN only. Never drop, never alter a type, never rename.
        A column in the database that is no longer in the models is
        left exactly where it is -- removing it would destroy data
        nobody asked to lose.
      * A NOT NULL column is only added when the model supplies a
        scalar default, since adding NOT NULL to a table with existing
        rows fails without one. Without a default the column is added
        as NULLABLE and a warning is logged, rather than the migration
        failing and taking startup down with it.
      * Every statement is `IF NOT EXISTS`, so re-running is a no-op.

    Anything this cannot do safely is reported, not guessed at --
    `installer.install_state.check_schema_drift` remains the full
    report for an operator.
    """
    import logging

    from sqlalchemy import inspect, text

    logger = logging.getLogger(__name__)
    engine = get_engine()

    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
    except Exception as exc:  # noqa: BLE001 - never block startup on introspection
        logger.warning("Could not inspect the database schema (%s); skipping column migration.", exc)
        return

    for table_name, table in Base.metadata.tables.items():
        if table_name not in existing_tables:
            continue  # create_all just made it; nothing to add
        try:
            actual = {c["name"] for c in inspector.get_columns(table_name)}
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not read columns of %s (%s); skipping.", table_name, exc)
            continue

        for column in table.columns:
            if column.name in actual:
                continue
            try:
                type_sql = column.type.compile(dialect=engine.dialect)
            except Exception:
                logger.warning(
                    "Cannot render a SQL type for %s.%s; add it manually.", table_name, column.name
                )
                continue

            clause = f"ADD COLUMN IF NOT EXISTS {column.name} {type_sql}"
            default = getattr(column, "default", None)
            default_value = getattr(default, "arg", None) if default is not None else None

            if not column.nullable:
                if isinstance(default_value, bool):
                    clause += f" NOT NULL DEFAULT {'true' if default_value else 'false'}"
                elif isinstance(default_value, (int, float)):
                    clause += f" NOT NULL DEFAULT {default_value}"
                elif isinstance(default_value, str):
                    escaped = default_value.replace("'", "''")
                    clause += f" NOT NULL DEFAULT '{escaped}'"
                else:
                    # No usable default: adding NOT NULL would fail on a
                    # populated table. Add it nullable and say so, rather
                    # than aborting startup.
                    logger.warning(
                        "Adding %s.%s as NULLABLE: the model declares it NOT NULL but supplies "
                        "no scalar default, and a NOT NULL column cannot be added to a table "
                        "with existing rows without one.",
                        table_name, column.name,
                    )

            statement = f"ALTER TABLE {table_name} {clause}"
            try:
                with engine.begin() as conn:
                    conn.execute(text(statement))
                logger.info("Schema migration: added %s.%s", table_name, column.name)
            except Exception as exc:  # noqa: BLE001
                logger.error("Schema migration failed for %s.%s (%s).", table_name, column.name, exc)

        # Relax a NOT NULL that the models no longer impose.
        #
        # Adding columns is not enough on its own: making an EXISTING
        # column nullable is a schema change too, and without it an
        # upgraded install still rejects rows the current code considers
        # valid. That is exactly what happened when the TACACS+ shared
        # secret became optional for RADIUS-only devices.
        #
        # Only ever DROPs NOT NULL, never adds one. Widening a
        # constraint cannot fail on existing data and cannot lose any;
        # tightening one can do both, so it is deliberately not done
        # here.
        try:
            actual_meta = {c["name"]: c for c in inspector.get_columns(table_name)}
        except Exception:
            continue
        for column in table.columns:
            meta = actual_meta.get(column.name)
            if meta is None:
                continue
            db_not_null = not meta.get("nullable", True)
            if column.nullable and db_not_null and not column.primary_key:
                try:
                    with engine.begin() as conn:
                        conn.execute(text(
                            f"ALTER TABLE {table_name} ALTER COLUMN {column.name} DROP NOT NULL"
                        ))
                    logger.info("Schema migration: %s.%s is now nullable", table_name, column.name)
                except Exception as exc:  # noqa: BLE001
                    logger.error(
                        "Could not relax NOT NULL on %s.%s (%s).", table_name, column.name, exc
                    )

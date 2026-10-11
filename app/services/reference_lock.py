"""Cross-worker writer gate for reference inspection/mutation, held to transaction end.

Installed on unsafe HTTP request sessions before their first read. This includes
legacy writers/restoration, not just deletion, so a validated tree cannot be
inserted after its referenced object was deleted. No in-process lock is used.
"""
from sqlalchemy import event, text
from sqlalchemy.orm import Session

KEY = 780312045


def _begin(session, transaction, connection):
    if transaction.nested:
        return
    dialect = connection.dialect.name
    if dialect == 'postgresql':
        # Production defaults to READ COMMITTED. A waiting writer must read the
        # newly committed inventory, not a pre-lock repeatable-read snapshot.
        if connection.get_isolation_level() != 'READ COMMITTED':
            raise RuntimeError('Reference mutations require PostgreSQL READ COMMITTED isolation.')
        connection.execute(text("SET LOCAL lock_timeout = '10s'"))
        connection.execute(text('SELECT pg_advisory_xact_lock(:key)'), {'key': KEY})
    elif dialect == 'sqlite':
        connection.exec_driver_sql('BEGIN IMMEDIATE')
    else:
        raise RuntimeError('Dependency-safe mutations require PostgreSQL or SQLite.')


def guard(session):
    """Register before first read; subsequent commits reacquire at next begin."""
    if not isinstance(session, Session):
        raise TypeError('Reference mutations require a SQLAlchemy Session.')
    if session.info.get('reference_guard'):
        return
    if session.in_transaction():
        # Service entry after a read-only preflight: release the old snapshot.
        # Never discard pending work owned by a caller.
        if session.new or session.dirty or session.deleted:
            raise RuntimeError('Reference guard must be acquired before mutation.')
        session.rollback()
    session.info['reference_guard'] = True
    event.listen(session, 'after_begin', _begin)


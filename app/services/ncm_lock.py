"""Cross-process NCM locks, held across commits and released on process exit.

PostgreSQL uses session advisory locks on a dedicated connection. SQLite uses
flock beside its database (one host, shared database path; not network SQLite).
"""
from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import tempfile

from sqlalchemy import text


class Busy(RuntimeError):
    pass


@contextmanager
def hold(db, name):
    engine = db.get_bind()
    digest = hashlib.sha256(name.encode()).hexdigest()
    if engine.dialect.name == 'postgresql':
        key = int(digest[:16], 16) - 2**63
        connection = engine.connect()
        acquired = False
        try:
            acquired = connection.execute(text('SELECT pg_try_advisory_lock(:key)'), {'key': key}).scalar()
            connection.commit()
            if not acquired:
                raise Busy('Another NCM operation is running. Retry after it finishes.')
            yield
        finally:
            if acquired:
                try:
                    connection.execute(text('SELECT pg_advisory_unlock(:key)'), {'key': key})
                    connection.commit()
                except Exception:
                    connection.invalidate()
            connection.close()
    elif engine.dialect.name == 'sqlite':
        import fcntl
        database = engine.url.database
        root = Path(database).resolve().parent if database and database != ':memory:' else Path(tempfile.gettempdir()) / ('netopsguard-' + str(os.getuid()))
        directory = root / '.ncm-locks'
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        scope = str(Path(database).resolve()) if database and database != ':memory:' else str(id(engine))
        path = directory / hashlib.sha256((scope + name).encode()).hexdigest()
        fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise Busy('Another NCM operation is running. Retry after it finishes.') from None
            yield
        finally:
            os.close(fd)
    else:
        raise RuntimeError('NCM scheduling requires PostgreSQL or SQLite.')

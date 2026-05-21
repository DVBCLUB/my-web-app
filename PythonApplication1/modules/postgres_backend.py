"""
Optional PostgreSQL connection pool.

The main application still defaults to SQLite. This module is intentionally
small and opt-in so deployments can test PostgreSQL connectivity before a
full SQL dialect migration is enabled.
"""

import os


class PostgreSQLPool:
    """Lazy psycopg2 pool wrapper used by migration and smoke-test tooling."""

    def __init__(self, dsn=None, minconn=1, maxconn=5):
        self.dsn = dsn or os.environ.get("ACCOUNTING_DATABASE_URL")
        self.minconn = int(os.environ.get("ACCOUNTING_PG_MINCONN", minconn))
        self.maxconn = int(os.environ.get("ACCOUNTING_PG_MAXCONN", maxconn))
        self._pool = None

    def _ensure_pool(self):
        if self._pool is None:
            if not self.dsn:
                raise ValueError("Chua cau hinh ACCOUNTING_DATABASE_URL cho PostgreSQL.")
            try:
                from psycopg2.pool import ThreadedConnectionPool
            except ImportError as exc:
                raise ImportError("Can cai psycopg2-binary de dung PostgreSQL.") from exc
            self._pool = ThreadedConnectionPool(self.minconn, self.maxconn, self.dsn)
        return self._pool

    def getconn(self):
        return self._ensure_pool().getconn()

    def putconn(self, conn):
        if self._pool is not None:
            self._pool.putconn(conn)

    def closeall(self):
        if self._pool is not None:
            self._pool.closeall()
            self._pool = None


def smoke_test_postgres(dsn=None):
    """Return PostgreSQL server version using the configured pool."""
    pool = PostgreSQLPool(dsn=dsn)
    conn = pool.getconn()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT version()")
            return cursor.fetchone()[0]
    finally:
        pool.putconn(conn)

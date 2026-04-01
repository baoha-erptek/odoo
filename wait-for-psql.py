#!/usr/bin/env python3
"""Wait for PostgreSQL to be ready before starting Odoo."""
import argparse
import os
import sys
import time

import psycopg2


def wait_for_psql(host, port, user, password, db, timeout=30):
    """Wait for PostgreSQL to accept connections."""
    start_time = time.time()

    while True:
        try:
            conn = psycopg2.connect(
                host=host,
                port=port,
                user=user,
                password=password,
                dbname=db or 'postgres'
            )
            conn.close()
            print(f"PostgreSQL is ready at {host}:{port}!")
            return True
        except psycopg2.OperationalError as e:
            elapsed = time.time() - start_time
            if elapsed >= timeout:
                print(f"Timeout waiting for PostgreSQL at {host}:{port}")
                print(f"Error: {e}")
                return False
            print(f"Waiting for PostgreSQL at {host}:{port}... ({elapsed:.0f}s)")
            time.sleep(2)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Wait for PostgreSQL to be ready')
    parser.add_argument('--db_host', default=os.environ.get('HOST', 'localhost'))
    parser.add_argument('--db_port', default=os.environ.get('PORT', '5432'))
    parser.add_argument('--db_user', default=os.environ.get('USER', 'odoo'))
    parser.add_argument('--db_password', default=os.environ.get('PASSWORD', 'odoo'))
    parser.add_argument('--db_name', default=os.environ.get('DB_NAME', 'postgres'))
    parser.add_argument('--timeout', type=int, default=30)

    args = parser.parse_args()

    success = wait_for_psql(
        host=args.db_host,
        port=args.db_port,
        user=args.db_user,
        password=args.db_password,
        db=args.db_name,
        timeout=args.timeout
    )

    sys.exit(0 if success else 1)

"""
Database connection setup. Reads the connection string from (in order):
1. Streamlit secrets (st.secrets["DATABASE_URL"]) — used on Streamlit
   Community Cloud, where you set this under App settings -> Secrets.
2. The DATABASE_URL environment variable — used for local development
   and testing.

Works with any Postgres, including Neon's serverless Postgres. Neon
connection strings already include `sslmode=require`; if yours doesn't,
add `?sslmode=require` to the end of it.
"""
import os
import streamlit as st
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session


def _get_database_url():
    try:
        if "DATABASE_URL" in st.secrets:
            return st.secrets["DATABASE_URL"]
    except Exception:
        pass
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "No DATABASE_URL found. Set it in .streamlit/secrets.toml (for Streamlit Cloud) "
            "or as an environment variable (for local development). See README.md."
        )
    return url


DATABASE_URL = _get_database_url()

# pool_pre_ping avoids "server closed the connection unexpectedly" errors,
# which serverless Postgres (like Neon, which suspends idle databases)
# can otherwise cause on the first query after a period of inactivity.
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_recycle=300)

SessionLocal = scoped_session(sessionmaker(bind=engine, autoflush=False, autocommit=False))

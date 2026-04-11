"""init

Revision ID: 0001
Revises:
Create Date: 2026-04-09 00:00:00.000000

"""

import os
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_PUBLICATION = "electric_publication_default"
_ROLE = "electric_user"
_ELECTRIC_TABLES = ("public.topic", "public.release")


def upgrade() -> None:
    op.create_table(
        "topic",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("category", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=True),
        sa.Column("download_id", sa.Integer, nullable=False),
        sa.Column("hash", sa.Text, nullable=False),
        sa.Column("hash_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("size", sa.Text, nullable=False),
        sa.Column("seeders", sa.Integer, nullable=False),
        sa.Column("leechers", sa.Integer, nullable=False),
        sa.Column("added_on", sa.Date(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "release",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("result", sa.Text, nullable=False),
        sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.Text, nullable=True),
        sa.Column("hash_changed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("torrent_size", sa.BigInteger, nullable=True),
        sa.Column("infohash_sha256", sa.Text, nullable=True),
        sa.Column("content_type", sa.Text, nullable=True),
        sa.Column("imdb_id", sa.Integer, nullable=True),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("year", sa.Integer, nullable=True),
        sa.Column("tvdb_id", sa.Integer, nullable=True),
        sa.Column("tmdb_id", sa.Integer, nullable=True),
        sa.Column("season", sa.Integer, nullable=True),
        sa.Column("last_episode", sa.Integer, nullable=True),
        sa.Column("season_complete", sa.Boolean, nullable=True),
        sa.Column("video_files", sa.Text, nullable=True),
        sa.Column("video_files_hash", sa.Text, nullable=True),
        sa.Column("file_to_episode", sa.Text, nullable=True),
        sa.Column("quality", sa.Text, nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("codec", sa.Text, nullable=True),
        sa.Column("audio_types", sa.Text, nullable=True),
        sa.Column("audio_sources", sa.Text, nullable=True),
        sa.Column("audio_lang", sa.Text, nullable=True),
        sa.Column("subtitle_lang", sa.Text, nullable=True),
        sa.Column("author", sa.Text, nullable=True),
        sa.Column("release_group", sa.Text, nullable=True),
    )

    op.create_table(
        "page",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("html", sa.Text, nullable=True),
        sa.Column("torrent", sa.LargeBinary, nullable=True),
        sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "skyhook",
        sa.Column("imdbid", sa.Integer, primary_key=True),
        sa.Column("tvdbid", sa.Integer, nullable=True),
        sa.Column("response", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "servarr",
        sa.Column("imdbid", sa.Integer, primary_key=True),
        sa.Column("tmdbid", sa.Integer, nullable=True),
        sa.Column("response", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "imdb_titles",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("title_type", sa.Text, nullable=True),
        sa.Column("primary_title", sa.Text, nullable=True),
        sa.Column("original_title", sa.Text, nullable=True),
        sa.Column("is_adult", sa.Integer, nullable=True),
        sa.Column("start_year", sa.Integer, nullable=True),
        sa.Column("end_year", sa.Integer, nullable=True),
        sa.Column("runtime_minutes", sa.Integer, nullable=True),
        sa.Column("genres", sa.Text, nullable=True),
    )

    op.create_table(
        "electric_offset",
        sa.Column("shape_name", sa.Text, primary_key=True),
        sa.Column("handle", sa.Text, nullable=True),
        sa.Column("offset", sa.Text, nullable=False),
    )

    conn = op.get_bind()

    if conn.dialect.name == "sqlite":
        conn.execute(sa.text("PRAGMA journal_mode=WAL"))

    if os.environ.get("CREATE_ELECTRIC_PUBLICATION"):
        if conn.dialect.name != "postgresql":
            raise RuntimeError(
                "CREATE_ELECTRIC_PUBLICATION is set but the database is not PostgreSQL"
            )
        password = os.environ["ELECTRIC_USER_PASSWORD"]
        db_name = conn.execute(sa.text("SELECT current_database()")).scalar()

        conn.execute(
            sa.text(f"CREATE ROLE {_ROLE} WITH LOGIN PASSWORD :password REPLICATION"),
            {"password": password},
        )
        conn.execute(sa.text(f"GRANT {_ROLE} TO CURRENT_USER"))
        conn.execute(sa.text(f'GRANT CONNECT ON DATABASE "{db_name}" TO {_ROLE}'))
        conn.execute(sa.text(f'GRANT CREATE ON DATABASE "{db_name}" TO {_ROLE}'))
        conn.execute(sa.text(f"GRANT USAGE ON SCHEMA public TO {_ROLE}"))
        for table in _ELECTRIC_TABLES:
            conn.execute(sa.text(f"GRANT SELECT ON {table} TO {_ROLE}"))
        tables_sql = ", ".join(_ELECTRIC_TABLES)
        conn.execute(sa.text(f"CREATE PUBLICATION {_PUBLICATION} FOR TABLE {tables_sql}"))
        for table in _ELECTRIC_TABLES:
            conn.execute(sa.text(f"ALTER TABLE {table} REPLICA IDENTITY FULL"))
        conn.execute(sa.text(f"ALTER PUBLICATION {_PUBLICATION} OWNER TO {_ROLE}"))


def downgrade() -> None:
    conn = op.get_bind()

    if os.environ.get("CREATE_ELECTRIC_PUBLICATION") and conn.dialect.name == "postgresql":
        db_name = conn.execute(sa.text("SELECT current_database()")).scalar()
        conn.execute(sa.text(f"DROP PUBLICATION IF EXISTS {_PUBLICATION}"))
        for table in _ELECTRIC_TABLES:
            conn.execute(sa.text(f"REVOKE SELECT ON {table} FROM {_ROLE}"))
        conn.execute(sa.text(f"REVOKE USAGE ON SCHEMA public FROM {_ROLE}"))
        conn.execute(sa.text(f'REVOKE CONNECT ON DATABASE "{db_name}" FROM {_ROLE}'))
        conn.execute(sa.text(f"DROP ROLE IF EXISTS {_ROLE}"))

    op.drop_table("electric_offset")
    op.drop_table("imdb_titles")
    op.drop_table("servarr")
    op.drop_table("skyhook")
    op.drop_table("page")
    op.drop_table("release")
    op.drop_table("topic")

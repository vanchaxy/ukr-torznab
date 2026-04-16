import sqlalchemy as sa

from toloka_torznab.db._base import metadata

topic = sa.Table(
    "topic",
    metadata,
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

release = sa.Table(
    "release",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("result", sa.Text, nullable=False),
    sa.Column("parsed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("content_hash", sa.Text, nullable=True),
    sa.Column("hash_changed_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("name", sa.Text, nullable=True),
    sa.Column("torrent_size", sa.BigInteger, nullable=True),
    sa.Column("infohash_sha256", sa.Text, nullable=True),
    sa.Column("content_type", sa.Text, nullable=True),  # ContentType.value
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
    sa.Column("quality", sa.Text, nullable=True),  # Quality.value
    sa.Column("resolution", sa.Text, nullable=True),  # Resolution.value
    sa.Column("codec", sa.Text, nullable=True),  # CodecFamily.value
    sa.Column("audio_types", sa.Text, nullable=True),  # JSON list of AudioType.value
    sa.Column("audio_sources", sa.Text, nullable=True),  # JSON list of AudioSource.name
    sa.Column("audio_lang", sa.Text, nullable=True),  # JSON list of Lang.value
    sa.Column("subtitle_lang", sa.Text, nullable=True),  # JSON list of Lang.value
    sa.Column("author", sa.Text, nullable=True),
    sa.Column("release_group", sa.Text, nullable=True),
    sa.Column("hdr", sa.Text, nullable=True),  # VideoFormat.value
    sa.Column("cut", sa.Text, nullable=True),
    sa.Column("ratio", sa.Text, nullable=True),  # AspectRatio.value
    sa.Column("hybrid", sa.Boolean, nullable=True),
    sa.Column("parser_version", sa.Integer, nullable=True),
    sa.Column("acodec", sa.Text, nullable=True),
    sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
)

page = sa.Table(
    "page",
    metadata,
    sa.Column("id", sa.Integer, primary_key=True),
    sa.Column("html", sa.Text, nullable=True),
    sa.Column("torrent", sa.LargeBinary, nullable=True),
    sa.Column("downloaded_at", sa.DateTime(timezone=True), nullable=False),
)

skyhook = sa.Table(
    "skyhook",
    metadata,
    sa.Column("imdbid", sa.Integer, primary_key=True),
    sa.Column("tvdbid", sa.Integer, nullable=True),
    sa.Column("response", sa.Text, nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

servarr = sa.Table(
    "servarr",
    metadata,
    sa.Column("imdbid", sa.Integer, primary_key=True),
    sa.Column("tmdbid", sa.Integer, nullable=True),
    sa.Column("response", sa.Text, nullable=True),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
)

electric_offset = sa.Table(
    "electric_offset",
    metadata,
    sa.Column("shape_name", sa.Text, primary_key=True),
    sa.Column("handle", sa.Text, nullable=True),
    sa.Column("offset", sa.Text, nullable=False),
)

imdb_titles = sa.Table(
    "imdb_titles",
    metadata,
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

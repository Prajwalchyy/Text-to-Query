import sys
import tempfile
import sqlite3
from pathlib import Path
import pytest

root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
src_dir = backend_dir / "src"
for p in [str(root_dir), str(backend_dir), str(src_dir)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from dialects.sql import (
    get_table_names,
    get_table_schema,
    get_table_details,
    get_all_relationships,
    get_sql_schema,
    format_schema_context,
    execute_sql_query,
    compile_sql_scripts_to_db,
    resolve_sqlite_path,
)


def test_chinook_schema_introspection():
    tables = get_table_names()
    assert "Album" in tables
    assert "Artist" in tables
    assert "Invoice" in tables
    assert "Track" in tables
    assert len(tables) == 11

    cols, pks, fks = get_table_details(None, "Album")
    col_names = [c["name"] for c in cols]
    assert "AlbumId" in col_names
    assert "Title" in col_names
    assert "ArtistId" in col_names
    assert pks == ["AlbumId"]
    assert len(fks) == 1
    assert fks[0]["referred_table"] == "Artist"


def test_chinook_relationships():
    rels = get_all_relationships()
    assert len(rels) >= 11
    album_artist_rel = next(
        (r for r in rels if r["from_table"] == "Album" and r["to_table"] == "Artist"),
        None
    )
    assert album_artist_rel is not None
    assert album_artist_rel["from_col"] == "ArtistId"
    assert album_artist_rel["to_col"] == "ArtistId"


def test_chinook_query_execution():
    query = "SELECT ArtistId, Name FROM Artist WHERE Name = 'AC/DC';"
    rows = execute_sql_query(query)
    assert len(rows) == 1
    assert rows[0]["ArtistId"] == 1
    assert rows[0]["Name"] == "AC/DC"


def test_format_schema_context():
    context = format_schema_context()
    assert "Table: Album" in context
    assert "Columns: AlbumId INTEGER, Title NVARCHAR(160), ArtistId INTEGER" in context
    assert "Foreign Keys: ArtistId -> Artist.ArtistId" in context


def test_compile_sql_scripts():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "compiled_test.db"
        scripts = [
            ("users.sql", "CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT NOT NULL); INSERT INTO users VALUES (1, 'alice');"),
            ("posts.sql", "CREATE TABLE posts (id INTEGER PRIMARY KEY, user_id INTEGER, body TEXT); INSERT INTO posts VALUES (1, 1, 'Hello');"),
        ]

        created_tables = compile_sql_scripts_to_db(scripts, db_path)
        assert "users" in created_tables
        assert "posts" in created_tables

        rows = execute_sql_query("SELECT username FROM users;", db_path=db_path)
        assert len(rows) == 1
        assert rows[0]["username"] == "alice"


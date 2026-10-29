"""Søgeindeks: en afledt kopi af biblioteket i SQLite, jf. ADR-0001.

Indekset ligger i add-on'ens datamappe og kan altid slettes. Det bygges op igen
ud fra filerne. Det synkroniseres ud fra filernes ændringstid og størrelse, så
ændringer lavet via Samba ses i næste kald.
"""

import json
import sqlite3
import threading
from collections.abc import Callable
from enum import StrEnum
from pathlib import Path
from typing import Any

from .library import Entry, Library

SCHEMA_VERSION = 1

_DANISH = str.maketrans({"æ": "{", "ä": "{", "ø": "|", "ö": "|", "å": "}"})


def danish_key(text: str) -> str:
    """Sorteringsnøgle, hvor æ, ø og å kommer efter z."""
    return text.casefold().translate(_DANISH)


def _danish_collation(a: str, b: str) -> int:
    ka, kb = danish_key(a), danish_key(b)
    return (ka > kb) - (ka < kb)


class Sorting(StrEnum):
    NYESTE = "nyeste"
    VURDERING = "vurdering"
    ALFABETISK = "alfabetisk"


_ORDER = {
    Sorting.NYESTE: "oprettet DESC NULLS LAST, titel COLLATE da",
    Sorting.VURDERING: "vurdering DESC NULLS LAST, titel COLLATE da",
    Sorting.ALFABETISK: "titel COLLATE da",
}

Summary = dict[str, Any]


class SearchIndex:
    def __init__(self, path: Path, library: Library, summarize: Callable[[Entry], Summary]) -> None:
        self.path = path
        self.library = library
        self.summarize = summarize
        self._lock = threading.Lock()
        self._db = self._open()

    def search(self, query: str = "", sorting: Sorting = Sorting.NYESTE, tag: str | None = None) -> list[Summary]:
        """Opskrifter, hvor alle ord i søgningen står i titel, ingredienser, tags, kilde eller noter."""
        where, params = [], []
        for word in query.casefold().split():
            where.append("instr(tekst, ?) > 0")
            params.append(word)
        if tag:
            where.append("id IN (SELECT id FROM tags WHERE tag = ?)")
            params.append(tag)
        sql = f"SELECT summary FROM recipes {'WHERE ' + ' AND '.join(where) if where else ''} ORDER BY {_ORDER[sorting]}"
        with self._lock:
            self._sync()
            rows = self._db.execute(sql, params).fetchall()
        return [json.loads(summary) for (summary,) in rows]

    def tags(self) -> list[str]:
        with self._lock:
            self._sync()
            rows = self._db.execute("SELECT DISTINCT tag FROM tags").fetchall()
        return sorted((tag for (tag,) in rows), key=danish_key)

    def sync(self) -> None:
        with self._lock:
            self._sync()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def _sync(self) -> None:
        files = {file.id: file for file in self.library.files()}
        known = {
            id: (mtime, size) for id, mtime, size in self._db.execute("SELECT id, mtime_ns, size FROM recipes")
        }
        with self._db:
            for id in known.keys() - files.keys():
                self._delete(id)
            for id, file in files.items():
                if known.get(id) != (file.mtime_ns, file.size):
                    entry = self.library.get(id)
                    if entry is None:
                        self._delete(id)
                    else:
                        self._store(entry, file.mtime_ns, file.size)

    def _delete(self, id: str) -> None:
        self._db.execute("DELETE FROM recipes WHERE id = ?", (id,))
        self._db.execute("DELETE FROM tags WHERE id = ?", (id,))

    def _store(self, entry: Entry, mtime_ns: int, size: int) -> None:
        opskrift = entry.opskrift
        title = opskrift.titel or entry.id
        words = [title, entry.id, opskrift.kilde or "", opskrift.noter or "", *opskrift.tags]
        words += [line.navn for group in opskrift.ingredienser for line in group.linjer]
        self._delete(entry.id)
        self._db.execute(
            "INSERT INTO recipes (id, mtime_ns, size, titel, oprettet, vurdering, tekst, summary) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                entry.id,
                mtime_ns,
                size,
                title,
                opskrift.oprettet.isoformat() if opskrift.oprettet else None,
                opskrift.vurdering,
                "\n".join(words).casefold(),
                json.dumps(self.summarize(entry)),
            ),
        )
        self._db.executemany("INSERT INTO tags (id, tag) VALUES (?, ?)", [(entry.id, tag) for tag in set(opskrift.tags)])

    def _open(self) -> sqlite3.Connection:
        """Åbner indekset. Et ødelagt eller forældet indeks slettes og bygges op igen ud fra filerne."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            return self._connect()
        except sqlite3.DatabaseError:
            self.path.unlink(missing_ok=True)
            return self._connect()

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path, check_same_thread=False)
        try:
            db.create_collation("da", _danish_collation)
            if db.execute("PRAGMA user_version").fetchone()[0] != SCHEMA_VERSION:
                db.executescript(
                    f"""
                    DROP TABLE IF EXISTS recipes;
                    DROP TABLE IF EXISTS tags;
                    CREATE TABLE recipes (
                        id TEXT PRIMARY KEY, mtime_ns INTEGER, size INTEGER, titel TEXT,
                        oprettet TEXT, vurdering INTEGER, tekst TEXT, summary TEXT
                    );
                    CREATE TABLE tags (id TEXT, tag TEXT);
                    CREATE INDEX tags_tag ON tags (tag);
                    PRAGMA user_version = {SCHEMA_VERSION};
                    """
                )
        except sqlite3.DatabaseError:
            db.close()
            raise
        return db

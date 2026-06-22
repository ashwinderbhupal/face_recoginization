"""Sighting event store (SQLite) + in-process pub/sub for live SSE streaming.

A single EventHub instance owns the database connection and a set of subscriber
queues. Recognitions are persisted *and* pushed to any connected SSE clients.
"""

import json
import os
import queue
import sqlite3
import threading
import time


class EventHub:
    def __init__(self, db_path):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        self._subscribers = set()   # set[queue.Queue]
        self._sub_lock = threading.Lock()

    def _init_schema(self):
        with self._lock:
            self._conn.execute(
                """CREATE TABLE IF NOT EXISTS events (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts        REAL    NOT NULL,
                    name      TEXT    NOT NULL,
                    confidence REAL   NOT NULL,
                    known     INTEGER NOT NULL,
                    alert     INTEGER NOT NULL DEFAULT 0,
                    source    TEXT,
                    snapshot  TEXT
                )"""
            )
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts)")
            self._conn.commit()

    # ---- writes ---------------------------------------------------------
    def record(self, name, confidence, known, alert=False, source=None,
               snapshot=None):
        ts = time.time()
        with self._lock:
            cur = self._conn.execute(
                "INSERT INTO events (ts,name,confidence,known,alert,source,snapshot)"
                " VALUES (?,?,?,?,?,?,?)",
                (ts, name, float(confidence), int(bool(known)),
                 int(bool(alert)), source, snapshot),
            )
            self._conn.commit()
            event = {
                "id": cur.lastrowid, "ts": ts, "name": name,
                "confidence": round(float(confidence), 1),
                "known": bool(known), "alert": bool(alert),
                "source": source, "snapshot": snapshot,
            }
        self._publish(event)
        return event

    # ---- reads ----------------------------------------------------------
    def recent(self, limit=50):
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(r) for r in rows]

    def stats(self, hours=24):
        since = time.time() - hours * 3600
        with self._lock:
            total = self._conn.execute(
                "SELECT COUNT(*) c FROM events WHERE ts>=?", (since,)
            ).fetchone()["c"]
            known = self._conn.execute(
                "SELECT COUNT(*) c FROM events WHERE ts>=? AND known=1", (since,)
            ).fetchone()["c"]
            per_person = self._conn.execute(
                "SELECT name, COUNT(*) c FROM events WHERE ts>=? "
                "GROUP BY name ORDER BY c DESC LIMIT 20", (since,)
            ).fetchall()
            rows = self._conn.execute(
                "SELECT ts FROM events WHERE ts>=?", (since,)
            ).fetchall()
        buckets = {}
        for r in rows:
            hr = int(r["ts"] // 3600)
            buckets[hr] = buckets.get(hr, 0) + 1
        timeline = [{"hour": h, "count": c} for h, c in sorted(buckets.items())]
        return {
            "hours": hours,
            "total": total,
            "known": known,
            "unknown": total - known,
            "per_person": [dict(r) for r in per_person],
            "timeline": timeline,
        }

    def clear(self):
        with self._lock:
            self._conn.execute("DELETE FROM events")
            self._conn.commit()

    # ---- pub/sub for SSE ------------------------------------------------
    def subscribe(self):
        q = queue.Queue(maxsize=100)
        with self._sub_lock:
            self._subscribers.add(q)
        return q

    def unsubscribe(self, q):
        with self._sub_lock:
            self._subscribers.discard(q)

    def _publish(self, event):
        data = json.dumps(event)
        with self._sub_lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(data)
                except queue.Full:
                    dead.append(q)
            for q in dead:
                self._subscribers.discard(q)

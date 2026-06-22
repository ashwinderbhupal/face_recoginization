"""Database helpers: store, load and match ArcFace embeddings."""

import os
import pickle

import numpy as np

import config
from face_engine import cosine_similarity


def load_database():
    if not os.path.exists(config.DB_PATH):
        return {"names": [], "embeddings": []}
    with open(config.DB_PATH, "rb") as f:
        return pickle.load(f)


def save_database(db):
    os.makedirs(config.DATABASE_DIR, exist_ok=True)
    with open(config.DB_PATH, "wb") as f:
        pickle.dump(db, f)


def add_embedding(db, name, embedding):
    db["names"].append(name)
    db["embeddings"].append(np.asarray(embedding, dtype=np.float32))


def recognize(embedding, db, threshold=None):
    """
    Match an embedding against the database using cosine similarity.

    Returns (name, similarity). name is "Unknown" if the best match is below
    `threshold`. similarity is in the 0..100 range for display.
    """
    if threshold is None:
        threshold = config.DEFAULT_THRESHOLD

    if not db["embeddings"]:
        return "Unknown", 0.0

    sims = [cosine_similarity(embedding, e) for e in db["embeddings"]]
    best_idx = int(np.argmax(sims))
    best_sim = sims[best_idx]
    pct = round(max(best_sim, 0.0) * 100, 1)

    if best_sim >= threshold:
        return db["names"][best_idx], pct
    return "Unknown", pct

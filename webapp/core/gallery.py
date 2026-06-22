"""Person photo gallery management over config.PHOTOS_DIR.

Each person is a sub-folder of PHOTOS_DIR containing their images. These helpers
list/add/delete photos and rename or delete people, keeping the pickled face
database in sync where relevant.
"""

import os
import shutil

import config

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def _safe_name(name):
    """Reject path-traversal; return a clean folder/person name."""
    name = (name or "").strip().strip(".")
    if not name or os.path.sep in name or (os.path.altsep and os.path.altsep in name) \
            or ".." in name:
        raise ValueError("invalid name")
    return name


def _safe_file(filename):
    base = os.path.basename(filename or "")
    if not base or base.startswith(".") or ".." in base:
        raise ValueError("invalid filename")
    if os.path.splitext(base)[1].lower() not in IMAGE_EXTS:
        raise ValueError("unsupported file type")
    return base


def person_dir(name):
    return os.path.join(config.PHOTOS_DIR, _safe_name(name))


def list_photos(name):
    d = person_dir(name)
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d)
                  if os.path.splitext(f)[1].lower() in IMAGE_EXTS)


def list_people(db=None):
    """Return people known from photos/ AND from the DB, merged."""
    counts = {}
    if db is not None:
        for n in db["names"]:
            counts[n] = counts.get(n, 0) + 1
    people = {}
    root = config.PHOTOS_DIR
    if os.path.isdir(root):
        for entry in sorted(os.listdir(root)):
            full = os.path.join(root, entry)
            if os.path.isdir(full):
                photos = list_photos(entry)
                people[entry] = {
                    "name": entry,
                    "photo_count": len(photos),
                    "db_count": counts.get(entry, 0),
                    "thumbnails": photos[:4],
                }
    # people that are in the DB but have no photos folder
    for n, c in counts.items():
        if n not in people:
            people[n] = {"name": n, "photo_count": 0, "db_count": c,
                         "thumbnails": []}
    return sorted(people.values(), key=lambda p: p["name"].lower())


def photo_path(name, filename):
    return os.path.join(person_dir(name), _safe_file(filename))


def add_photo_bytes(name, filename, data):
    name = _safe_name(name)
    d = person_dir(name)
    os.makedirs(d, exist_ok=True)
    base = _safe_file(filename)
    dest = os.path.join(d, base)
    # avoid clobbering: add numeric suffix if needed
    stem, ext = os.path.splitext(base)
    i = 1
    while os.path.exists(dest):
        dest = os.path.join(d, f"{stem}_{i}{ext}")
        i += 1
    with open(dest, "wb") as f:
        f.write(data)
    return os.path.basename(dest)


def delete_photo(name, filename):
    p = photo_path(name, filename)
    if os.path.exists(p):
        os.remove(p)
        return True
    return False


def delete_person(name, db=None, save_database=None):
    name = _safe_name(name)
    d = person_dir(name)
    removed_photos = os.path.isdir(d)
    if removed_photos:
        shutil.rmtree(d)
    removed_db = 0
    if db is not None:
        keep = [i for i, n in enumerate(db["names"]) if n != name]
        removed_db = len(db["names"]) - len(keep)
        db["names"] = [db["names"][i] for i in keep]
        db["embeddings"] = [db["embeddings"][i] for i in keep]
        if save_database:
            save_database(db)
    return {"photos_removed": removed_photos, "db_removed": removed_db}


def rename_person(old, new, db=None, save_database=None):
    old = _safe_name(old)
    new = _safe_name(new)
    src = person_dir(old)
    dst = person_dir(new)
    if os.path.isdir(src):
        if os.path.exists(dst):
            # merge photos into existing folder
            for f in os.listdir(src):
                shutil.move(os.path.join(src, f), os.path.join(dst, f))
            os.rmdir(src)
        else:
            os.rename(src, dst)
    renamed = 0
    if db is not None:
        for i, n in enumerate(db["names"]):
            if n == old:
                db["names"][i] = new
                renamed += 1
        if save_database and renamed:
            save_database(db)
    return {"renamed": renamed}

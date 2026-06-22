"""
Build the face database from the photos/ folder.

Each sub-folder of photos/ is treated as one person:

    photos/Alice/*.jpg     -> person "Alice"
    photos/Bob Smith/*.jpg -> person "Bob Smith"

Usage:
    python enroll.py                 # rebuild DB from scratch from photos/
    python enroll.py --append        # add photos/ people without wiping existing DB
"""

import argparse
import os

import cv2

import config
from db_utils import add_embedding, load_database, save_database
from face_engine import detect_faces, largest_face

SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def enroll_image(name, path, db):
    image = cv2.imread(path)
    if image is None:
        print(f"    skip (cannot read): {os.path.basename(path)}")
        return 0

    faces = detect_faces(image)
    if not faces:
        print(f"    skip (no face): {os.path.basename(path)}")
        return 0

    face = largest_face(faces)
    if len(faces) > 1:
        print(f"    {len(faces)} faces in {os.path.basename(path)} -> using largest")

    add_embedding(db, name, face.normed_embedding)
    print(f"    + {os.path.basename(path)}")
    return 1


def main():
    parser = argparse.ArgumentParser(description="Build face DB from the photos/ folder")
    parser.add_argument("--append", action="store_true",
                        help="Add to the existing database instead of rebuilding")
    args = parser.parse_args()

    if not os.path.isdir(config.PHOTOS_DIR):
        print(f"No photos folder at {config.PHOTOS_DIR}")
        return

    people = sorted(
        d for d in os.listdir(config.PHOTOS_DIR)
        if os.path.isdir(os.path.join(config.PHOTOS_DIR, d))
    )
    if not people:
        print("No person sub-folders found in photos/. See photos/README.txt for the layout.")
        return

    db = load_database() if args.append else {"names": [], "embeddings": []}

    grand_total = 0
    for person in people:
        person_dir = os.path.join(config.PHOTOS_DIR, person)
        images = [
            os.path.join(person_dir, f)
            for f in sorted(os.listdir(person_dir))
            if os.path.splitext(f)[1].lower() in SUPPORTED
        ]
        if not images:
            continue

        print(f"\n{person}:")
        person_count = sum(enroll_image(person, img, db) for img in images)
        grand_total += person_count
        print(f"  -> {person_count} encoding(s)")

    save_database(db)
    n_people = len(set(db["names"]))
    print(f"\nDatabase saved: {grand_total} new encoding(s), "
          f"{len(db['names'])} total across {n_people} person(s).")


if __name__ == "__main__":
    main()

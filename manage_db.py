"""
Manage the face recognition database.

Usage:
    python manage_db.py --list              # show all registered people
    python manage_db.py --remove "Name"     # remove all encodings for a person
    python manage_db.py --clear             # wipe the entire database (asks for confirmation)
    python manage_db.py --stats             # show encoding counts per person
"""

import argparse
from collections import Counter

from db_utils import load_database, save_database


def cmd_list(db):
    if not db["names"]:
        print("Database is empty.")
        return
    people = sorted(set(db["names"]))
    counts = Counter(db["names"])
    print(f"{'Name':<30} {'Encodings':>10}")
    print("-" * 42)
    for name in people:
        print(f"{name:<30} {counts[name]:>10}")
    print("-" * 42)
    print(f"Total: {len(people)} person(s), {len(db['names'])} encoding(s)")


def cmd_remove(db, name):
    indices_to_keep = [i for i, n in enumerate(db["names"]) if n != name]
    removed = len(db["names"]) - len(indices_to_keep)
    if removed == 0:
        print(f"'{name}' not found in database.")
        return
    db["names"] = [db["names"][i] for i in indices_to_keep]
    db["embeddings"] = [db["embeddings"][i] for i in indices_to_keep]
    save_database(db)
    print(f"Removed {removed} encoding(s) for '{name}'.")


def cmd_clear(db):
    answer = input("This will delete ALL faces from the database. Type 'yes' to confirm: ")
    if answer.strip().lower() == "yes":
        db["names"].clear()
        db["embeddings"].clear()
        save_database(db)
        print("Database cleared.")
    else:
        print("Cancelled.")


def main():
    parser = argparse.ArgumentParser(description="Manage the face recognition database")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="List all registered people")
    group.add_argument("--stats", action="store_true", help="Alias for --list")
    group.add_argument("--remove", metavar="NAME", help="Remove a person by name")
    group.add_argument("--clear", action="store_true", help="Wipe the entire database")
    args = parser.parse_args()

    db = load_database()

    if args.list or args.stats:
        cmd_list(db)
    elif args.remove:
        cmd_remove(db, args.remove)
    elif args.clear:
        cmd_clear(db)


if __name__ == "__main__":
    main()

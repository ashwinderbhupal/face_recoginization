"""
Add a person's face to the recognition database.

Usage:
    python add_face.py "Name"                    # capture from webcam (SPACE to grab)
    python add_face.py "Name" --image photo.jpg  # add from one image
    python add_face.py "Name" --images folder/   # add every image in a folder
    python add_face.py "Name" --save-photos      # also copy webcam shots into photos/Name/
    python add_face.py "Name" --source rtsp://user:pass@192.168.0.24:554/stream1  # IP camera
"""

import argparse
import os
import time

import cv2

import config
from camera import open_camera
from db_utils import add_embedding, load_database, save_database
from face_engine import detect_faces, largest_face

SUPPORTED = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def add_from_image(name, image_path, db):
    image = cv2.imread(image_path)
    if image is None:
        print(f"  cannot read: {image_path}")
        return 0
    faces = detect_faces(image)
    if not faces:
        print(f"  no face in: {os.path.basename(image_path)}")
        return 0
    face = largest_face(faces)
    add_embedding(db, name, face.normed_embedding)
    print(f"  + {os.path.basename(image_path)}")
    return 1


def add_from_folder(name, folder, db):
    total = 0
    for fname in sorted(os.listdir(folder)):
        if os.path.splitext(fname)[1].lower() in SUPPORTED:
            total += add_from_image(name, os.path.join(folder, fname), db)
    return total


def add_from_webcam(name, db, save_photos, source=0):
    cap = open_camera(source)
    if cap is None:
        if isinstance(source, str):
            print(f"ERROR: cannot open stream {source!r}. Test the URL in VLC and "
                  "check the camera is reachable on your network.")
        else:
            print("ERROR: cannot open webcam (no working backend). "
                  "Is another app using the camera, or is camera access blocked in "
                  "Windows Settings > Privacy > Camera?")
        return 0

    photo_dir = os.path.join(config.PHOTOS_DIR, name)
    if save_photos:
        os.makedirs(photo_dir, exist_ok=True)

    print(f"\nAdding '{name}'. Controls: SPACE = capture | Q = done")
    captured = 0
    read_failures = 0

    while True:
        ok, frame = cap.read()
        if not ok or frame is None:
            read_failures += 1
            if read_failures > 30:
                print("ERROR: lost the camera feed (too many empty frames).")
                break
            continue
        read_failures = 0

        faces = detect_faces(frame)
        for f in faces:
            x1, y1, x2, y2 = f.bbox.astype(int)
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        cv2.putText(frame, f"Captured: {captured}   SPACE=grab  Q=done",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Add Face", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord(" "):
            face = largest_face(faces)
            if face is None:
                print("  no face in frame, try again")
                continue
            add_embedding(db, name, face.normed_embedding)
            captured += 1
            print(f"  captured #{captured}")
            if save_photos:
                fname = os.path.join(photo_dir, f"{name}_{int(time.time()*1000)}.jpg")
                cv2.imwrite(fname, frame)
        elif key == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()
    return captured


def main():
    parser = argparse.ArgumentParser(description="Add a face to the database")
    parser.add_argument("name", help="Person's name")
    parser.add_argument("--image", help="Single image file")
    parser.add_argument("--images", help="Folder of images")
    parser.add_argument("--save-photos", action="store_true",
                        help="Also save webcam captures into photos/<Name>/")
    parser.add_argument("--source", default=None,
                        help="Webcam index or stream URL (rtsp://...) for capture. "
                             "Defaults to config.CAMERA_SOURCE / the FACE_RTSP_URL env var.")
    args = parser.parse_args()

    name = args.name.strip()
    db = load_database()

    if args.image:
        count = add_from_image(name, args.image, db)
    elif args.images:
        count = add_from_folder(name, args.images, db)
    else:
        count = add_from_webcam(name, db, args.save_photos,
                                source=config.resolve_source(args.source))

    if count > 0:
        save_database(db)
        total = db["names"].count(name)
        print(f"\nDone. '{name}' now has {total} encoding(s) in the database.")
    else:
        print("\nNo faces were added.")


if __name__ == "__main__":
    main()

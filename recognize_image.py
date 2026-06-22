"""
Recognize faces in a static image (InsightFace / ArcFace).

Usage:
    python recognize_image.py photo.jpg
    python recognize_image.py photo.jpg --threshold 0.45 --no-display
"""

import argparse
import os
import sys

import cv2

import config
from db_utils import load_database, recognize
from face_engine import detect_faces


def main():
    parser = argparse.ArgumentParser(description="Recognize faces in an image")
    parser.add_argument("image", help="Path to the image file")
    parser.add_argument("--threshold", type=float, default=config.DEFAULT_THRESHOLD,
                        help=f"Cosine match threshold (default {config.DEFAULT_THRESHOLD})")
    parser.add_argument("--no-display", action="store_true", help="Don't open a window")
    args = parser.parse_args()

    if not os.path.isfile(args.image):
        print(f"ERROR: file not found: {args.image}")
        sys.exit(1)

    db = load_database()
    if not db["embeddings"]:
        print("Database is empty. Run enroll.py or add_face.py first.")
        sys.exit(1)

    image = cv2.imread(args.image)
    if image is None:
        print(f"ERROR: cannot read image: {args.image}")
        sys.exit(1)

    faces = detect_faces(image)
    print(f"Detected {len(faces)} face(s):" if faces else "No faces detected.")

    for face in faces:
        name, sim = recognize(face.normed_embedding, db, threshold=args.threshold)
        x1, y1, x2, y2 = face.bbox.astype(int)
        color = (0, 200, 0) if name != "Unknown" else (0, 0, 220)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 2)
        label = f"{name} {sim:.0f}%"
        ly = y1 - 8 if y1 > 25 else y2 + 22
        cv2.putText(image, label, (x1, ly), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        print(f"  {label}")

    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    base, ext = os.path.splitext(os.path.basename(args.image))
    out_path = os.path.join(config.OUTPUT_DIR, f"{base}_recognized{ext}")
    cv2.imwrite(out_path, image)
    print(f"\nSaved annotated image to: {out_path}")

    if not args.no_display:
        cv2.imshow("Result", image)
        print("Press any key to close.")
        cv2.waitKey(0)
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

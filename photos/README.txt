PHOTOS FOLDER
=============

Put your known people here, one sub-folder per person. The sub-folder name
is used as the person's name.

Example layout:

    photos/
        Alice/
            alice1.jpg
            alice2.jpg
            alice3.png
        Bob Smith/
            bob_front.jpg
            bob_side.jpg

Tips for good accuracy:
  - 3 to 10 clear photos per person, different angles and lighting.
  - One face per photo is ideal. If a photo has several faces, the largest
    is used.
  - Supported formats: .jpg .jpeg .png .bmp .webp

After adding photos, build/refresh the database with:

    python enroll.py

You can also add people directly from a webcam:

    python add_face.py "Name"

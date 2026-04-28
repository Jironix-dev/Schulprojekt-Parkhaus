import re
from pathlib import Path

import cv2
from picamera2 import Picamera2

IMAGE_DIR = Path("images")
IMAGE_PATTERN = re.compile(r"^(\d{4})\.jpg$")
IMAGE_FORMAT = "jpg"
IMAGE_WIDTH = 1280
IMAGE_HEIGHT = 720


def ensure_image_folder() -> Path:
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    return IMAGE_DIR


def get_next_image_index(image_dir: Path) -> int:
    highest = 0
    for path in image_dir.iterdir():
        if not path.is_file():
            continue
        match = IMAGE_PATTERN.match(path.name)
        if match:
            try:
                value = int(match.group(1))
            except ValueError:
                continue
            highest = max(highest, value)
    return highest + 1


def build_image_path(image_dir: Path, index: int) -> Path:
    filename = f"{index:04d}.{IMAGE_FORMAT}"
    return image_dir / filename


def add_overlay(frame, text: str) -> None:
    cv2.putText(
        frame,
        text,
        (10, 30),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.9,
        (255, 255, 255),
        2,
        cv2.LINE_AA,
    )


def main() -> None:
    image_dir = ensure_image_folder()
    next_index = get_next_image_index(image_dir)

    picam2 = Picamera2()
    camera_config = picam2.create_preview_configuration(
        main={"size": (IMAGE_WIDTH, IMAGE_HEIGHT)}
    )
    picam2.configure(camera_config)
    picam2.start()

    window_name = "Live Feed - Drücke ENTER zum Speichern, ESC zum Beenden"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    try:
        while True:
            frame = picam2.capture_array()
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            add_overlay(rgb_frame, f"Bild {next_index:04d} | ENTER=Speichern | ESC=Beenden")
            cv2.imshow(window_name, rgb_frame)

            key = cv2.waitKey(10) & 0xFF
            if key == 27:  # ESC
                print("Programm wird beendet...")
                break
            if key in (13, 10):  # ENTER
                image_path = build_image_path(image_dir, next_index)
                saved = cv2.imwrite(str(image_path), rgb_frame)
                if saved:
                    print(f"Bild gespeichert: {image_path}")
                    next_index += 1
                else:
                    print(f"Fehler beim Speichern von {image_path}")
    finally:
        picam2.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()

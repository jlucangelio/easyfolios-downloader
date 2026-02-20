import subprocess
import cv2
import numpy as np
import time
import os
import argparse

def take_screenshot(output_path="screen.png"):
    """
    Captures the device screen using ADB and saves it to a file.
    """
    try:
        # Execute adb command to capture screen and pipe it to a file
        # This is often faster than 'adb shell screencap -p /sdcard/screen.png' + 'adb pull'
        with open(output_path, "wb") as f:
            subprocess.check_call(["adb", "exec-out", "screencap", "-p"], stdout=f)
        print(f"Screenshot saved to {output_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error taking screenshot: {e}")
        return False
    except FileNotFoundError:
        print("ADB not found. Please ensure Android Debug Bridge is installed and in your PATH.")
        return False


def find_element(template_path, screen_path="screen.png", threshold=0.8):
    """
    Locates a UI element (template) within the screenshot.
    Returns the (x, y) coordinates of the center of the match, or None if not found.
    """
    if not os.path.exists(template_path):
        print(f"Template file not found: {template_path}")
        return None

    if not os.path.exists(screen_path):
        print(f"Screenshot file not found: {screen_path}")
        return None

    # Load images
    img_rgb = cv2.imread(screen_path)
    template = cv2.imread(template_path)

    if img_rgb is None or template is None:
        print("Error loading images.")
        return None

    h, w = template.shape[:2]

    # Perform template matching
    res = cv2.matchTemplate(img_rgb, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        # max_loc is the top-left corner of the match
        center_x = max_loc[0] + w // 2
        center_y = max_loc[1] + h // 2
        # print(f"Found element '{template_path}' at ({center_x}, {center_y}) with confidence {max_val:.2f}")
        return (center_x, center_y)
    else:
        print(f"Element '{template_path}' not found. Max confidence: {max_val:.2f}")
        return None


def find_all_elements(template_path, screen_path="screen.png", threshold=0.8):
    """
    Locates all occurrences of a UI element (template) within the screenshot.
    Returns a list of (x, y) coordinates of the centers of the matches.
    """
    if not os.path.exists(template_path):
        print(f"Template file not found: {template_path}")
        return []

    if not os.path.exists(screen_path):
        print(f"Screenshot file not found: {screen_path}")
        return []

    # Load images
    img_rgb = cv2.imread(screen_path)
    template = cv2.imread(template_path)

    if img_rgb is None or template is None:
        print("Error loading images.")
        return []

    h, w = template.shape[:2]

    # Perform template matching
    res = cv2.matchTemplate(img_rgb, template, cv2.TM_CCOEFF_NORMED)

    # Find all matches above threshold
    loc = np.where(res >= threshold)

    # loc is a tuple of arrays (y_coords, x_coords)
    # Zip them into (x, y) points
    points = list(zip(*loc[::-1]))

    if not points:
        print(f"Element '{template_path}' not found.")
        return []

    # Non-maximum suppression (simple distance-based)
    found_points = []

    # Let's convert points to rectangles [x, y, w, h] for groupRectangles
    rects = []
    for pt in points:
        rects.append([int(pt[0]), int(pt[1]), int(w), int(h)])

    rects, weights = cv2.groupRectangles(rects, 1, 0.2)

    for (x, y, w, h) in rects:
        center_x = x + w // 2
        center_y = y + h // 2
        found_points.append((center_x, center_y))
        # print(f"Found element '{template_path}' at ({center_x}, {center_y})")

    return found_points


def tap_element(x, y):
    """
    Simulates a tap at the given coordinates using ADB.
    """
    try:
        subprocess.check_call(["adb", "shell", "input", "tap", str(x), str(y)])
        # print(f"Tapped at ({x}, {y})")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error tapping element: {e}")
        return False


def scroll(start_x, start_y, end_x, end_y, duration=300):
    """
    Swipes from (start_x, start_y) to (end_x, end_y).
    """
    try:
        subprocess.check_call(["adb", "shell", "input", "swipe", str(start_x), str(start_y), str(end_x), str(end_y),
                               str(duration)])
        # print(f"Scrolled from ({start_x}, {start_y}) to ({end_x}, {end_y})")
        return True
    except subprocess.CalledProcessError:
        return False


def scroll_down_one_entry(current_rightarrow_location):
    """
    Swipes up to scroll down one entry.
    """
    return scroll(500, current_rightarrow_location[1], 500, 450, 1000)


def scroll_down_one_picture(current_download_location):
    """
    Swipes up to scroll down one picture.
    """
    cur_x = 500
    cur_y = current_download_location[1]
    new_y = 495

    return scroll(cur_x, cur_y, cur_x, new_y, 1000)


def download_all_photos_from_entry():
    # Don't loop forever if all detection fails.
    for _ in range(100):
        if not take_screenshot():
            print("Failed to take screenshot.")
            break

        # Figure out if a picture is open by mistake.
        coord = find_element("closepic.png")
        if coord is not None:
            # Picture is open. Close it.
            print("Closing open photo")
            tap_element(*coord)
            time.sleep(1)
            continue

        # Figure out if we're at the end of the entry.
        # There is an "Add your comment" button at the end of every entry.
        coord = find_element("add_your_comment.png")
        if coord is not None:
            # Reached the end.
            coords = find_all_elements("download.png")
            for c in coords:
                if not args.dry_run:
                    # print(f"tapping {c}")
                    print(f"Downloading image at {c}")
                    tap_element(*c)
                    time.sleep(1)
            # Exit the outer loop
            break

        # Otherwise, find the download buttons, download the first picture, and scroll the list
        # until the download button is no longer visible.
        coords = find_all_elements("download.png")
        if len(coords) > 0:
            # print(f"Found {len(coords)} elements at {coords}")
            if not args.dry_run:
                print(f"Downloading image at {coords[0]}")
                tap_element(*coords[0])
                time.sleep(1)
            scroll_down_one_picture(coords[0])
        else:
            # If there are no visible download buttons, scroll the view until the bottom
            # of the current entry is no longer visible.
            scroll(500, 2200, 500, 495, 1000)

    # After downloading all photos from an entry, go back to the main screen.
    # Sometimes the overlay that shows where pictures are downloaded will block the back button, so try a few times.
    for _ in range(5):
        if not take_screenshot():
            break
        time.sleep(1)
        coord = find_element("back.png")
        if coord is not None:
            tap_element(*coord)
            time.sleep(1)
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ADB Automation Script")
    parser.add_argument("--dry-run", action="store_true", help="Perform a dry run without making any changes")
    args = parser.parse_args()

    if args.dry_run:
        print("Dry run mode enabled. No actions will be taken.")

    # Download all photos for one entry.
    # If everything else fails, at least don't loop forever.
    for _ in range(10000):
        # Have we reached the end?
        if take_screenshot():
            if find_element("loadmore.png") is not None:
                break

        # Tap one photo entry.
        if take_screenshot():
            coords = find_all_elements("right.png")
            if len(coords) > 0:
                # print(f"Found {len(coords)} elements at {coords}")
                tap_element(*coords[0])
                time.sleep(1)
                download_all_photos_from_entry()
                scroll_down_one_entry(coords[0])
            else:
                print("No right arrows found.")
                break

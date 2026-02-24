# tracker.py
import cv2
import numpy as np
import csv
import subprocess
import imageio_ffmpeg
from pathlib import Path

# HSV ranges you calibrated
pink_lower = np.array([150, 40, 80])
pink_upper  = np.array([179, 220, 255])

green_lower = np.array([40, 29, 108])
green_upper = np.array([81, 143, 245])

def find_centroids(mask):
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    pts = []
    for c in contours:
        if cv2.contourArea(c) < 50:
            continue
        M = cv2.moments(c)
        if M["m00"] == 0:
            continue
        cx = int(M["m10"]/M["m00"])
        cy = int(M["m01"]/M["m00"])
        pts.append((cx, cy))
    return pts

def angle_between(v1, v2):
    v1 = np.array(v1, float)
    v2 = np.array(v2, float)
    if np.linalg.norm(v1)==0 or np.linalg.norm(v2)==0:
        return np.nan
    dot = np.dot(v1, v2) / (np.linalg.norm(v1)*np.linalg.norm(v2))
    dot = np.clip(dot, -1, 1)
    return float(np.degrees(np.arccos(dot)))

def force_downward(vec):
    x, y = vec
    return vec if y > 0 else -vec

def force_leftward(vec):
    x, y = vec
    return vec if x < 0 else -vec

def process_video(input_path: str, output_video_path: str, output_csv_path: str | None = None) -> dict:
    """
    Reads input video, overlays detections/lines/angle, writes processed mp4.
    Then transcodes to H.264 for phone/browser compatibility.
    Optionally writes CSV of angles.
    """
    input_path = str(input_path)
    output_video_path = str(output_video_path)

    out_dir = Path(output_video_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_path = str(out_dir / "processed_raw.mp4")

    # Optional CSV
    out_csv = None
    writer = None
    csvfile = None
    if output_csv_path is not None:
        out_csv = str(output_csv_path)
        Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
        csvfile = open(out_csv, "w", newline="")
        writer = csv.writer(csvfile)
        writer.writerow(["Frame", "Angle (degrees)"])

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open input video: {input_path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    # Write OpenCV output to RAW file first
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(raw_path, fourcc, fps, (w, h))
    if not out.isOpened():
        cap.release()
        raise RuntimeError("Could not open VideoWriter for raw output")

    prev_pink_vec = None
    prev_green_vec = None
    frame_idx = 0
    frames_with_angle = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame_idx += 1
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

        mask_pink  = cv2.inRange(hsv, pink_lower, pink_upper)
        mask_green = cv2.inRange(hsv, green_lower, green_upper)

        pink_pts  = find_centroids(mask_pink)
        green_pts = find_centroids(mask_green)

        for x,y in pink_pts:
            cv2.circle(frame, (x,y), 10, (0,0,255), -1)
        for x,y in green_pts:
            cv2.circle(frame, (x,y), 10, (0,255,0), -1)

        angle_display = "N/A"

        if len(pink_pts)==2 and len(green_pts)==2:
            p1, p2 = sorted(pink_pts,  key=lambda p:p[1])
            g1, g2 = sorted(green_pts, key=lambda p:p[1])

            pink_vec  = np.array(p2) - np.array(p1)
            green_vec = np.array(g2) - np.array(g1)

            pink_vec  = force_downward(pink_vec)
            green_vec = force_downward(green_vec)
            pink_vec  = force_leftward(pink_vec)
            green_vec = force_leftward(green_vec)

            if prev_pink_vec is not None and np.dot(pink_vec, prev_pink_vec) < 0:
                pink_vec = -pink_vec
            if prev_green_vec is not None and np.dot(green_vec, prev_green_vec) < 0:
                green_vec = -green_vec

            prev_pink_vec = pink_vec
            prev_green_vec = green_vec

            ang = angle_between(pink_vec, green_vec)
            angle_display = f"{ang:.2f}°"
            frames_with_angle += 1

            cv2.line(frame, p1, p2, (0,255,255), 3)
            cv2.line(frame, g1, g2, (0,255,255), 3)

            if writer is not None:
                writer.writerow([frame_idx, ang])

        cv2.putText(frame, "Angle: "+angle_display, (30,60),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255,255,0), 3)

        out.write(frame)

    cap.release()
    out.release()
    if csvfile is not None:
        csvfile.close()

    # Transcode RAW -> H.264 MP4 for phone compatibility
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg, "-y",
        "-i", raw_path,
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        output_video_path
    ]
    subprocess.run(cmd, check=True)

    # Optional cleanup
    try:
        Path(raw_path).unlink(missing_ok=True)
    except Exception:
        pass

    return {
        "frames": frame_idx,
        "frames_with_angle": frames_with_angle,
        "output_video": output_video_path,
        "output_csv": out_csv
    }
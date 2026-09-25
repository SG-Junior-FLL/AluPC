"""Kurzes Testvideo mit Qt selbst erzeugen (Qt ≥ 6.8: QVideoFrameInput + QMediaRecorder)."""

import sys
import time

from PySide6.QtCore import QUrl
from PySide6.QtGui import QColor, QGuiApplication, QImage
from PySide6.QtMultimedia import QMediaCaptureSession, QMediaFormat, QMediaRecorder, QVideoFrame, QVideoFrameInput


def main(path: str, seconds: float = 4.0, fps: int = 10) -> int:
    app = QGuiApplication.instance() or QGuiApplication([])
    session = QMediaCaptureSession()
    frames = QVideoFrameInput()
    session.setVideoFrameInput(frames)
    recorder = QMediaRecorder()
    session.setRecorder(recorder)
    fmt = QMediaFormat(QMediaFormat.MPEG4)
    fmt.setVideoCodec(QMediaFormat.VideoCodec.H264)
    recorder.setMediaFormat(fmt)
    recorder.setVideoFrameRate(fps)
    recorder.setOutputLocation(QUrl.fromLocalFile(path))
    recorder.record()
    total = int(seconds * fps)
    for i in range(total):
        img = QImage(160, 90, QImage.Format_RGB32)
        img.fill(QColor.fromHsv(int(360 * i / total) % 360, 200, 220))
        frame = QVideoFrame(img)
        frame.setStartTime(int(i * 1_000_000 / fps))
        frame.setEndTime(int((i + 1) * 1_000_000 / fps))
        end = time.time() + 2
        while not frames.sendVideoFrame(frame) and time.time() < end:
            app.processEvents()
        app.processEvents()
    recorder.stop()
    end = time.time() + 10
    while recorder.recorderState() != QMediaRecorder.StoppedState and time.time() < end:
        app.processEvents()
        time.sleep(0.02)
    for _ in range(20):
        app.processEvents()
    return 0 if recorder.error() == QMediaRecorder.NoError else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))

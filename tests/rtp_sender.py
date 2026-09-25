"""Test-Sender: schickt ein H.264-Video per RTP an 127.0.0.1:<port> – so wie UxPlay mit
`-vrtp "config-interval=1 ! udpsink host=127.0.0.1 port=<port>"` (Payload 96). Braucht PyAV."""

import sys
import time

import av


def main(port: int, seconds: float = 6.0, fps: int = 25):
    out = av.open(f"rtp://127.0.0.1:{port}", mode="w", format="rtp")
    stream = out.add_stream("libx264", rate=fps)
    stream.width, stream.height, stream.pix_fmt = 320, 180, "yuv420p"
    stream.options = {"tune": "zerolatency", "preset": "ultrafast", "g": "10", "x264-params": "repeat-headers=1"}
    start = time.time()
    i = 0
    while time.time() - start < seconds:
        frame = av.VideoFrame(320, 180, "rgb24")
        plane = frame.planes[0]
        row = bytearray(b"\xe6\x00\x00" * 320)  # rot
        x = (i * 4) % 280
        row[x * 3:(x + 40) * 3] = b"\xff" * 120  # weißes Kästchen wandert
        plane.update(bytes(row) * 180 if plane.line_size == 960 else
                     b"".join(bytes(row) + bytes(plane.line_size - 960) for _ in range(180)))
        for packet in stream.encode(frame):
            out.mux(packet)
        i += 1
        time.sleep(1 / fps)
    out.close()


if __name__ == "__main__":
    main(int(sys.argv[1]), float(sys.argv[2]) if len(sys.argv) > 2 else 6.0)

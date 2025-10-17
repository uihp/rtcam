# Receive WebRTC Camera Stream with [`aiortc`](https://github.com/aiortc/aiortc)

### See also [`BrowserCam`](https://github.com/uihp/BrowserCam)

## Signaling
WebSocket with JSON, message format below:

SDP Exchange (Offer/Answer): same as `RTCSessionDescriptionInit`, `{ type: "offer/anwser", sdp: "<SDP>" }`

ICE Candidate: `{ type: "candidate", candidate: RTCLocalIceCandidateInit | undefined }`

## Example
```python
import cv2
from rtcam import CameraThread

camera = CameraThread(f'wss://{signaling_server_addr}/signal')
camera.start()

while True:
    if camera.frame is None: continue
    cv2.imshow("Browser Camera", camera.frame.to_ndarray(format='bgr24'))
    if cv2.waitKey(1) == 27: break
```

import asyncio
import websockets
import json
import threading
from time import sleep
from concurrent.futures import CancelledError
from aiortc.mediastreams import MediaStreamError
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.signaling import object_from_string, object_to_string

class WebRTC:
    def __init__(self, websocket_signaling_server_url):
        self.url = websocket_signaling_server_url
        self.track = None
        self.state = 'created'
        self._recv_future = None
        self.__create()
    def __create(self):
        self.cancel_recv_future()
        self.peer_conn = RTCPeerConnection()
        @self.peer_conn.on('connectionstatechange')
        async def _():
            self.state = self.peer_conn.connectionState
            print('peer', self.state)
            if self.state == 'closed': self.__create()
            if self.state == 'failed': await self.peer_conn.close()
        @self.peer_conn.on('track')
        def _(track):
            assert track.kind == 'video', 'Not video track'
            print('track detected')
            if self.track:
                self.track.stop()
                self.cancel_recv_future()
            self.track = track
    async def handle_signal(self, signal_dict):
        match signal_dict:
            case { 'type': 'offer' }:
                print('offer received')
                await self.peer_conn.setRemoteDescription(RTCSessionDescription(**signal_dict))
                answer = await self.peer_conn.createAnswer()
                await self.peer_conn.setLocalDescription(answer)
                return object_to_string(self.peer_conn.localDescription)
            case { 'type': 'candidate', 'candidate': candidate }:
                if candidate is None: return print('candidate ended')
                print('candidate received')
                await self.peer_conn.addIceCandidate(object_from_string(json.dumps({
                    'type': 'candidate',
                    'candidate': candidate['candidate'],
                    'id': candidate['sdpMid'], 'label': candidate['sdpMLineIndex']
                })))
    async def negotiate(self):
        async with websockets.connect(self.url) as websocket:
            print('signaling server connected')
            while True:
                if (resp := await self.handle_signal(json.loads(await websocket.recv()))):
                    await websocket.send(resp)
    def create_loop(self):
        self.loop = asyncio.new_event_loop()
        def async_event_loop_thread():
            asyncio.set_event_loop(self.loop)
            self.loop.run_forever()
        self.thread = threading.Thread(target=async_event_loop_thread, daemon=True)
        self.thread.start()
        self.loop.create_task(self.negotiate())
    async def arecv(self):
        assert self.track, 'No track now'
        assert self.state == 'connected', 'RTCPeerConnection is not connected'
        return await self.track.recv()
    def recv(self):
        self._recv_future = asyncio.run_coroutine_threadsafe(self.arecv(), self.loop)
        return self._recv_future.result()
    def cancel_recv_future(self):
        if self._recv_future: self._recv_future.cancel()

class CameraThread:
    def __init__(self, signal_server):
        self.__webrtc = WebRTC(signal_server)
        self.__running = False
        self.frame = None
    def start(self):
        if self.__running: return
        self.__running = True
        def browsercam_thread():
            self.__webrtc.create_loop()
            while self.__running:
                if self.__webrtc.state != 'connected': sleep(0.02)
                try: self.frame = self.__webrtc.recv()
                except (CancelledError, MediaStreamError, AssertionError): self.frame = None
        self.thread = threading.Thread(target=browsercam_thread, daemon=True)
        self.thread.start()
    def stop(self, timeout=1):
        if not self.__running: return
        self.__running = False
        self.__webrtc.cancel_recv_future()
        self.thread.join(timeout)
        assert not self.thread.is_alive(), 'Failed to stop the camera thread'

if __name__ == '__main__':
    import cv2
    camera = CameraThread('wss://192.168.1.106:5000/browsercam/signal')
    camera.start()
    while True:
        if camera.frame is None: continue
        cv2.imshow("Browser Camera", camera.frame.to_ndarray(format='bgr24'))
        if cv2.waitKey(1) == 27: break



from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.mediastreams import MediaStreamError
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import numpy
from pydantic import BaseModel

import audioproc


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Offer(BaseModel):
    sdp: str
    type: str


@app.post("/offer/")
async def handle_offer(offer: Offer):
    pc = RTCPeerConnection()
    offer_sdp = RTCSessionDescription(sdp=offer.sdp, type=offer.type)

    @pc.on("datachannel")
    def on_datachannel(channel):
        print("Debug: Datachannel event triggered")
        # Handle data channel events here

    @pc.on("iceconnectionstatechange")
    def on_iceconnectionstatechange():
        print("ICE Connection State is:", pc.iceConnectionState)

    @pc.on("track")
    async def on_track(track):
        if isinstance(track, MediaStreamTrack):
            samples = None
            i = 0
            while True:
                try:
                    frame = await track.recv()
                    if samples is None:
                        min_data_length = int(2 * frame.sample_rate)
                        print("Recording...")
                except MediaStreamError:
                    print("Disconnected")
                    audioproc.save_as_mp3(
                        samples, frame.sample_rate, i)
                    return

                # Accumulate samples
                ndar = frame.to_ndarray()[0][::2]
                if samples is None:
                    samples = ndar
                else:
                    samples = numpy.concatenate((samples, ndar))

                # Only start detecting silence after accumulating enough data
                if len(samples) < min_data_length:
                    continue

                # Run silence detection
                while True:
                    detected = audioproc.detect_silence(samples)
                    if detected is None:
                        break
                    (start_sample, end_sample) = detected
                    if not start_sample:
                        samples = samples[end_sample:]
                        continue
                    print("saving segment", i, start_sample)
                    audioproc.save_as_mp3(
                        samples[:start_sample], frame.sample_rate, i)
                    i += 1
                    samples = samples[end_sample:]

    await pc.setRemoteDescription(offer_sdp)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


@app.get("/", response_class=HTMLResponse)
def index():
    return open('index.html').read()

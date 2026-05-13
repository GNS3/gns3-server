/*
 * This file is part of Xpra.
 * Copyright (C) 2021 Tijs van der Zwaan <tijzwa@vpo.nl>
 * Licensed under MPL 2.0, see:
 * http://www.mozilla.org/MPL/2.0/
 *
 */

/*
 * Receives native video packets and decodes them via VideoDecoder.
 * https://developer.mozilla.org/en-US/docs/Web/API/VideoDecoder
 * VideoDecoder is only working in Chrome 94+ and Android
 *
 * Example taken from: https://github.com/w3c/webcodecs/blob/main/explainer.md
 *
 */

const XpraVideoDecoderLoader = {
  hasNativeDecoder() {
    return typeof VideoDecoder !== "undefined";
  },
};

class XpraVideoDecoder {
  constructor() {
    this.initialized = false;
    this.had_first_key = false;
    this.draining = false;

    this.decoder_queue = [];
    this.decoded_frames = [];
    this.erroneous_frame = null;

    this.codec = null;
    this.vp9_params = null;
    this.frameWaitTimeout = 1; // Interval for wait loop while frame is being decoded

    this.frame_threshold = 250;
  }

  prepareVP9params(csc) {
    // Check if we have the right VP9 params before init.
    // This is needed because we can only set the params when the video decoder is created.
    // We close the decoder when the coding changes.
    if (csc === "YUV444P" && this.vp9_params !== ".01.10.08") {
      this.vp9_params = ".01.10.08";
      this._close();
    } else if (csc === "YUV444P10" && this.vp9_params !== ".03.10.10") {
      this.vp9_params = ".03.10.10";
      this._close();
    } else if (this.vp9_params !== ".00.20.08.01.02.02") {
      // chroma shift for YUV420P, both X and Y are downscaled by 2^1
      this.vp9_params = ".00.20.08.01.02.02";
      this._close();
    }
  }

  init(coding) {
    this.draining = false;

    this.codec = this.resolveCodec(coding);
    this.videoDecoder = new VideoDecoder({
      output: this._on_decoded_frame.bind(this),
      error: this._on_decoder_error.bind(this),
    });

    // ToDo: hardwareAcceleration can be "no-preference" / "prefer-hardware" / "prefer-software"
    // Figure out when "prefer-hardware" is the right choise and when not (ie: no GPU, remote session like RDP?)
    this.videoDecoder.configure({
      codec: this.codec,
      hardwareAcceleration: "no-preference",
      optimizeForLatency: true,
      colorSpace: new VideoColorSpace({
        fullRange: true
      })
    });
    this.last_timestamp = 0;
    this.initialized = true;
  }

  resolveCodec(coding) {
    if (coding === "h264") return "avc1.42C01E";
    if (coding === "vp8") return "vp8";
    if (coding === "vp9") return `vp09${this.vp9_params}`;
    throw `No codec defined for coding ${coding}`;
  }

  _on_decoded_frame(videoFrame) {
    if (this.decoder_queue.length === 0) {
      videoFrame.close();
      return;
    }

    // Find the frame
    const frame_timestamp = videoFrame.timestamp;
    let current_frame = this.decoder_queue.filter(
      (q) => q.p[10]["frame"] === frame_timestamp
    );
    if (current_frame.length === 1) {
      // We found our frame!
      this.decoder_queue = this.decoder_queue.filter(
        (q) => q.p[10]["frame"] !== frame_timestamp
      );
      current_frame = current_frame[0];
    } else {
      // We decoded a frame the is no longer queued??
      // TODO: handle error??
      videoFrame.close();
      return;
    }

    if (frame_timestamp === 0) {
      this.last_timestamp = 0;
    }

    if (
      this.decoder_queue.length > this.frame_threshold ||
      this.last_timestamp > frame_timestamp
    ) {
      // Skip if the decoders queue is growing too big or this frames timestamp is smaller then the last one painted.
      videoFrame.close();

      const packet = current_frame.p;
      packet[6] = "throttle";
      packet[7] = null;
      this.decoded_frames.push(packet);
      return;
    }

    this.last_timestamp = frame_timestamp;
    const packet = current_frame.p;

    // Latest possible check for draining
    if (this.draining) {
      videoFrame.close();
      return;
    }

    packet[6] = `frame:${packet[6]}`;
    packet[7] = videoFrame;
    this.decoded_frames.push(packet);
  }

  _on_decoder_error(error) {
    // TODO: Handle error? Or just assume we will catch up?
    this.erroneous_frame = `Error decoding frame: ${error}`;
    console.error(this.erroneous_frame);
  }

  queue_frame(packet) {
    // eslint-disable-next-line no-async-promise-executor
    return new Promise(async (resolve, reject) => {
      const options = packet[10] || {};
      const data = packet[7];
      const packet_sequence = packet[8];

      // H264 (avc1.42C01E) needs key frames
      if (
        this.codec.startsWith("avc1") &&
        !this.had_first_key &&
        !(options["type"] &&
        options["type"] == "IDR")
      ) {
        reject(
          new Error(
            `first h264 frame must be a key frame but packet ${packet_sequence} is not: ${options}`
          )
        );
        return;
      }

      if (this.videoDecoder.state === "closed") {
        reject(new Error("video decoder is closed"));
        return;
      }
      if (this.draining) {
        reject(new Error("video decoder is draining"));
        return;
      }

      this.had_first_key = true;
      this.decoder_queue.push({
        p: packet
      });
      const init = {
        type: options["type"] === "IDR" ? "key" : "delta",
        data,
        timestamp: options["frame"],
      };
      const chunk = new EncodedVideoChunk(init);
      this.videoDecoder.decode(chunk);

      let frame_out = this.decoded_frames.filter(
        (p) => p[8] === packet_sequence
      );
      while (frame_out.length === 0) {
        // Await our frame
        await new Promise((r) => setTimeout(r, this.frameWaitTimeout));
        if (this.erroneous_frame != null) {
          // The last frame was erroneous, break the wait loop
          break;
        }
        frame_out = this.decoded_frames.filter((p) => p[8] === packet_sequence);
      }

      if (this.erroneous_frame != null) {
        // Last frame was erroneous. Reject the promise and reset the state.
        const msg = this.erroneous_frame;
        this.erroneous_frame = null;
        reject(new Error(msg));
      }
      // Remove the frame from decoded frames list
      this.decoded_frames = this.decoded_frames.filter(
        (p) => p[8] !== packet_sequence
      );
      resolve(frame_out[0]);
    });
  }

  _close() {
    if (this.initialized) {
      if (this.videoDecoder.state !== "closed") {
        this.videoDecoder.close();
      }
      this.had_first_key = false;
      this.draining = true;
      this.decoder_queue = [];
    }
    this.initialized = false;
  }
}

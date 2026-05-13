/*
 * This file is part of Xpra.
 * Copyright (C) 2021 Tijs van der Zwaan <tijzwa@vpo.nl>
 * Copyright (c) 2022 Antoine Martin <antoine@xpra.org>
 * Licensed under MPL 2.0, see:
 * http://www.mozilla.org/MPL/2.0/
 *
 */

/*
 * Worker for offscreen decoding.
 */

importScripts("./lib/lz4.js");
importScripts("./VideoDecoder.js");
importScripts("./ImageDecoder.js");
importScripts("./RgbHelpers.js");
importScripts("./Constants.js");

// WindowDecoder for each window we have control over:
const window_decoders = new Map();

// You can change this delay to test decode worker initialization timeouts:
const ACK_DELAY = 0;

const image_coding = [
  "rgb",
  "rgb32",
  "rgb24",
  "jpeg",
  "png",
  "png/P",
  "png/L",
  "webp",
  "avif",
];
const video_coding = [];
if (XpraVideoDecoderLoader.hasNativeDecoder()) {
  // We can support native H264 & VP8 decoding
  video_coding.push("h264", "vp8");
} else {
  console.warn("Offscreen decoding is available for images only");
  console.warn("Please consider using Google Chrome 94+ in a secure (SSL or localhost) context for h264 offscreen decoding support.");
}

const all_encodings = new Set([
  "void",
  ...image_coding,
  ...video_coding,
]);

function send_decode_error(packet, error) {
  packet[7] = null;
  self.postMessage({
    error: `${error}`,
    packet
  });
}


class WindowDecoder {
  constructor(wid, canvas, debug) {
    this.wid = wid;
    this.canvas = canvas;
    this.context = this.canvas.getContext("2d");
    this.debug = debug;

    this.image_decoder = new XpraImageDecoder();
    this.video_decoder = new XpraVideoDecoder();

    this.decode_queue = [];
    this.decode_queue_draining = false;
  }

  decode_error(packet, error) {
    const coding = packet[6];
    const packet_sequence = packet[8];
    const message = `failed to decode '${coding}' draw packet sequence ${packet_sequence}: ${error}`;
    console.error(message);
    packet[7] = null;
    send_decode_error(packet, message);
  }

  queue_draw_packet(packet) {
    if (this.closed) {
      return;
    }
    this.decode_queue.push(packet);
    if (!this.decode_queue_draining) {
      this.process_decode_queue();
    }
  }

  process_decode_queue() {
    this.decode_queue_draining = true;
    const packet = this.decode_queue.shift();
    this.process_packet(packet).then(
      () => {
        if (this.decode_queue.length > 0) {
          // Next
          this.process_decode_queue();
        } else {
          this.decode_queue_draining = false;
        }
      },
      (error) => {
        send_decode_error(packet, error);
        this.decode_queue_draining = false;
      }
    );
  }

  async process_packet(packet) {
    let coding = packet[6];
    const start = performance.now();
    if (coding === "eos" && this.video_decoder) {
      this.video_decoder._close();
      return;
    } else if (coding === "scroll" || coding === "void") {
      // Nothing to do
    } else if (image_coding.includes(coding)) {
      await this.image_decoder.convertToBitmap(packet);
    } else if (video_coding.includes(coding)) {
      if (!this.video_decoder.initialized) {
        this.video_decoder.init(coding);
      }
      packet = await this.video_decoder.queue_frame(packet).catch((error) => {
        this.decode_error(packet, error);
      });
    } else {
      this.decode_error(packet, `unsupported encoding: '${coding}'`);
    }

    // Hold throttle packages for 500 ms to prevent flooding of the VideoDecoder
    if (packet[6] === "throttle") {
      await new Promise((r) => setTimeout(r, 500));
    }

    // Fake packet to send back
    const options = packet[10] || {};
    const decode_time = Math.round(1000 * (performance.now() - start));
    options["decode_time"] = Math.max(0, decode_time);
    // Copy without data
    const clonepacket = packet.map((x, i) => {
      if (i !== 7) {
        return x;
      }
    });
    clonepacket[6] = "offscreen-painted";
    clonepacket[10] = options;

    // Tell the server we are done with this packet
    self.postMessage({
      draw: clonepacket,
      start
    });

    // Paint the packet on screen refresh (if we can use requestAnimationFrame in the worker)
    if (packet[6] === "throttle") {
      return;
    }

    const wid = packet[1];
    const x = packet[2];
    const y = packet[3];
    const w = packet[4];
    const h = packet[5];
    coding = packet[6];
    const image = packet[7];
    this.paint_packet(wid, coding, image, x, y, w, h);
  }

  paint_packet(wid, coding, image, x, y, width, height) {
    let painted = false;
    try {
      // Paint the packet on screen refresh (if we can use requestAnimationFrame in the worker)
      if (typeof requestAnimationFrame == "function") {
        requestAnimationFrame(() => {
          this.do_paint_packet(wid, coding, image, x, y, width, height);
        });
        painted = true;
      }
    } catch {
      // If requestAnimationFrame is a function but it failed somehow (ie forbidden in worker in the current browser) we fall back
      console.error("requestAnimationFrame error for paint packet");
      painted = false;
    } finally {
      if (!painted) {
        // Paint right away
        this.do_paint_packet(wid, coding, image, x, y, width, height);
      }
    }
  }

  do_paint_packet(wid, coding, image, x, y, width, height) {
    // Update the coding propery
    if (!this.canvas) {
      return;
    }
    let context = this.context;
    if (coding.startsWith("bitmap")) {
      // Bitmap paint
      context.imageSmoothingEnabled = false;
      context.clearRect(x, y, width, height);
      context.drawImage(image, 0, 0, width, height, x, y, width, height);
      this.paint_box(coding, context, x, y, width, height);
    } else if (coding === "scroll") {
      let canvas = this.canvas;
      context.imageSmoothingEnabled = false;
      for (let index = 0, stop = image.length; index < stop; ++index) {
        const scroll_data = image[index];
        const sx = scroll_data[0];
        const sy = scroll_data[1];
        const sw = scroll_data[2];
        const sh = scroll_data[3];
        const xdelta = scroll_data[4];
        const ydelta = scroll_data[5];
        context.drawImage(canvas,
            sx, sy, sw, sh,
            sx + xdelta, sy + ydelta, sw, sh,
        );
        this.paint_box(coding, context, sx, sy, sw, sh);
      }
    } else if (coding.startsWith("frame")) {
      context.drawImage(image, 0, 0, width, height, x, y, width, height);
      image.close();
      this.paint_box(coding, context, x, y, width, height);
    }
  }

  paint_box(coding, context, px, py, pw, ph) {
    if (!this.debug) {
      return;
    }
    const source_encoding = coding.split(":")[1] || ""; //ie: "rgb24"
    const box_color = DEFAULT_BOX_COLORS[source_encoding];
    if (box_color) {
      context.strokeStyle = box_color;
      context.lineWidth = 2;
      context.strokeRect(px, py, pw, ph);
    }
  }

  update_geometry(w, h) {
    this.canvas.width = w;
    this.canvas.height = h;
  }

  redraw() {
    console.info("REDRAW requested");
  }

  eos() {
    // Add eos packet to queue to prevent closing the decoder before all packets are proceeded
    const packet = [];
    packet[6] = "eos";
    this.decode_queue.push(packet);
  }

  close() {
    this.eos();
    this.canvas = null;
    this.decode_queue = [];
    this.decode_queue_draining = true;
  }
}

onmessage = function(e) {
  const data = e.data;
  let wd = null;
  switch (data.cmd) {
    case "check": {
      // Check if we support the given encodings.
      const encodings = [...data.encodings];
      const common = encodings.filter((value) => all_encodings.has(value));
      function ack() {
        self.postMessage({
          result: true,
          formats: common
        });
      }
      setTimeout(ack, ACK_DELAY);
      break;
    }
    case "eos":
      wd = window_decoders.get(data.wid);
      if (wd) {
        wd.eos();
      }
      break;
    case "remove":
      wd = window_decoders.get(data.wid);
      if (wd) {
        wd.close();
        window_decoders.delete(data.wid);
      }
      break;
    case "decode": {
      const packet = data.packet;
      const wid = packet[1];
      wd = window_decoders.get(wid);
      if (wd) {
        wd.queue_draw_packet(packet);
      } else {
        send_decode_error(packet,
          `no window decoder found for wid ${wid}, only:${[...window_decoders.keys(),].join(",")}`
        );
      }
      break;
    }
    case "redraw":
      wd = window_decoders.get(data.wid);
      if (wd) {
        wd.redraw();
      }
      break;
    case "canvas":
      // console.log("canvas transfer for window", data.wid, ":", data.canvas, data.debug);
      if (data.canvas) {
        window_decoders.set(
          data.wid,
          new WindowDecoder(data.wid, data.canvas, data.debug)
        );
      }
      break;
    case "canvas-geo":
      wd = window_decoders.get(data.wid);
      if (wd) {
        wd.update_geometry(data.w, data.h);
      }
      break;
    case "close":
      for (const decoder of window_decoders.values()) {
        decoder.close();
      }
      window_decoders.clear();
      break;
    default:
      console.error(`Offscreen decode worker got unknown message: ${data.cmd}`);
  }
};

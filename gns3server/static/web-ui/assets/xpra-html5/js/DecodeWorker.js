/*
 * Copyright (c) 2021 Antoine Martin <antoine@xpra.org>
 */

importScripts("./lib/lz4.js");
importScripts("./RgbHelpers.js");

const on_hold = new Map();

let zerocopy = true;

function decode_eos(wid) {}

function decode_draw_packet(packet, start) {
  const wid = packet[1];
  const width = packet[4];
  const height = packet[5];
  const coding = packet[6];
  const packet_sequence = packet[8];

  function send_back(raw_buffers) {
    const wid_hold = on_hold.get(wid);
    if (wid_hold) {
      //find the highest sequence number which is still lower than this packet
      let seq_holding = 0;
      for (const seq of wid_hold.keys()) {
        if (seq > seq_holding && seq < packet_sequence) {
          seq_holding = seq;
        }
      }
      if (seq_holding) {
        const held = wid_hold.get(seq_holding);
        if (held) {
          held.push([packet, raw_buffers]);
          return;
        }
      }
    }
    do_send_back(packet, raw_buffers);
  }

  function do_send_back(p, raw_buffers) {
    self.postMessage({
      draw: p,
      start
    }, raw_buffers);
  }

  function decode_error(message) {
    self.postMessage({
      error: `${message}`,
      packet,
      start
    });
  }

  function hold() {
    //we're loading asynchronously
    //so ensure that any packet sequence arriving after this one will be put on hold
    //until we have finished decoding this one:
    let wid_hold = on_hold.get(wid);
    if (!wid_hold) {
      wid_hold = new Map();
      on_hold.set(wid, wid_hold);
    }
    wid_hold.set(packet_sequence, []);
    return wid_hold;
  }

  function release() {
    const wid_hold = on_hold.get(wid);
    if (!wid_hold) {
      //could have been cancelled by EOS
      return;
    }
    //release any packets held back by this image:
    const held = wid_hold.get(packet_sequence);
    if (!held) {
      //could have been cancelled by EOS
      return;
    }
    let index;
    for (index = 0; index < held.length; index++) {
      const held_packet = held[index][0];
      const held_raw_buffers = held[index][1];
      do_send_back(held_packet, held_raw_buffers);
    }
    wid_hold.delete(packet_sequence);
    if (wid_hold.size === 0 && on_hold.has(wid)) {
      //this was the last held sequence for this window
      on_hold.delete(wid);
    }
  }

  function send_rgb32_back(data, actual_width, actual_height, options) {
    const img = new ImageData(
      new Uint8ClampedArray(data.buffer),
      actual_width,
      actual_height
    );
    hold();
    createImageBitmap(img, 0, 0, actual_width, actual_height, options).then(
      function(bitmap) {
        packet[6] = "bitmap:rgb32";
        packet[7] = bitmap;
        send_back([bitmap]);
        release();
      },
      function(error) {
        decode_error(
          `failed to create ${actual_width}x${actual_height} rgb32 bitmap from buffer ${data}: ${error}`
        );
        release();
      }
    );
  }

  let options = {};
  if (packet.length > 10) options = packet[10];
  const bitmap_options = {
    premultiplyAlpha: "none",
  };
  const scaled_size = options["scaled_size"];
  if (scaled_size) {
    delete options["scaled-size"];
    bitmap_options["resizeWidth"] = width;
    bitmap_options["resizeHeight"] = height;
    bitmap_options["resizeQuality"] = "medium";
  }
  try {
    if (coding === "rgb24" || coding === "rgb32") {
      const data = decode_rgb(packet);
      send_rgb32_back(data, width, height, bitmap_options);
    } else if (
      coding.startsWith("png") ||
      coding === "jpeg" ||
      coding === "webp" ||
      coding === "avif"
    ) {
      const data = packet[7];
      if (!data.buffer) {
        decode_error(`missing pixel data buffer: ${typeof data}`);
        release();
        return;
      }
      let buffer = data;
      if (zerocopy) {
        buffer = data.buffer;
      }
      const blob = new Blob([buffer], {
        type: `image/${coding}`
      });
      hold();
      createImageBitmap(blob, bitmap_options).then(
        function(bitmap) {
          packet[6] = `bitmap:${coding}`;
          packet[7] = bitmap;
          send_back([bitmap]);
          release();
        },
        function(error) {
          console.info(`decode worker failed to create ${coding} image bitmap: ${error}`);
          console.info(`using ${blob} + ${JSON.stringify(bitmap_options)} from data=${data}`);
          console.info(`data from ${buffer.constructor.name} of length ${data.length}`);
          // maybe the regular paint function will succeed?
          console.info("sending it back for decoding directly in the client");
          send_back([]);
          release();
          if (zerocopy) {
            console.warn("turning off zerocopy");
            zerocopy = false;
          }
        }
      );
    } else {
      //pass-through:
      send_back([]);
    }
  } catch (error) {
    decode_error(
      `error processing ${coding} packet ${packet_sequence}: ${error}`
    );
  }
}

function check_image_decode(
  format,
  image_bytes,
  success_callback,
  fail_callback
) {
  if (console) {
    console.info(
      "checking",
      format,
      `with test image: ${image_bytes.length} bytes`
    );
  }
  try {
    const timer = setTimeout(function() {
      fail_callback(format, `timeout, no ${format} picture decoded`);
    }, 2000);
    const data = new Uint8Array(image_bytes);
    const blob = new Blob([data], {
      type: `image/${format}`
    });
    createImageBitmap(blob, {
      premultiplyAlpha: "none",
    }).then(
      function() {
        clearTimeout(timer);
        success_callback(format);
      },
      function(error) {
        clearTimeout(timer);
        fail_callback(format, `${error}`);
      }
    );
  } catch (error) {
    fail_callback(format, `${error}`);
  }
}

onmessage = function(e) {
  const data = e.data;
  switch (data.cmd) {
    case "check": {
      const encodings = data.encodings;
      if (console) {
        console.info("decode worker checking:", encodings);
      }
      const CHECKS = {
        png: [
          137, 80, 78, 71, 13, 10, 26, 10, 0, 0, 0, 13, 73, 72, 68, 82, 0, 0, 0,
          1, 0, 0, 0, 1, 8, 6, 0, 0, 0, 31, 21, 196, 137, 0, 0, 0, 13, 73, 68,
          65, 84, 120, 218, 99, 252, 207, 192, 80, 15, 0, 4, 133, 1, 128, 132,
          169, 140, 33, 0, 0, 0, 0, 73, 69, 78, 68, 174, 66, 96, 130,
        ],
        webp: [
          82, 73, 70, 70, 58, 0, 0, 0, 87, 69, 66, 80, 86, 80, 56, 32, 46, 0, 0,
          0, 178, 2, 0, 157, 1, 42, 2, 0, 2, 0, 46, 105, 52, 154, 77, 34, 34,
          34, 34, 34, 0, 104, 75, 40, 0, 5, 206, 150, 90, 0, 0, 254, 247, 159,
          127, 253, 15, 63, 198, 192, 255, 242, 240, 96, 0, 0,
        ],
        jpeg: [
          255, 216, 255, 224, 0, 16, 74, 70, 73, 70, 0, 1, 1, 1, 0, 96, 0, 96,
          0, 0, 255, 219, 0, 67, 0, 8, 6, 6, 7, 6, 5, 8, 7, 7, 7, 9, 9, 8, 10,
          12, 20, 13, 12, 11, 11, 12, 25, 18, 19, 15, 20, 29, 26, 31, 30, 29,
          26, 28, 28, 32, 36, 46, 39, 32, 34, 44, 35, 28, 28, 40, 55, 41, 44,
          48, 49, 52, 52, 52, 31, 39, 57, 61, 56, 50, 60, 46, 51, 52, 50, 255,
          219, 0, 67, 1, 9, 9, 9, 12, 11, 12, 24, 13, 13, 24, 50, 33, 28, 33,
          50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50,
          50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50,
          50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 50, 255,
          192, 0, 17, 8, 0, 1, 0, 1, 3, 1, 34, 0, 2, 17, 1, 3, 17, 1, 255, 196,
          0, 31, 0, 0, 1, 5, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2, 3,
          4, 5, 6, 7, 8, 9, 10, 11, 255, 196, 0, 181, 16, 0, 2, 1, 3, 3, 2, 4,
          3, 5, 5, 4, 4, 0, 0, 1, 125, 1, 2, 3, 0, 4, 17, 5, 18, 33, 49, 65, 6,
          19, 81, 97, 7, 34, 113, 20, 50, 129, 145, 161, 8, 35, 66, 177, 193,
          21, 82, 209, 240, 36, 51, 98, 114, 130, 9, 10, 22, 23, 24, 25, 26, 37,
          38, 39, 40, 41, 42, 52, 53, 54, 55, 56, 57, 58, 67, 68, 69, 70, 71,
          72, 73, 74, 83, 84, 85, 86, 87, 88, 89, 90, 99, 100, 101, 102, 103,
          104, 105, 106, 115, 116, 117, 118, 119, 120, 121, 122, 131, 132, 133,
          134, 135, 136, 137, 138, 146, 147, 148, 149, 150, 151, 152, 153, 154,
          162, 163, 164, 165, 166, 167, 168, 169, 170, 178, 179, 180, 181, 182,
          183, 184, 185, 186, 194, 195, 196, 197, 198, 199, 200, 201, 202, 210,
          211, 212, 213, 214, 215, 216, 217, 218, 225, 226, 227, 228, 229, 230,
          231, 232, 233, 234, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250,
          255, 196, 0, 31, 1, 0, 3, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 0, 0, 0, 0,
          1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 255, 196, 0, 181, 17, 0, 2, 1, 2,
          4, 4, 3, 4, 7, 5, 4, 4, 0, 1, 2, 119, 0, 1, 2, 3, 17, 4, 5, 33, 49, 6,
          18, 65, 81, 7, 97, 113, 19, 34, 50, 129, 8, 20, 66, 145, 161, 177,
          193, 9, 35, 51, 82, 240, 21, 98, 114, 209, 10, 22, 36, 52, 225, 37,
          241, 23, 24, 25, 26, 38, 39, 40, 41, 42, 53, 54, 55, 56, 57, 58, 67,
          68, 69, 70, 71, 72, 73, 74, 83, 84, 85, 86, 87, 88, 89, 90, 99, 100,
          101, 102, 103, 104, 105, 106, 115, 116, 117, 118, 119, 120, 121, 122,
          130, 131, 132, 133, 134, 135, 136, 137, 138, 146, 147, 148, 149, 150,
          151, 152, 153, 154, 162, 163, 164, 165, 166, 167, 168, 169, 170, 178,
          179, 180, 181, 182, 183, 184, 185, 186, 194, 195, 196, 197, 198, 199,
          200, 201, 202, 210, 211, 212, 213, 214, 215, 216, 217, 218, 226, 227,
          228, 229, 230, 231, 232, 233, 234, 242, 243, 244, 245, 246, 247, 248,
          249, 250, 255, 218, 0, 12, 3, 1, 0, 2, 17, 3, 17, 0, 63, 0, 247, 250,
          40, 162, 128, 63, 255, 217,
        ],
      };
      const errors = [];
      const formats = ["rgb24", "rgb32"];
      const done = (format) => {
        delete CHECKS[format];
        if (Object.keys(CHECKS).length === 0) {
          if (errors.length === 0) {
            self.postMessage({
              result: true,
              formats
            });
          } else {
            self.postMessage({
              result: false,
              errors
            });
          }
        }
      };
      const success = (format) => {
        //only enable this format if the client requested it:
        if (encodings.includes(format)) {
          formats.push(format);
        }
        done(format);
      };
      const failure = (format, message) => {
        //only record an error if the client actually asked us to verify this format
        if (encodings.includes(format)) {
          errors.push(message);
          if (console.warn) {
            console.warn(
              `Warning: decode worker error on '${format}': ${message}`
            );
          }
        } else {
          console.info(`decode worker failure on '${format}': ${message}`);
        }
        done(format);
      };
      for (const format in CHECKS) {
        const image_bytes = CHECKS[format];
        check_image_decode(format, image_bytes, success, failure);
      }
      break;
    }
    case "eos":
      decode_eos(data.wid);
      break;
    case "remove":
      decode_eos(data.wid);
      on_hold.delete(data.wid);
      break;
    case "decode":
      decode_draw_packet(data.packet, data.start);
      break;
    case "close":
      on_hold.clear();
      break;
    default:
      console.error(`decode worker got unknown message: ${data.cmd}`);
  }
};

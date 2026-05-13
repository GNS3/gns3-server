/*
 * This file is part of Xpra.
 * Copyright (C) 2021 Tijs van der Zwaan <tijzwa@vpo.nl>
 * Copyright (c) 2021 Antoine Martin <antoine@xpra.org>
 * Licensed under MPL 2.0, see:
 * http://www.mozilla.org/MPL/2.0/
 *
 */

class XpraImageDecoder {
  async convertToBitmap(packet) {
    const width = packet[4];
    const height = packet[5];
    const coding = packet[6];
    if (coding.startsWith("rgb")) {
      const data = decode_rgb(packet);
      const bitmap = await createImageBitmap(new ImageData(new Uint8ClampedArray(data.buffer), width, height), 0, 0, width, height);
      packet[6] = `bitmap:${coding}`;
      packet[7] = bitmap;
    } else {
      const paint_coding = coding.split("/")[0]; //ie: "png/P" -> "png"
      const options = packet[10];
      const bitmap_options = {
        premultiplyAlpha: "none",
      };
      if ("scaled_size" in options) {
        bitmap_options.resizeWidth = width;
        bitmap_options.resizeHeight = height;
        bitmap_options.resizeQuality = options["scaling-quality"] || "medium";
      }

      const blob = new Blob([packet[7].buffer], {
        type: `image/${paint_coding}`,
      });
      const bitmap = await createImageBitmap(blob, bitmap_options);
      packet[6] = `bitmap:${coding}`;
      packet[7] = bitmap;
    }
    return packet;
  }
}

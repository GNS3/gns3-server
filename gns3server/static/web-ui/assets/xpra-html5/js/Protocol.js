/*
 * Copyright (c) 2013 Antoine Martin <antoine@xpra.org>
 * Copyright (c) 2016 David Brushinski <dbrushinski@spikes.com>
 * Copyright (c) 2014 Joshua Higgins <josh@kxes.net>
 * Copyright (c) 2015 Spikes, Inc.
 * Portions based on websock.js by Joel Martin
 * Copyright (C) 2012 Joel Martin
 *
 * Licensed under MPL 2.0
 *
 * xpra wire protocol with worker support
 *
 * requires:
 *  lz4.js
 *  brotli_decode.js
 */

const CONNECT_TIMEOUT = 15_000;

/*
A stub class to facilitate communication with the protocol when
it is loaded in a worker
*/
class XpraProtocolWorkerHost {
  constructor() {
    this.worker = null;
    this.packet_handler = null;
  }

  open(uri) {
    if (this.worker) {
      //re-use the existing worker:
      this.worker.postMessage({
        c: "o",
        u: uri
      });
      return;
    }
    this.worker = new Worker("js/Protocol.js");
    this.worker.addEventListener(
      "message",
      (e) => {
        const data = e.data;
        switch (data.c) {
          case "r":
            this.worker.postMessage({
              c: "o",
              u: uri
            });
            break;
          case "p":
            if (this.packet_handler) {
              this.packet_handler(data.p);
            }
            break;
          case "l":
            // console.log(data.t);
            break;
          default:
            console.error("got unknown command from worker");
            console.error(e.data);
        }
      },
      false
    );
  }

  close = function() {
    this.worker.postMessage({
      c: "c"
    });
  };

  terminate = function() {
    this.worker.postMessage({
      c: "t"
    });
  };

  send = function(packet) {
    this.worker.postMessage({
      c: "s",
      p: packet
    });
  };

  set_packet_handler = function(callback) {
    this.packet_handler = callback;
  };

  set_cipher_in = function(caps, key) {
    this.worker.postMessage({
      c: "z",
      p: caps,
      k: key
    });
  };

  set_cipher_out = function(caps, key) {
    this.worker.postMessage({
      c: "x",
      p: caps,
      k: key
    });
  };
}


/*
The main Xpra wire protocol
*/
class XpraProtocol {
  constructor() {
    this.verify_connected_timer = 0;
    this.is_worker = false;
    this.packet_handler = null;
    this.websocket = null;
    this.raw_packets = [];
    this.cipher_in_block_size = null;
    this.cipher_in_params = null;
    this.cipher_in_key = null;
    this.cipher_out_params = null;
    this.cipher_out_key = null;
    this.rQ = []; // Receive queue
    this.sQ = []; // Send queue
    this.mQ = []; // Worker message queue
    this.header = [];

    //Queue processing via intervals
    this.process_interval = 0; //milliseconds
  }

  close_event_str(event) {
    const code_mappings = {
      1000: "Normal Closure",
      1001: "Going Away",
      1002: "Protocol Error",
      1003: "Unsupported Data",
      1004: "(For future)",
      1005: "No Status Received",
      1006: "Abnormal Closure",
      1007: "Invalid frame payload data",
      1008: "Policy Violation",
      1009: "Message too big",
      1010: "Missing Extension",
      1011: "Internal Error",
      1012: "Service Restart",
      1013: "Try Again Later",
      1014: "Bad Gateway",
      1015: "TLS Handshake",
    };
    let message = "";
    if (event.code) {
      try {
        message +=
          typeof code_mappings[event.code] !== "undefined" ?
          `'${code_mappings[event.code]}' (${event.code})` :
          `${event.code}`;
        if (event.reason) {
          message += `: '${event.reason}'`;
        }
      } catch (error) {
        this.error("cannot parse websocket event:", error);
        message = "unknown reason";
      }
    } else {
      message = "unknown reason (no websocket error code)";
    }
    return message;
  }

  open(uri) {
    const me = this;
    // (re-)init
    this.raw_packets = [];
    this.rQ = [];
    this.sQ = [];
    this.mQ = [];
    this.header = [];
    this.websocket = null;

    function handle(packet) {
      me.packet_handler(packet);
    }
    this.verify_connected_timer = setTimeout(
      () => handle(["error", "connection timed out", 0]),
      CONNECT_TIMEOUT
    );
    // connect the socket
    try {
      // Request 'binary' subprotocol as required by xpra protocol
      this.websocket = new WebSocket(uri, "binary");
    } catch (error) {
      handle(["error", `${error}`, 0]);
      return;
    }
    this.websocket.binaryType = "arraybuffer";
    this.websocket.addEventListener("open", function() {
      if (me.verify_connected_timer) {
        clearTimeout(me.verify_connected_timer);
        me.verify_connected_timer = 0;
      }
      handle(["open"]);
    });
    this.websocket.addEventListener("close", (event) =>
      handle(["close", me.close_event_str(event)])
    );
    this.websocket.onerror = (event) =>
      handle(["error", me.close_event_str(event), event.code || 0]);
    this.websocket.onmessage = function(e) {
      // push arraybuffer values onto the end
      me.rQ.push(new Uint8Array(e.data));
      setTimeout(function() {
        me.process_receive_queue();
      }, this.process_interval);
    };
  }

  close() {
    if (this.websocket) {
      this.websocket.onopen = null;
      this.websocket.onclose = null;
      this.websocket.onerror = null;
      this.websocket.onmessage = null;
      this.websocket.close();
      this.websocket = null;
    }
  }

  protocol_error(message) {
    this.error("protocol error:", message);
    //make sure we stop processing packets and events:
    this.websocket.onopen = null;
    this.websocket.onclose = null;
    this.websocket.onerror = null;
    this.websocket.onmessage = null;
    this.header = [];
    this.rQ = [];
    //and just tell the client to close (it may still try to re-connect):
    this.packet_handler(["close", message]);
  }

  process_receive_queue() {
    while (this.websocket && this.rQ.length > 0 && this.do_process_receive_queue());
  }

  error() {
    console.error.apply(console, arguments);
  }
  log() {
    // console.log.apply(console, arguments);
  }

  do_process_receive_queue() {
    /*
     * process data from this.rQ until we have enough for one packet chunk
     * then calls this.process_packet_data
     */
    if (this.header.length < 8 && this.rQ.length > 0) {
      //add from receive queue data to header until we get the 8 bytes we need:
      while (this.header.length < 8 && this.rQ.length > 0) {
        const slice = this.rQ[0];
        const needed = 8 - this.header.length;
        const n = Math.min(needed, slice.length);
        this.header.push(...slice.subarray(0, n));
        if (slice.length > needed) {
          //replace the slice with what is left over:
          this.rQ[0] = slice.subarray(n);
        } else {
          //this slice has been fully consumed already:
          this.rQ.shift();
        }
      }

      //verify the header format:
      if (this.header[0] !== 80) {
        let message = `invalid packet header format: ${this.header[0]}`;
        if (this.header.length > 1) {
          let hex = "";
          for (let p of this.header) {
            const v = p.toString(16);
            hex += v.length < 2 ? `0${v}` : v;
          }
          message += `: 0x${hex}`;
        }
        this.protocol_error(message);
        return false;
      }
    }

    if (this.header.length < 8) {
      //we need more data to continue
      return true;
    }

    //ignore 0x8: this flag is unused client-side:
    let proto_flags = this.header[1] & ~0x8;
    const encrypted = proto_flags & 0x2;
    if (encrypted) {
      proto_flags = proto_flags & ~0x2;
    }
    if (proto_flags > 1 && proto_flags !== 0x10) {
      this.protocol_error(`we can't handle this protocol flag yet: ${proto_flags}`);
      return false;
    }

    let packet_size = [4, 5, 6, 7].reduce((accumulator, value) => accumulator * 0x1_00 + this.header[value], 0);

    // add padding if encryption is enabled
    let padding = 0;
    if (encrypted && this.cipher_in_block_size > 0) {
      // PKCS#7 has always at least one byte of padding!
      padding = this.cipher_in_block_size - packet_size % this.cipher_in_block_size;

      packet_size += padding;
    }

    // verify that we have enough data for the full payload:
    let rsize = this.rQ.reduce((accumulator, value) => accumulator + value.length, 0);
    if (rsize < packet_size) {
      return false;
    }

    // done parsing the header, the next packet will need a new one:
    const header = this.header;
    this.header = [];

    let packet_data;
    if (this.rQ[0].length === packet_size) {
      //exact match: the payload is in a buffer already:
      packet_data = this.rQ.shift();
    } else {
      //aggregate all the buffers into "packet_data" until we get exactly "packet_size" bytes:
      packet_data = new Uint8Array(packet_size);
      rsize = 0;
      while (rsize < packet_size) {
        const slice = this.rQ[0];
        const needed = packet_size - rsize;
        if (slice.length > needed) {
          //add part of this slice:
          packet_data.set(slice.subarray(0, needed), rsize);
          rsize += needed;
          this.rQ[0] = slice.subarray(needed);
        } else {
          //add this slice in full:
          packet_data.set(slice, rsize);
          rsize += slice.length;
          this.rQ.shift();
        }
      }
    }

    // decrypt if needed
    if (encrypted) {
      if (!this.cipher_in_key) {
        this.protocol_error("encrypted packet received, but no decryption is configured");
        return false;
      }
      // extract the iv:
      const iv = packet_data.slice(0, 16);
      const encrypted_data = packet_data.subarray(16);
      this.cipher_in_params["iv"] = iv;
      // console.log("decrypt", packet_data.byteLength, "bytes, padding=", padding, JSON.stringify(this.cipher_in_params), packet_data);
      crypto.subtle.decrypt(this.cipher_in_params, this.cipher_in_key, encrypted_data)
        .then(decrypted => {
          // console.log("decrypted", decrypted.byteLength, "bytes, padding=", padding);
          const expected_length = packet_size - padding - iv.length;
          if (!decrypted || decrypted.byteLength < expected_length) {
            this.protocol_error(` expected ${expected_length} bytes, but got ${decrypted.byteLength}`);
            return false;
          }
          if (decrypted.byteLength === packet_size - padding) {
            packet_data = new Uint8Array(decrypted);
          } else {
            packet_data = new Uint8Array(decrypted.slice(0, packet_size - padding));
          }
          // console.log("packet data:", packet_data);
          this.process_packet_data(header, packet_data);
        })
        .catch(err => this.protocol_error("failed to decrypt data: " + err));
      return true;
    }

    this.process_packet_data(header, packet_data);
    return true;
  }

  process_packet_data(header, packet_data) {
    /*
     * the packet data has been decrypted (if needed),
     * decompress it (if needed),
     * then either store it if it is a chunk,
     * or decode the packet if we have received all the chunks (chunk no is 0)
     */
    const level = header[2];
    const index = header[3];
    // console.log("process packet data, header=", header, packet_data.byteLength, "bytes, index=", index, "level=", level);

    //decompress it if needed:
    if (level !== 0) {
      let inflated;
      if (level & 0x10) {
        inflated = lz4.decode(packet_data);
      } else if (level & 0x40) {
        inflated = new Uint8Array(BrotliDecode(packet_data));
      } else {
        throw `unsupported compressor specified: ${level}`;
      }
      packet_data = inflated;
    }

    //save it for later? (partial raw packet)
    if (index > 0) {
      if (index >= 20) {
        this.protocol_error(`invalid packet index: ${index}`);
        return;
      }
      this.raw_packets[index] = packet_data;
      if (this.raw_packets.length >= 4) {
        this.protocol_error(`too many raw packets: ${this.raw_packets.length}`);
      }
      return;
    }

    //decode raw packet data into objects:
    let packet = null;
    try {
      packet = rdecode(packet_data);
      for (const index in this.raw_packets) {
        packet[index] = this.raw_packets[index];
      }
      this.raw_packets = {};
    } catch (error) {
      //FIXME: maybe we should error out and disconnect here?
      this.error("error decoding packet", error);
      this.error(`packet=${packet_data}`);
      const proto_flags = header[1];
      this.error(`protocol flags=${proto_flags}`);
      this.error(` level=${level}`);
      this.error(` index=${index}`);
      this.raw_packets = [];
      return;
    }

    try {
      // call the packet handler
      if (this.is_worker) {
        this.mQ[this.mQ.length] = packet;
        setTimeout(() => this.process_message_queue(), this.process_interval);
      } else {
        this.packet_handler(packet);
      }
    } catch (error) {
      //FIXME: maybe we should error out and disconnect here?
      this.error(`error processing packet ${packet[0]}: ${error}`);
      this.error(` packet data: ${packet_data}`)
    }
  }

  process_send_queue() {
    while (this.sQ.length > 0 && this.websocket) {
      const packet = this.sQ.shift();
      if (!packet) {
        return;
      }
      let bdata = null;
      try {
        bdata = rencode(packet);
      } catch (error) {
        this.error("Error: failed to encode packet:", packet);
        this.error(error);
        continue;
      }
      let payload_size = bdata.length;

      if (this.cipher_out_key) {
        //console("encrypting", packet[0], "packet using", JSON.stringify(this.cipher_out_params), ":", bdata);
        const iv = Utilities.getSecureRandomBytes(16);
        this.cipher_out_params["iv"] = iv;
        crypto.subtle.encrypt(this.cipher_out_params, this.cipher_out_key, bdata)
          .then(encrypted => {
            const enc_u8 = new Uint8Array(encrypted);
            const packet_data = new Uint8Array(iv.byteLength + enc_u8.byteLength);
            packet_data.set(iv, 0);
            packet_data.set(enc_u8, iv.byteLength);
            payload_size += iv.byteLength;
            this.send_packet(packet_data, payload_size, true);
          })
          .catch(err => this.protocol_error("failed to encrypt packet: " + err));
        return;
      }
      this.send_packet(bdata, payload_size, false);
    }
  }

  make_packet_header(proto_flags, level, payload_size) {
    const header = new Uint8Array(8);
    header[0] = "P".charCodeAt(0);
    header[1] = proto_flags;
    header[2] = level;
    header[3] = 0;
    //size header:
    for (let index = 0; index < 4; index++) {
      header[7 - index] = (payload_size >> (8 * index)) & 0xff;
    }
    return header;
  }

  send_packet(bdata, payload_size, encrypted) {
    const level = 0;
    let proto_flags = 0x10;
    if (encrypted) {
      proto_flags |= 0x2;
    }
    const header = this.make_packet_header(proto_flags, level, payload_size);
    const actual_size = bdata.byteLength;
    const packet = new Uint8Array(8 + actual_size);
    packet.set(header, 0);
    packet.set(bdata, 8);
    // put into buffer before send
    if (this.websocket) {
      this.websocket.send(packet.buffer);
    }
  }

  process_message_queue() {
    while (this.mQ.length > 0) {
      const packet = this.mQ.shift();

      if (!packet) {
        return;
      }

      const raw_buffers = [];
      if (packet[0] === "draw" && "buffer" in packet[7]) {
        raw_buffers.push(packet[7].buffer);
      } else if (packet[0] === "sound-data" && Object.hasOwn(packet[2], "buffer")) {
        raw_buffers.push(packet[2].buffer);
      }
      postMessage({
        c: "p",
        p: packet
      }, raw_buffers);
    }
  }

  send(packet) {
    this.sQ[this.sQ.length] = packet;
    setTimeout(() => this.process_send_queue(), this.process_interval);
  }

  set_packet_handler(callback) {
    this.packet_handler = callback;
  }

  set_cipher_in(caps, key) {
    // console.log("configuring cipher in:", caps);
    this.setup_cipher(caps, key, "decrypt", (block_size, params, crypto_key) => {
      // console.log("cipher in configured, params=", JSON.stringify(params));
      this.cipher_in_block_size = block_size;
      this.cipher_in_params = params;
      this.cipher_in_key = crypto_key;
    });
  }

  set_cipher_out(caps, key) {
    // console.log("configuring cipher out:", caps);
    this.setup_cipher(caps, key, "encrypt", (block_size, params, crypto_key) => {
      // console.log("cipher out configured, params=", JSON.stringify(params));
      this.cipher_out_params = params;
      this.cipher_out_key = crypto_key;
    });
  }

  setup_cipher(caps, key, usage, setup_function) {
    if (!key) {
      throw "missing encryption key";
    }

    const cipher = caps["cipher"] || "AES";
    if (cipher !== "AES") {
      throw `unsupported encryption specified: '${cipher}'`;
    }

    const DEFAULT_MODE = "CBC";
    const mode = caps["mode"] || DEFAULT_MODE;
    let block_size = 0;
    if (mode === "CBC") {
      block_size = 16;
    } else if (!["GCM", "CTR"].includes(mode)) {
      throw `unsupported AES mode '${mode}'`;
    }

    const iv = caps["iv"];
    if (!iv) {
      throw "missing IV";
    }

    const salt = Utilities.u8(caps["key_salt"]);
    if (!salt) {
      throw "missing salt";
    }

    const iterations = caps["key_stretch_iterations"];
    if (iterations < 1000 || iterations > 1000000) {
      throw `invalid number of iterations: ${iterations}`;
    }

    const DEFAULT_KEYSIZE = 32;
    const key_size = caps["key_size"] || DEFAULT_KEYSIZE;
    if (![32, 24, 16].includes(key_size)) {
      throw `invalid key size '${key_size}'`;
    }

    const DEFAULT_KEYSTRETCH = "PBKDF2";
    const key_stretch = caps["key_stretch"] || DEFAULT_KEYSTRETCH;
    if (key_stretch.toUpperCase() !== "PBKDF2") {
      throw `invalid key stretching function ${key_stretch}`;
    }

    const DEFAULT_KEY_HASH = "SHA-1";
    let key_hash = (caps["key_hash"] || DEFAULT_KEY_HASH).toUpperCase();
    if (key_hash.startsWith("SHA") && !key_hash.startsWith("SHA-")) {
      key_hash = "SHA-" + key_hash.substring(3);
    }

    const params = {
      name: "AES-" + mode, //ie: "AES-CBC"
      iv: Utilities.u8(iv),
    }

    // console.log("importing", "PBKDF2", "key", "'" + key + "'");
    crypto.subtle.importKey("raw", Utilities.u8(key), {
        name: "PBKDF2"
      }, false, ["deriveKey", "deriveBits"])
      .then(imported_key => {
        // console.log("imported key:", imported_key);
        // console.log("deriving", key_size * 8, "bits", mode, "key with:", iterations, key_hash);
        // console.log("salt=", salt);
        // now stretch it to get the real key:
        crypto.subtle.deriveKey({
            name: "PBKDF2",
            salt: salt,
            iterations: iterations,
            hash: {
              name: key_hash
            },
          }, imported_key, {
            name: "AES-" + mode,
            length: key_size * 8,
          }, false, [usage], )
          .then(crypto_key => {
            // console.log("derived key for", usage, "usage:", crypto_key);
            setup_function(block_size, params, crypto_key);
          })
          .catch(err => {
            this.protocol_error("failed to derive AES key: " + err);
          });
      })
      .catch(err => {
        this.protocol_error("failed to import AES key: " + err);
      });
  }
}

/*
If we are in a web worker, set up an instance of the protocol
*/
if (
  !(
    typeof window == "object" &&
    typeof document == "object" &&
    window.document === document
  )
) {
  // some required imports
  // worker imports are relative to worker script path
  importScripts(
    "lib/lz4.js",
    "lib/brotli_decode.js",
    "lib/rencode.js",
    "Utilities.js"
  );
  // make protocol instance
  const protocol = new XpraProtocol();
  protocol.is_worker = true;
  // we create a custom packet handler which posts packet as a message
  protocol.set_packet_handler((packet) => {
    let raw_buffer = [];
    if (packet[0] === "draw" && Object.hasOwn(packet[7], "buffer")) {
      //zero-copy the draw buffer
      raw_buffer = packet[7].buffer;
      packet[7] = null;
    } else if (
      packet[0] === "send-file-chunk" &&
      Object.hasOwn(packet[3], "buffer")
    ) {
      //zero-copy the file data buffer
      raw_buffer = packet[3].buffer;
      packet[3] = null;
    }
    postMessage({
      c: "p",
      p: packet
    }, raw_buffer);
  }, null);
  // attach listeners from main thread
  self.addEventListener(
    "message",
    (e) => {
      const data = e.data;
      switch (data.c) {
        case "o":
          protocol.open(data.u);
          break;
        case "s":
          protocol.send(data.p);
          break;
        case "x":
          protocol.set_cipher_out(data.p, data.k);
          break;
        case "z":
          protocol.set_cipher_in(data.p, data.k);
          break;
        case "c":
          // close the connection
          protocol.close();
          break;
        case "t":
          // terminate the worker
          self.close();
          break;
        default:
          postMessage({
            c: "l",
            t: "got unknown command from host"
          });
      }
    },
    false
  );
  // tell host we are ready
  postMessage({
    c: "r"
  });
}

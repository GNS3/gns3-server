/*
 * Copyright (c) 2013 Antoine Martin <antoine@xpra.org>
 *
 * Licensed under MPL 2.0
 *
 * xpra wire protocol for WebTransport
 *
 */

/*
The main Xpra wire protocol
*/
class XpraWebTransportProtocol {
  constructor() {
    this.verify_connected_timer = 0;
    this.packet_handler = null;
    this.webtransport = null;
    this.stream = null;
    this.writer = null;
    this.raw_packets = [];
    this.rQ = []; // Receive queue
    this.sQ = []; // Send queue
    this.header = [];

    //Queue processing via intervals
    this.process_interval = 0; //milliseconds
  }

  cancel_connected_timer() {
    if (this.verify_connected_timer) {
      clearTimeout(this.verify_connected_timer);
      this.verify_connected_timer = 0;
    }
  }

  async open(uri) {
    const me = this;
    // (re-)init
    this.raw_packets = [];
    this.rQ = [];
    this.sQ = [];
    this.header = [];
    this.webtransport = null;
    this.stream = null;

    function handle(packet) {
      me.packet_handler(packet);
    }

    this.verify_connected_timer = setTimeout(
      () => handle(["error", "connection timed out", 0]),
      CONNECT_TIMEOUT
    );

    // connect the socket
    try {
      // console.log("opening WebTransport connection to " + uri);
      this.webtransport = new WebTransport(uri);
    } catch (error) {
      handle(["error", `${error}`, 0]);
      return;
    }

    try {
      // console.log("waiting for connection");
      await this.webtransport.ready;
      this.cancel_connected_timer();
    } catch (e) {
      console.error("connection failed: " + e);
      handle(["error", e.toString()]);
      this.cancel_connected_timer();
      return;
    }

    this.webtransport.closed.then(() => {
        handle(["close", "transport closed"])
      })
      .catch((e) => {
        console.error("error closing WebTransport: " + e);
        handle(["close", "error", e.toString()])
      });

    // console.log("creating stream");
    this.stream = await this.webtransport.createBidirectionalStream();
    // console.log("starting read loop with stream=" + this.stream);
    this.read_loop().then(() => {
        // console.log("read loop ended, closing");
        handle(["close", "read loop ended"])
      })
      .catch((e) => {
        console.error("error in read loop: " + e);
        handle(["close", "read loop error", e.toString()])
      });
    this.writer = this.stream.writable.getWriter();
    handle(["open"]);
    // console.log("async open end");
  }

  async read_loop() {
    const reader = this.stream.readable.getReader();
    const me = this;
    while (true) {
      const {
        value,
        done
      } = await reader.read();
      if (done) {
        break;
      }
      this.rQ.push(value);
      setTimeout(() => me.process_receive_queue(), this.process_interval);
    }
  }

  protocol_error(message) {
    this.packet_handler(["error", message]);
    console.error("protocol error: " + message);
    this.close();
  }

  close() {
    this.cancel_connected_timer();
    const wt = this.webtransport;
    if (wt) {
      wt.closed.then(() => {
          // console.log("closed WebTransport connection");
          handle(["close", "WebTransport closed"])
        })
        .catch((e) => {
          // console.log("error closing WebTransport connection: " + e);
          handle(["close", "error closing WebTransport connection", e.toString()])
        });
    }
    this.webtransport = null;
  }

  process_receive_queue() {
    while (this.webtransport && this.do_process_receive_queue());
  }

  do_process_receive_queue() {
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
      return false;
    }

    let proto_flags = this.header[1];
    const proto_crypto = proto_flags & 0x2;
    if (proto_crypto) {
      throw "crypto packets not supported";
    }

    if (proto_flags & 0x8) {
      //this flag is unused client-side, so just ignore it:
      proto_flags = proto_flags & ~0x8;
    }

    if (proto_flags > 1 && proto_flags !== 0x10) {
      this.protocol_error(`we can't handle this protocol flag yet: ${proto_flags}`);
      return;
    }

    const level = this.header[2];
    if (level & 0x20) {
      this.protocol_error("lzo compression is not supported");
      return false;
    }
    const index = this.header[3];
    if (index >= 20) {
      this.protocol_error(`invalid packet index: ${index}`);
      return false;
    }
    let packet_size = [4, 5, 6, 7].reduce(
      (accumulator, value) => accumulator * 0x1_00 + this.header[value],
      0
    );

    // verify that we have enough data for the full payload:
    let rsize = this.rQ.reduce(
      (accumulator, value) => accumulator + value.length,
      0
    );
    if (rsize < packet_size) {
      return false;
    }

    // done parsing the header, the next packet will need a new one:
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

    //decompress it if needed:
    if (level !== 0) {
      let inflated;
      if (level & 0x10) {
        inflated = lz4.decode(packet_data);
      } else if (level & 0x40) {
        inflated = new Uint8Array(BrotliDecode(packet_data));
      } else {
        throw "zlib is no longer supported";
      }
      packet_data = inflated;
    }

    //save it for later? (partial raw packet)
    if (index > 0) {
      this.raw_packets[index] = packet_data;
      if (this.raw_packets.length >= 4) {
        this.protocol_error(`too many raw packets: ${this.raw_packets.length}`);
        return false;
      }
    } else {
      //decode raw packet string into objects:
      let packet = null;
      try {
        if (proto_flags === 0x10) {
          packet = rdecode(packet_data);
        } else if (proto_flags === 0x1) {
          throw `rencode legacy mode is not supported, protocol flag: ${proto_flags}`;
        } else {
          throw `invalid packet encoder flags ${proto_flags}`;
        }
        for (const index in this.raw_packets) {
          packet[index] = this.raw_packets[index];
        }
        this.raw_packets = {};
      } catch (error) {
        //FIXME: maybe we should error out and disconnect here?
        console.error("error decoding packet", error);
        console.error(`packet=${packet_data}`);
        console.error(`protocol flags=${proto_flags}`);
        this.raw_packets = [];
        return this.rQ.length > 0;
      }
      try {
        // pass to our packet handler
        this.packet_handler(packet);
      } catch (error) {
        //FIXME: maybe we should error out and disconnect here?
        console.error(`error processing packet ${packet[0]}: ${error}`);
        console.error(` packet data: ${packet_data}`)
      }
    }
    return this.rQ.length > 0;
  }

  process_send_queue() {
    while (this.sQ.length > 0 && this.webtransport) {
      const packet = this.sQ.shift();
      if (!packet) {
        return;
      }
      let proto_flags = 0x10;
      let bdata = null;
      try {
        bdata = rencode(packet);
      } catch (error) {
        console.error("Error: failed to encode packet:", packet);
        console.error(error);
        continue;
      }
      const payload_size = bdata.length;
      const packet_data = new Uint8Array(payload_size + 8);
      const level = 0;
      //header:
      packet_data[0] = "P".charCodeAt(0);
      packet_data[1] = proto_flags;
      packet_data[2] = level;
      packet_data[3] = 0;
      //size header:
      for (let index = 0; index < 4; index++) {
        packet_data[7 - index] = (payload_size >> (8 * index)) & 0xff;
      }
      packet_data.set(bdata, 8);
      if (this.stream) {
        this.writer.write(new Uint8Array(packet_data).buffer);
      }
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
    throw "not supported with WebTransport";
  }

  set_cipher_out(caps, key) {
    throw "not supported with WebTransport";
  }
}

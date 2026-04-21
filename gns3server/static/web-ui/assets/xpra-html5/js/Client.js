/*
 * Copyright (c) 2013 Antoine Martin <antoine@xpra.org>
 * Copyright (c) 2016 David Brushinski <dbrushinski@spikes.com>
 * Copyright (c) 2014 Joshua Higgins <josh@kxes.net>
 * Copyright (c) 2015 Spikes, Inc.
 * Licensed under MPL 2.0
 *
 * xpra client
 *
 * requires:
 *    Protocol.js
 *    Window.js
 *    Keycodes.js
 */

const WORKER = Boolean(window.Worker);
const CLIPBOARD_IMAGES = true;
const CLIPBOARD_EVENT_DELAY = 100;
const DECODE_WORKER = WORKER && !!window.createImageBitmap;
const SHOW_START_MENU = true;
const FILE_SIZE_LIMIT = 4 * 1024 * 1024 * 1024; //are we even allowed to allocate this much memory?
const FILE_CHUNKS_SIZE = 128 * 1024;
const MAX_CONCURRENT_FILES = 5;
const CHUNK_TIMEOUT = 10 * 1000;
const MODAL_FOCUS = true;

const TEXT_PLAIN = "text/plain";
const UTF8_STRING = "UTF8_STRING";
const TEXT_HTML = "text/html";

const FLOAT_MENU_SELECTOR = "#float_menu";
const PASTEBOARD_SELECTOR = "#pasteboard";
const WINDOW_PREVIEW_SELECTOR = "#window_preview";

const BELL_SOUND = "data:audio/wav;base64,//uQRAAAAWMSLwUIYAAsYkXgoQwAEaYLWfkWgAI0wWs/ItAAAGDgYtAgAyN+QWaAAihwMWm4G8QQRDiMcCBcH3Cc+CDv/7xA4Tvh9Rz/y8QADBwMWgQAZG/ILNAARQ4GLTcDeIIIhxGOBAuD7hOfBB3/94gcJ3w+o5/5eIAIAAAVwWgQAVQ2ORaIQwEMAJiDg95G4nQL7mQVWI6GwRcfsZAcsKkJvxgxEjzFUgfHoSQ9Qq7KNwqHwuB13MA4a1q/DmBrHgPcmjiGoh//EwC5nGPEmS4RcfkVKOhJf+WOgoxJclFz3kgn//dBA+ya1GhurNn8zb//9NNutNuhz31f////9vt///z+IdAEAAAK4LQIAKobHItEIYCGAExBwe8jcToF9zIKrEdDYIuP2MgOWFSE34wYiR5iqQPj0JIeoVdlG4VD4XA67mAcNa1fhzA1jwHuTRxDUQ//iYBczjHiTJcIuPyKlHQkv/LHQUYkuSi57yQT//uggfZNajQ3Vmz+Zt//+mm3Wm3Q576v////+32///5/EOgAAADVghQAAAAA//uQZAUAB1WI0PZugAAAAAoQwAAAEk3nRd2qAAAAACiDgAAAAAAABCqEEQRLCgwpBGMlJkIz8jKhGvj4k6jzRnqasNKIeoh5gI7BJaC1A1AoNBjJgbyApVS4IDlZgDU5WUAxEKDNmmALHzZp0Fkz1FMTmGFl1FMEyodIavcCAUHDWrKAIA4aa2oCgILEBupZgHvAhEBcZ6joQBxS76AgccrFlczBvKLC0QI2cBoCFvfTDAo7eoOQInqDPBtvrDEZBNYN5xwNwxQRfw8ZQ5wQVLvO8OYU+mHvFLlDh05Mdg7BT6YrRPpCBznMB2r//xKJjyyOh+cImr2/4doscwD6neZjuZR4AgAABYAAAABy1xcdQtxYBYYZdifkUDgzzXaXn98Z0oi9ILU5mBjFANmRwlVJ3/6jYDAmxaiDG3/6xjQQCCKkRb/6kg/wW+kSJ5//rLobkLSiKmqP/0ikJuDaSaSf/6JiLYLEYnW/+kXg1WRVJL/9EmQ1YZIsv/6Qzwy5qk7/+tEU0nkls3/zIUMPKNX/6yZLf+kFgAfgGyLFAUwY//uQZAUABcd5UiNPVXAAAApAAAAAE0VZQKw9ISAAACgAAAAAVQIygIElVrFkBS+Jhi+EAuu+lKAkYUEIsmEAEoMeDmCETMvfSHTGkF5RWH7kz/ESHWPAq/kcCRhqBtMdokPdM7vil7RG98A2sc7zO6ZvTdM7pmOUAZTnJW+NXxqmd41dqJ6mLTXxrPpnV8avaIf5SvL7pndPvPpndJR9Kuu8fePvuiuhorgWjp7Mf/PRjxcFCPDkW31srioCExivv9lcwKEaHsf/7ow2Fl1T/9RkXgEhYElAoCLFtMArxwivDJJ+bR1HTKJdlEoTELCIqgEwVGSQ+hIm0NbK8WXcTEI0UPoa2NbG4y2K00JEWbZavJXkYaqo9CRHS55FcZTjKEk3NKoCYUnSQ0rWxrZbFKbKIhOKPZe1cJKzZSaQrIyULHDZmV5K4xySsDRKWOruanGtjLJXFEmwaIbDLX0hIPBUQPVFVkQkDoUNfSoDgQGKPekoxeGzA4DUvnn4bxzcZrtJyipKfPNy5w+9lnXwgqsiyHNeSVpemw4bWb9psYeq//uQZBoABQt4yMVxYAIAAAkQoAAAHvYpL5m6AAgAACXDAAAAD59jblTirQe9upFsmZbpMudy7Lz1X1DYsxOOSWpfPqNX2WqktK0DMvuGwlbNj44TleLPQ+Gsfb+GOWOKJoIrWb3cIMeeON6lz2umTqMXV8Mj30yWPpjoSa9ujK8SyeJP5y5mOW1D6hvLepeveEAEDo0mgCRClOEgANv3B9a6fikgUSu/DmAMATrGx7nng5p5iimPNZsfQLYB2sDLIkzRKZOHGAaUyDcpFBSLG9MCQALgAIgQs2YunOszLSAyQYPVC2YdGGeHD2dTdJk1pAHGAWDjnkcLKFymS3RQZTInzySoBwMG0QueC3gMsCEYxUqlrcxK6k1LQQcsmyYeQPdC2YfuGPASCBkcVMQQqpVJshui1tkXQJQV0OXGAZMXSOEEBRirXbVRQW7ugq7IM7rPWSZyDlM3IuNEkxzCOJ0ny2ThNkyRai1b6ev//3dzNGzNb//4uAvHT5sURcZCFcuKLhOFs8mLAAEAt4UWAAIABAAAAAB4qbHo0tIjVkUU//uQZAwABfSFz3ZqQAAAAAngwAAAE1HjMp2qAAAAACZDgAAAD5UkTE1UgZEUExqYynN1qZvqIOREEFmBcJQkwdxiFtw0qEOkGYfRDifBui9MQg4QAHAqWtAWHoCxu1Yf4VfWLPIM2mHDFsbQEVGwyqQoQcwnfHeIkNt9YnkiaS1oizycqJrx4KOQjahZxWbcZgztj2c49nKmkId44S71j0c8eV9yDK6uPRzx5X18eDvjvQ6yKo9ZSS6l//8elePK/Lf//IInrOF/FvDoADYAGBMGb7FtErm5MXMlmPAJQVgWta7Zx2go+8xJ0UiCb8LHHdftWyLJE0QIAIsI+UbXu67dZMjmgDGCGl1H+vpF4NSDckSIkk7Vd+sxEhBQMRU8j/12UIRhzSaUdQ+rQU5kGeFxm+hb1oh6pWWmv3uvmReDl0UnvtapVaIzo1jZbf/pD6ElLqSX+rUmOQNpJFa/r+sa4e/pBlAABoAAAAA3CUgShLdGIxsY7AUABPRrgCABdDuQ5GC7DqPQCgbbJUAoRSUj+NIEig0YfyWUho1VBBBA//uQZB4ABZx5zfMakeAAAAmwAAAAF5F3P0w9GtAAACfAAAAAwLhMDmAYWMgVEG1U0FIGCBgXBXAtfMH10000EEEEEECUBYln03TTTdNBDZopopYvrTTdNa325mImNg3TTPV9q3pmY0xoO6bv3r00y+IDGid/9aaaZTGMuj9mpu9Mpio1dXrr5HERTZSmqU36A3CumzN/9Robv/Xx4v9ijkSRSNLQhAWumap82WRSBUqXStV/YcS+XVLnSS+WLDroqArFkMEsAS+eWmrUzrO0oEmE40RlMZ5+ODIkAyKAGUwZ3mVKmcamcJnMW26MRPgUw6j+LkhyHGVGYjSUUKNpuJUQoOIAyDvEyG8S5yfK6dhZc0Tx1KI/gviKL6qvvFs1+bWtaz58uUNnryq6kt5RzOCkPWlVqVX2a/EEBUdU1KrXLf40GoiiFXK///qpoiDXrOgqDR38JB0bw7SoL+ZB9o1RCkQjQ2CBYZKd/+VJxZRRZlqSkKiws0WFxUyCwsKiMy7hUVFhIaCrNQsKkTIsLivwKKigsj8XYlwt/WKi2N4d//uQRCSAAjURNIHpMZBGYiaQPSYyAAABLAAAAAAAACWAAAAApUF/Mg+0aohSIRobBAsMlO//Kk4soosy1JSFRYWaLC4qZBYWFRGZdwqKiwkNBVmoWFSJkWFxX4FFRQWR+LsS4W/rFRb/////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////VEFHAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAU291bmRib3kuZGUAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAMjAwNGh0dHA6Ly93d3cuc291bmRib3kuZGUAAAAAAAAAACU=";

const SAFE_ENCODINGS = [
  "jpeg",
  "png",
  "png/P",
  "png/L",
  "rgb",
  "rgb32",
  "rgb24",
  "scroll",
  "void",
];

const METADATA_SUPPORTED = [
  "fullscreen", "maximized",
  "iconic", "above", "below",
  "title", "size-hints",
  "class-instance", "transient-for", "window-type",
  "has-alpha", "decorations", "override-redirect",
  "tray", "modal", "opacity",
]

// This option adds the CSS class .gpu-trigger to the windows.
// The article at https://www.urbaninsight.com/article/improving-html5-app-performance-gpu-accelerated-css-transitions
// states that adding 'transform: transale3d(0,0,0);' is the strongest CSS indication for the browser to enable hardware acceleration.
const TRY_GPU_TRIGGER = true;

function truncate(input) {
  if (!input) {
    return input;
  }
  const s = input.toString();
  if (s.length > 5) {
    return s.slice(0, 5) + "..."; // eslint-disable-line prefer-template
  }
  return s;
}

class XpraClient {
  constructor(container) {
    // the container div is the "screen" on the HTML page where we
    // are able to draw our windows in.
    this.container = document.querySelector(`#${container}`);
    if (!this.container) {
      throw new Error("invalid container element");
    }
    // assign callback for window resize event
    if (window.jQuery) {
      jQuery(window).resize(
        jQuery.debounce(250, (e) => this._screen_resized(e))
      );
    }

    this.protocol = null;

    this.init_settings();
    this.init_state();
  }

  init_settings() {
    //server:
    this.host = null;
    this.port = null;
    this.ssl = null;
    this.webtransport = false;
    this.path = "";
    this.username = "";
    this.passwords = [];
    this.insecure = false;
    this.uri = "";
    this.packet_encoder = null;
    //connection options:
    this.sharing = false;
    this.open_url = true;
    this.steal = true;
    this.remote_logging = true;
    this.debug_categories = [];
    this.start_new_session = null;
    this.clipboard_enabled = false;
    this.clipboard_poll = false;
    this.clipboard_preferred_format = TEXT_PLAIN;
    this.file_transfer = false;
    this.remote_file_size_limit = 0;
    this.remote_file_chunks = 0;
    this.send_chunks_in_progress = new Map();
    this.receive_chunks_in_progress = new Map();
    this.keyboard_layout = null;
    this.printing = false;
    this.key_packets = [];
    this.clipboard_delayed_event_time = 0;

    this.scale = 1;
    this.vrefresh = -1;
    this.bandwidth_limit = 0;
    this.reconnect = true;
    this.reconnect_count = 10;
    this.reconnect_in_progress = false;
    this.reconnect_delay = 2000; //wait 2 seconds before retrying
    this.reconnect_attempt = 0;
    this.swap_keys = Utilities.isMacOS();
    this.HELLO_TIMEOUT = 30_000;
    this.OPEN_TIMEOUT = 10_000;
    this.PING_TIMEOUT = 15_000;
    this.PING_GRACE = 2000;
    this.PING_FREQUENCY = 5000;
    this.INFO_FREQUENCY = 1000;
    this.uuid = Utilities.getHexUUID();
    this.offscreen_api = false;
    this.try_gpu = TRY_GPU_TRIGGER;

    this.init_encodings();
  }

  init_encodings() {
    this.encoding = "auto";
    //basic set of encodings:
    //(more may be added after checking via the DecodeWorker)
    this.supported_encodings = [
      "jpeg",
      "png",
      "png/P",
      "png/L",
      "rgb",
      "rgb32",
      "rgb24",
      "scroll",
      "void",
    ];
    //extra encodings we enable if validated via the decode worker:
    //(we also validate jpeg and png as a sanity check)
    this.check_encodings = [
      "jpeg",
      "png",
      "png/P",
      "png/L",
      "rgb",
      "rgb32",
      "rgb24",
      "scroll",
      "webp",
      "void",
      "avif",
    ];
    // this may be overriden after detecting the offscreen worker:
    const video_max_size = [1024, 768];
    this.encoding_options = {
      "": this.encoding,
      "icons": {
        "max_size": [30, 30],
        "greedy": true,
      },
      "transparency": true,
      "rgb_lz4": (lz4 && lz4.decode != "undefined"),
      "decoder-speed": {
        "video": 0
      },
      "color-gamut": Utilities.getColorGamut(),
      "video_scaling": true,
      "video_max_size": video_max_size,
      "full_csc_modes": {
        "mpeg1": ["YUV420P"],
        "h264": ["YUV420P"],
        "mpeg4+mp4": ["YUV420P"],
        "h264+mp4": ["YUV420P"],
        "vp8+webm": ["YUV420P"],
        "webp": ["BGRX", "BGRA"],
        "jpeg": ["BGRX", "BGRA", "BGR", "RGBX", "RGBA", "RGB", "YUV420P", "YUV422P", "YUV444P"],
        "vp8": ["YUV420P"],
      },
      "h264": {
        "score-delta": 80,
        "YUV420P": {
          "profile": "baseline",
          "level": "2.1",
          "cabac": false,
          "deblocking-filter": false,
          "fast-decode": true,
        },
      },
      "h264+mp4": {
        "score-delta": 50,
        "YUV420P": {
          "profile": "baseline",
          "level": "3.0",
        },
      },
      //prefer unmuxed VPX
      "vp8": {
        "score-delta": 70,
      },
      "mpeg4+mp4": {
        "score-delta": 40,
      },
      "vp8+webm": {
        "score-delta": 40,
      },
    };
  }

  init_state() {
    // state
    this.connected = false;
    this.session_name = undefined;
    this.desktop_width = 0;
    this.desktop_height = 0;
    this.desktop_width = this.container.clientWidth;
    this.desktop_height = this.container.clientHeight;
    this.server_remote_logging = false;
    this.server_start_time = -1;
    this.client_start_time = new Date();
    // some client stuff
    this.capabilities = {};
    this.RGB_FORMATS = ["RGBX", "RGBA", "RGB"];
    this.disconnect_reason = null;
    this.password_prompt_fn = null;
    this.keycloak_prompt_fn = null;
    // audio
    this.audio = null;
    this.audio_enabled = false;
    this.audio_mediasource_enabled = MediaSourceUtil.getMediaSourceClass() != undefined;
    this.audio_aurora_enabled = typeof AV !== "undefined" &&
      AV != undefined &&
      AV.Decoder != undefined &&
      AV.Player.fromXpraSource != undefined;
    this.audio_codecs = {};
    this.audio_framework = null;
    this.audio_aurora_ctx = null;
    this.audio_codec = null;
    this.audio_context = new AudioContext();
    this.audio_state = "";
    this.aurora_codecs = {};
    this.mediasource_codecs = {};
    // encryption
    this.encryption = false;
    this.encryption_key = null;
    this.cipher_in_caps = null;
    this.cipher_out_caps = null;
    // detect locale change:
    this.browser_language = Utilities.getFirstBrowserLanguage();
    this.browser_language_change_embargo_time = 0;
    this.key_layout = null;
    this.last_keycode_pressed = 0;
    this.last_key_packet = [];
    // mouse
    this.buttons_pressed = new Set();
    this.last_button_event = [-1, false, -1, -1];
    this.mousedown_event = null;
    this.mouseup_event = null;
    this.last_mouse_x = null;
    this.last_mouse_y = null;
    this.wheel_delta_x = 0;
    this.wheel_delta_y = 0;
    this.mouse_grabbed = false;
    this.scroll_reverse_x = false;
    this.scroll_reverse_y = "auto";
    // clipboard
    this.clipboard_direction = default_settings["clipboard_direction"] || "both";
    this.clipboard_datatype = null;
    this.clipboard_buffer = "";
    this.clipboard_server_buffers = {};
    this.clipboard_pending = false;
    this.clipboard_targets = [TEXT_HTML, UTF8_STRING, "TEXT", "STRING", TEXT_PLAIN];
    // printing / file-transfer:
    this.remote_printing = false;
    this.remote_file_transfer = false;
    this.remote_open_files = false;
    // hello
    this.hello_timer = null;
    this.open_timer = null;
    this.info_timer = null;
    this.info_request_pending = false;
    this.server_last_info = {};
    // ping
    this.ping_timeout_timer = null;
    this.ping_grace_timer = null;
    this.ping_timer = null;
    this.last_ping_server_time = 0;
    this.last_ping_local_time = 0;
    this.last_ping_echoed_time = 0;
    this.server_ping_latency = 0;
    this.client_ping_latency = 0;
    this.server_load = null;
    this.server_ok = false;
    //packet handling
    this.decode_worker = null;
    this.decode_worker_timeout = 0;
    // floating menu
    this.toolbar_position = "top";

    this.server_display = "";
    this.server_platform = "";
    this.server_resize_exact = false;
    this.server_screen_sizes = [];
    this.server_is_desktop = false;
    this.server_is_shadow = false;
    this.server_readonly = false;

    this.server_connection_data = false;

    this.xdg_menu = null;
    // a list of our windows
    this.id_to_window = {};
    this.ui_events = 0;
    this.pending_redraw = [];
    this.draw_pending = 0;
    // basic window management
    this.focused_wid = 0;

    const me = this;
    const screen_element = jQuery("#screen");
    screen_element.mousedown((e) => this.on_mousedown(e));
    screen_element.mouseup((e) => this.on_mouseup(e));
    document.getElementById("screen").addEventListener("mousemove", (e) => this.on_mousemove(e));

    const div = document.querySelector("#screen");

    function on_mousescroll(e) {
      me.on_mousescroll(e);
      return e.preventDefault();
    }
    if (Utilities.isEventSupported("wheel")) {
      div.addEventListener("wheel", on_mousescroll, false);
    } else {
      this.warn("browser does not support scroll wheel events");
    }
  }

  send() {
    this.debug("network", "sending a", arguments[0], "packet");
    if (this.protocol) {
      this.protocol.send.apply(this.protocol, arguments);
    }
  }

  send_log(level, arguments_) {
    if (this.remote_logging && this.server_remote_logging && this.connected) {
      try {
        const sargs = [];
        for (const argument of arguments_) {
          sargs.push(unescape(encodeURIComponent(String(argument))));
        }
        this.send([PACKET_TYPES.logging, level, sargs]);
      } catch {
        this.cerror("remote logging failed");
        for (const index in arguments_) {
          const argument = arguments_[index];
          this.clog(" argument", index, typeof argument, ":", `'${argument}'`);
        }
      }
    }
  }
  exc() {
    //first argument is the exception:
    const exception = arguments[0];
    let arguments_ = [...arguments];
    arguments_ = arguments_.splice(1);
    if (arguments_.length > 0) {
      this.cerror(arguments_);
    }
    if (exception.stack) {
      try {
        //logging.ERROR = 40
        this.send_log(40, [exception.stack]);
      } catch {
        //we tried our best
      }
    }
  }
  error() {
    //logging.ERROR = 40
    this.send_log(40, arguments);
    Reflect.apply(this.cerror, this, arguments);
  }
  cerror() {
    Utilities.cerror.apply(Utilities, arguments);
  }
  warn() {
    //logging.WARN = 30
    this.send_log(30, arguments);
    Reflect.apply(this.cwarn, this, arguments);
  }
  cwarn() {
    Utilities.cwarn.apply(Utilities, arguments);
  }
  log() {
    //logging.INFO = 20
    this.send_log(20, arguments);
    Reflect.apply(this.clog, this, arguments);
  }
  clog() {
    Utilities.clog.apply(Utilities, arguments);
  }
  debug() {
    const category = arguments[0];
    const arguments_ = [...arguments];
    if (this.debug_categories.includes(category)) {
      if (category !== "network") {
        //logging.DEBUG = 10
        this.send_log(10, arguments_);
      }
      Reflect.apply(this.cdebug, this, arguments);
    }
  }
  cdebug() {
    Utilities.cdebug.apply(Utilities, arguments);
  }

  init(ignore_blacklist) {
    this.on_connection_progress("Initializing", "", 20);
    this.init_audio(ignore_blacklist);
    this.init_packet_handlers();
    this.init_keyboard();
    if (this.scale !== 1) {
      this.container.style.width = `${100 * this.scale}%`;
      this.container.style.height = `${100 * this.scale}%`;
      this.container.style.transform = `scale(${1 / this.scale})`;
      this.container.style.transformOrigin = "top left";
    }
  }

  init_packet_handlers() {
    // the client holds a list of packet handlers
    this.packet_handlers = {
      [PACKET_TYPES.control]: this._process_control,
      [PACKET_TYPES.ack_file_chunk]: this._process_ack_file_chunk,
      [PACKET_TYPES.bell]: this._process_bell,
      [PACKET_TYPES.challenge]: this._process_challenge,
      [PACKET_TYPES.clipboard_request]: this._process_clipboard_request,
      [PACKET_TYPES.clipboard_token]: this._process_clipboard_token,
      [PACKET_TYPES.close]: this._process_close,
      [PACKET_TYPES.configure_override_redirect]: this._process_configure_override_redirect,
      [PACKET_TYPES.cursor]: this._process_cursor,
      [PACKET_TYPES.desktop_size]: this._process_desktop_size,
      [PACKET_TYPES.disconnect]: this._process_disconnect,
      [PACKET_TYPES.draw]: this._process_draw,
      [PACKET_TYPES.encodings]: this._process_encodings,
      [PACKET_TYPES.eos]: this._process_eos,
      [PACKET_TYPES.error]: this._process_error,
      [PACKET_TYPES.hello]: this._process_hello,
      [PACKET_TYPES.info_response]: this._process_info_response,
      [PACKET_TYPES.initiate_moveresize]: this._process_initiate_moveresize,
      [PACKET_TYPES.lost_window]: this._process_lost_window,
      [PACKET_TYPES.new_override_redirect]: this._process_new_override_redirect,
      [PACKET_TYPES.new_tray]: this._process_new_tray,
      [PACKET_TYPES.new_window]: this._process_new_window,
      [PACKET_TYPES.notify_close]: this._process_notify_close,
      [PACKET_TYPES.notify_show]: this._process_notify_show,
      [PACKET_TYPES.open]: this._process_open,
      [PACKET_TYPES.open_url]: this._process_open_url,
      [PACKET_TYPES.ping]: this._process_ping,
      [PACKET_TYPES.ping_echo]: this._process_ping_echo,
      [PACKET_TYPES.pointer_position]: this._process_pointer_position,
      [PACKET_TYPES.raise_window]: this._process_raise_window,
      [PACKET_TYPES.send_file]: this._process_send_file,
      [PACKET_TYPES.send_file_chunk]: this._process_send_file_chunk,
      [PACKET_TYPES.set_clipboard_enabled]: this._process_set_clipboard_enabled,
      [PACKET_TYPES.setting_change]: this._process_setting_change,
      [PACKET_TYPES.sound_data]: this._process_sound_data,
      [PACKET_TYPES.startup_complete]: this._process_startup_complete,
      [PACKET_TYPES.window_icon]: this._process_window_icon,
      [PACKET_TYPES.window_metadata]: this._process_window_metadata,
      [PACKET_TYPES.window_move_resize]: this._process_window_move_resize,
      [PACKET_TYPES.window_resized]: this._process_window_resized,
    };
  }

  on_connection_progress(state, details, progress) {
    //can be overriden
    this.clog(state, details);
  }

  callback_close(reason) {
    if (reason === undefined) {
      reason = "unknown reason";
    }
    this.clog(`connection closed: ${reason}`);
  }

  connect() {
    let details = `${this.host}:${this.port}${this.path}`;
    if (this.ssl) {
      details += " with ssl";
    }
    this.schedule_open_timer();
    this.on_connection_progress("Connecting to server", details, 30);
    // open the web socket, started it in a worker if available
    // check we have enough information for encryption
    if (this.encryption && !this.encryption_key) {
      this.disconnect("no key specified for encryption");
      return;
    }
    this.initialize_workers();
  }

  initialize_workers() {
    // detect webworker support and degrade gracefully
    if (window.Worker) {
      this.clog("we have webworker support");
    }
    else {
      this.clog("no webworker support at all.");
    }

    if (this.webtransport) {
      this.protocol = new XpraWebTransportProtocol();
    } else if (WORKER) {
      this.protocol = new XpraProtocolWorkerHost();
    } else {
      this.protocol = new XpraProtocol();
    }
    this.open_protocol();

    this.decode_worker_timeout = false;
    if (!DECODE_WORKER) {
      this.supported_encodings = SAFE_ENCODINGS;
      this.offscreen_api = false;
      this.decode_worker = null;
      return;
    }

    let decode_worker;
    if (this.offscreen_api) {
      // check that it is actually available:
      this.offscreen_api = DECODE_WORKER && XpraOffscreenWorker.isAvailable(this.ssl);
    }

    if (this.offscreen_api) {
      this.clog("initializing offscreen decode worker");
      decode_worker = new Worker("js/OffscreenDecodeWorker.js");
    } else {
      this.clog("initializing regular decode worker");
      decode_worker = new Worker("js/DecodeWorker.js");
    }
    decode_worker.addEventListener(
      "message",
      (e) => {
        const data = e.data;
        if (data["draw"]) {
          this.do_process_draw(data["draw"], data["start"]);
          return;
        }
        if (data["error"]) {
          const message = data["error"];
          const packet = data["packet"];
          const wid = packet[1];
          const width = packet[2];
          const height = packet[3];
          const coding = packet[6];
          const packet_sequence = packet[8];
          this.clog("decode error on ", coding, "packet sequence", packet_sequence, ":", message);
          if (!this.offscreen_api) {
            this.clog(" pixel data:", packet[7]);
          }
          this.do_send_damage_sequence(packet_sequence, wid, width, height, -1, message);
          return;
        }
        switch (data["result"]) {
          case true: {
            const formats = [...data["formats"]];
            this.clog("we can decode using a worker:", decode_worker);
            if (this.decode_worker_timeout) {
              this.clog("but worker initialization took too long!");
              decode_worker.postMessage({cmd: "close"});
              this.decode_worker = null;
            }
            else {
              if (this.offscreen_api) {
                this.set_encoding_option('video_max_size', [4096, 4096]);
              }
              this.supported_encodings = formats;
              this.clog("full list of supported encodings:", this.supported_encodings);
              this.decode_worker = decode_worker;
            }
            break;
          }
          case false:
            this.clog(`we can't decode using a worker: ${data["errors"]}`);
            this.decode_worker = null;
            break;
          default:
            this.clog("client got unknown message from the decode worker");
            this.decode_worker = null;
        }
      },
      false
    );
    this.clog("decode worker will check:", this.check_encodings);
    decode_worker.postMessage({cmd: "check", encodings: this.check_encodings});
  }

  open_protocol() {
    // set protocol to deliver packets to our packet router
    this.protocol.set_packet_handler((packet) => this._route_packet(packet));
    // make uri
    let uri = "";
    if (this.webtransport) {
      uri = "https";
    } else {
      if (this.ssl) {
        uri = "wss";
      } else {
        uri = "ws";
      }
    }
    uri += "://";
    uri += this.host;
    if (this.port) {
      uri += `:${this.port}`;
    }
    uri += this.path;
    // do open
    this.uri = uri;
    this.on_connection_progress("Opening WebSocket connection", uri, 50);
    this.protocol.open(uri);
    // console.log("open_protocol() done");
  }

  request_refresh(wid) {
    this.send([PACKET_TYPES.buffer_refresh, wid, 0, 100,
      {
        "refresh-now": true,
        batch: {
          reset: true
        },
      },
      {}, //no client_properties
    ]);
  }

  redraw_windows() {
    for (const wid in this.id_to_window) {
      const win = this.id_to_window[wid];
      this.request_redraw(win);
    }
  }

  remove_windows() {
    for (const wid in this.id_to_window) {
      const win = this.id_to_window[wid];
      window.removeWindowListItem(win.wid);
      win.destroy();
    }
    if (this.decode_worker) {
      this.decode_worker.postMessage({cmd: "close"});
      this.decode_worker = null;
    }
  }

  send_close_window(win) {
    this.send([PACKET_TYPES.close_window, win.wid]);
  }

  close_protocol() {
    this.connected = false;
    if (this.protocol) {
      this.protocol.close();
      this.protocol.terminate();
      this.protocol = null;
    }
  }

  clear_timers() {
    this.stop_info_timer();
    this.cancel_hello_timer();
    if (this.ping_timer) {
      clearTimeout(this.ping_timer);
      this.ping_timer = null;
    }
    if (this.ping_timeout_timer) {
      clearTimeout(this.ping_timeout_timer);
      this.ping_timeout_timer = null;
    }
    if (this.ping_grace_timer) {
      clearTimeout(this.ping_grace_timer);
      this.ping_grace_timer = null;
    }
  }

  set_encoding(encoding) {
    // add an encoding to our hello.encodings list
    this.clog("encoding:", encoding);
    this.encoding = encoding;
  }

  set_encoding_option(option, value) {
    this.clog("encoding: ", option, "=", value);
    this.encoding_options[option] = value;
  }

  _route_packet(packet) {
    // ctx refers to `this` because we came through a callback
    const packet_type = Utilities.s(packet[0]);
    this.debug("network", "received a", packet_type, "packet");
    const function_ = this.packet_handlers[packet_type];
    if (function_ === undefined) {
      this.cerror("no packet handler for ", packet_type);
      this.clog(packet);
    } else {
      function_.call(this, packet);
    }
  }

  _screen_resized(event) {
    // send the desktop_size packet so server knows we changed size
    if (!this.connected) {
      return;
    }
    if (this.container.clientWidth === this.desktop_width && this.container.clientHeight === this.desktop_height) {
      // unchanged
      return;
    }
    this.desktop_width = this.container.clientWidth;
    this.desktop_height = this.container.clientHeight;
    const dpi = this._get_DPI();
    const packet = [PACKET_TYPES.configure_display, {
      "desktop-size": [this.desktop_width, this.desktop_height],
      // "desktop-size-unscaled": [this.desktop_width, this.desktop_height],  - we don't do desktop scaling
      "monitors": this._get_monitors(),
      "dpi": {"x": dpi, "y": dpi},
      "vrefresh": this.vrefresh,
    }];
    this.send(packet);
    // call the screen_resized function on all open windows
    for (const index in this.id_to_window) {
      const win = this.id_to_window[index];
      win.screen_resized();

      // Force fullscreen on a a given window name from the provided settings
      if (
        default_settings !== undefined &&
        default_settings.auto_fullscreen !== undefined &&
        default_settings.auto_fullscreen.length > 0
      ) {
        const pattern = new RegExp(`.*${default_settings.auto_fullscreen}.*`);
        if (win.fullscreen === false && pattern.test(win.metadata.title)) {
          clog(`auto fullscreen window: ${win.metadata.title}`);
          win.set_fullscreen(true);
          win.screen_resized();
        }
      }

      // Make a DESKTOP-type window fullscreen automatically.
      // This resizes things like xfdesktop according to the window size.
      if (this.fullscreen === false && this.client.is_window_desktop(win)) {
        clog(`auto fullscreen desktop window: ${this.metadata.title}`);
        this.set_fullscreen(true);
        this.screen_resized();
      }
    }
    // Re-position floating toolbar menu
    this.position_float_menu();
  }

  /**
   * Keyboard
   */
  init_keyboard() {
    this.query_keyboard_map();
  }
  do_init_keyboard() {
    // modifier keys:
    this.num_lock_modifier = null;
    this.alt_modifier = null;
    this.control_modifier = "control";
    this.meta_modifier = null;
    this.altgr_modifier = null;
    this.altgr_state = false;

    this.capture_keyboard = false;
    // assign the key callbacks
    document.addEventListener("keydown", (e) => {
      const preview_element = $(WINDOW_PREVIEW_SELECTOR);
      if (e.code === "Escape" && preview_element.is(":visible")) {
        client.toggle_window_preview();
        return e.stopPropagation() || e.preventDefault();
      }
      if (e.code === "Tab") {
        if (preview_element.is(":visible")) {
          // Select next for previous window.
          const number_slides = $(".window-preview-item-container").length;
          const current_slide = preview_element.slick("slickCurrentSlide");
          let next_index = current_slide;
          next_index = e.shiftKey ?
            (current_slide - 1) % number_slides :
            (current_slide + 1) % number_slides;
          preview_element.slick("goTo", next_index, true);
          return e.stopPropagation() || e.preventDefault();
        } else if (e.altKey) {
          // Alt+Tab shows window preview. and goes to the next window.
          client.toggle_window_preview((e, slick) => {
            const number_slides = slick.slideCount;
            const current_slide = slick.currentSlide;
            const next_index = (current_slide + 1) % number_slides;
            setTimeout(() => {
              slick.goTo(next_index, true);
            }, 10);
          });
          return e.stopPropagation() || e.preventDefault();
        }
      }
      const r = this._keyb_onkeydown(e);
      if (!r) {
        e.preventDefault();
      }
    });
    document.addEventListener("keyup", (e) => {
      if (
        (e.code === "Tab" || e.code.startsWith("Alt")) &&
        $(WINDOW_PREVIEW_SELECTOR).is(":visible")
      ) {
        if (e.code.startsWith("Alt")) {
          client.toggle_window_preview();
        }
        return e.stopPropagation() || e.preventDefault();
      }
      const r = this._keyb_onkeyup(e);
      if (!r) {
        e.preventDefault();
      }
    });
  }

  query_keyboard_map() {
    const keyboard = navigator.keyboard;
    this.keyboard_map = {};
    if (!navigator.keyboard) {
      this.do_init_keyboard();
      return;
    }
    keyboard.getLayoutMap().then((keyboardLayoutMap) => {
      clog("got a keyboard layout map:", keyboardLayoutMap);
      clog("keys:", [...keyboardLayoutMap.keys()]);
      for (const key of keyboardLayoutMap.keys()) {
        const value = keyboardLayoutMap[key];
        cdebug("keyboard", key, "=", value);
        this.keyboard_map[key] = value;
      }
      this.do_init_keyboard();
    },
        (error) => {
          this.cwarn("failed to get keyboard layout:", error);
          this.do_init_keyboard();
        }
    );
    if (keyboard.addEventListener) {
      keyboard.addEventListener("layoutchange", () =>
        this.clog("keyboard layout has changed!")
      );
    }
  }

  send_keymap() {
    const keymap = this._get_keymap_caps();
    const props = {"keymap": keymap};
    this.send([PACKET_TYPES.keymap_changed, props, false]);
  }

  _keyb_get_modifiers(event) {
    /**
     * Returns the modifiers set for the current event.
     * We get the list of modifiers using "get_event_modifiers"
     * then we translate them.
     */
    //convert generic modifiers "meta" and "alt" into their x11 name:
    const modifiers = get_event_modifiers(event);
    return this.translate_modifiers(modifiers);
  }

  translate_modifiers(modifiers) {
    /**
     * We translate "alt" and "meta" into their keymap name.
     * (usually "mod1")
     * And also swap keys for macos clients.
     */
    //convert generic modifiers "meta" and "alt" into their x11 name:
    const alt = this.alt_modifier;
    let control = this.control_modifier;
    let meta = this.meta_modifier;
    const altgr = this.altgr_modifier;
    if (this.swap_keys) {
      meta = this.control_modifier;
      control = this.meta_modifier;
    }

    const new_modifiers = [...modifiers];
    let index = modifiers.indexOf("meta");
    if (index >= 0 && meta) new_modifiers[index] = meta;
    index = modifiers.indexOf("control");
    if (index >= 0 && control) new_modifiers[index] = control;
    index = modifiers.indexOf("alt");
    if (index >= 0 && alt) new_modifiers[index] = alt;
    index = modifiers.indexOf("numlock");
    if (index >= 0) {
      if (this.num_lock_modifier) {
        new_modifiers[index] = this.num_lock_modifier;
      } else {
        new_modifiers.splice(index, 1);
      }
    }
    index = modifiers.indexOf("capslock");
    if (index >= 0) {
      new_modifiers[index] = "lock";
    }

    //add altgr?
    if (this.altgr_state && altgr && !new_modifiers.includes(altgr)) {
      new_modifiers.push(altgr);
      //remove spurious modifiers:
      index = new_modifiers.indexOf(alt);
      if (index >= 0) new_modifiers.splice(index, 1);
      index = new_modifiers.indexOf(control);
      if (index >= 0) new_modifiers.splice(index, 1);
    }
    return new_modifiers;
  }

  _check_browser_language(key_layout) {
    /**
     * This function may send the new detected keyboard layout.
     * (ignoring the keyboard_layout preference)
     */
    const now = performance.now();
    if (now < this.browser_language_change_embargo_time) {
      return;
    }
    let new_layout;
    if (key_layout) {
      new_layout = key_layout;
    } else {
      //we may have used a different layout for a specific key,
      //and now this new key doesn't need it anymore,
      //so we may want to switch back to the original layout:
      const l = Utilities.getFirstBrowserLanguage();
      if (l && this.browser_language !== l) {
        //if the browser language has changed,
        //this takes precedence over the configuration
        this.clog("browser language changed from", this.browser_language, "to", l);
        this.browser_language = l;
        new_layout = Utilities.getKeyboardLayout();
      } else {
        //this will honour the setting supplied by the user on the connect page
        //or default to Utilities.getKeyboardLayout()
        new_layout = this._get_keyboard_layout() || "us";
      }
    }
    if (new_layout && this.key_layout !== new_layout) {
      this.key_layout = new_layout;
      this.clog("keyboard layout changed from", this.key_layout, "to", key_layout);
      this.send_keymap();
      //changing the language too quickly can cause problems server side,
      //wait a bit before checking again:
      this.browser_language_change_embargo_time = now + 1000;
    } else {
      //check again after 100ms minimum
      this.browser_language_change_embargo_time = now + 100;
    }
  }

  _keyb_process(pressed, event) {
    if (this.server_readonly) {
      return true;
    }
    if (!this.capture_keyboard) {
      return true;
    }
    /**
     * Process a key event: key pressed or key released.
     * Figure out the keycode, keyname, modifiers, etc
     * And send the event to the server.
     */

    let keyname = event.code || "";
    const keycode = event.which || event.keyCode;
    if (keycode === 229) {
      //this usually fires when we have received the event via "oninput" already
      return;
    }
    let keystring = event.key || String.fromCharCode(keycode);
    let unpress_now = false;
    this.debug("keyboard", "last keycode pressed=", this.last_keycode_pressed, ", keycode=", keycode,
      ", pressed=", pressed, ", str=", keystring);
    const dead = keystring.toLowerCase() === "dead";
    if (dead && ((this.last_keycode_pressed !== keycode && !pressed) || pressed)) {
      //dead key unpress without first getting a key pressed event,
      //or just a regular pressed dead key, in both cases send a pair:
      pressed = true;
      unpress_now = true;
    }

    this.last_keycode_pressed = pressed ? keycode : 0;

    this.debug("keyboard", "processKeyEvent(", pressed, ", ", event, ") key=", keyname, "keycode=", keycode, "dead=", dead);

    //sync numlock
    if (keycode === 144 && pressed) {
      this.num_lock = !this.num_lock;
    }

    let key_language = null;
    //some special keys are better mapped by name:
    const map_string = this.keyboard_map[keyname];
    if (dead && map_string && map_string in DEAD_KEYS) {
      keyname = DEAD_KEYS[map_string];
      keystring = map_string;
      this.debug("keyboard", "dead key:", keyname);
    } else if (keyname in KEY_TO_NAME) {
      keyname = KEY_TO_NAME[keyname];
    } else if (keyname === "" && keystring in KEY_TO_NAME) {
      keyname = KEY_TO_NAME[keystring];
    }
    //special case for numpad,
    //try to distinguish arrowpad and numpad:
    //(for arrowpad, keyname==str)
    else if (keyname !== keystring && keystring in NUMPAD_TO_NAME) {
      keyname = NUMPAD_TO_NAME[keystring];
      this.num_lock = "0123456789.".includes(keyname);
    }
    //next try mapping the actual character
    else if (keystring in CHAR_TO_NAME) {
      keyname = CHAR_TO_NAME[keystring];
      if (keyname.includes("_")) {
        //ie: Thai_dochada
        const lang = keyname.split("_")[0];
        key_language = KEYSYM_TO_LAYOUT[lang];
      }
    }
    //fallback to keycode map:
    else {
      if (keycode in CHARCODE_TO_NAME) {
        keyname = CHARCODE_TO_NAME[keycode];
      }
      //may override with shifted table:
      if (event.getModifierState && event.getModifierState("Shift") && keycode in CHARCODE_TO_NAME_SHIFTED) {
        keyname = CHARCODE_TO_NAME_SHIFTED[keycode];
      }
    }

    this._check_browser_language(key_language);

    const DOM_KEY_LOCATION_RIGHT = 2;
    if (keyname.match("_L$") && event.location === DOM_KEY_LOCATION_RIGHT)
      keyname = keyname.replace("_L", "_R");

    //AltGr: keep track of pressed state
    if (
      keystring === "AltGraph" ||
      (keyname === "Alt_R" && (Utilities.isWindows() || Utilities.isMacOS())) ||
      (keyname === "Alt_L" && Utilities.isMacOS())
    ) {
      this.altgr_state = pressed;
      keyname = "ISO_Level3_Shift";
      keystring = "AltGraph";
    }

    const raw_modifiers = get_event_modifiers(event);
    const modifiers = this._keyb_get_modifiers(event);
    const keyval = keycode;
    const group = 0;

    const shift = modifiers.includes("shift");
    const capslock = modifiers.includes("capslock");
    if ((capslock && shift) || (!capslock && !shift)) {
      keystring = keystring.toLowerCase();
    }

    const ostr = keystring;
    if (this.swap_keys) {
      if (keyname === "Control_L") {
        keyname = "Meta_L";
        keystring = "meta";
      } else if (keyname === "Meta_L") {
        keyname = "Control_L";
        keystring = "control";
      } else if (keyname === "Control_R") {
        keyname = "Meta_R";
        keystring = "meta";
      } else if (keyname === "Meta_R") {
        keyname = "Control_R";
        keystring = "control";
      }
    }

    //macos will swallow the key release event if the meta modifier is pressed,
    //so simulate one immediately:
    if (pressed && Utilities.isMacOS() && raw_modifiers.includes("meta") && ostr !== "meta") {
      unpress_now = true;
    }

    let allow_default = false;
    if (this.clipboard_enabled && client.clipboard_direction !== "to-server") {
      //allow some key events that need to be seen by the browser
      //for handling the clipboard:
      let clipboard_modifier_keys = ["Control_L", "Control_R", "Shift_L", "Shift_R"];
      let clipboard_modifier = "control";
      if (Utilities.isMacOS()) {
        //Apple does things differently, as usual:
        clipboard_modifier_keys = ["Meta_L", "Meta_R", "Shift_L", "Shift_R"];
        clipboard_modifier = "meta";
      }
      //let the OS see Control (or Meta on macos) and Shift:
      if (clipboard_modifier_keys.includes(keyname)) {
        this.debug("keyboard", "passing clipboard modifier key event to browser:", keyname);
        allow_default = true;
      }
      //let the OS see Shift + Insert:
      if (shift && keyname === "Insert") {
        this.debug("keyboard", "passing clipboard combination Shift+Insert to browser");
        allow_default = true;
      }
      const is_clipboard_modifier_set = raw_modifiers.includes(clipboard_modifier);
      if (is_clipboard_modifier_set) {
        const l = keyname.toLowerCase();
        if (l === "c" || l === "x" || l === "v") {
          this.debug("keyboard", "passing clipboard combination to browser:", clipboard_modifier, "+", keyname);
          allow_default = true;
          if (l === "v") {
            this.clipboard_delayed_event_time = performance.now() + CLIPBOARD_EVENT_DELAY;
          }
        }
      }
    }

    const wid = this.focused_wid;
    this.debug("keyboard", "focused=", this.focused, "keyname=", keyname);
    let packet = [PACKET_TYPES.key_action, wid, keyname, pressed, modifiers, keyval, keystring, keycode, group];
    this.key_packets.push(packet);
    if (unpress_now) {
      packet = [PACKET_TYPES.key_action, wid, keyname, false, modifiers, keyval, keystring, keycode, group];
      this.key_packets.push(packet);
    }

    //if there is a chance that we're in the process of handling
    //a clipboard event (a click or control-v)
    //then we send with a slight delay:
    let delay = 0;
    const now = performance.now();
    if (this.clipboard_delayed_event_time > now) {
      delay = this.clipboard_delayed_event_time - now;
    }
    const me = this;
    setTimeout(() => {
      while (this.key_packets.length > 0) {
        const key_packet = me.key_packets.shift();
        this.last_key_packet = key_packet;
        this.send(key_packet);
      }
    }, delay);
    if (keyname === "F11") {
      this.debug("keyboard", "allowing default handler for", keyname);
      allow_default = true;
    }
    return allow_default;
  }

  _keyb_onkeydown(event) {
    return this._keyb_process(true, event);
  }

  _keyb_onkeyup(event) {
    return this._keyb_process(false, event);
  }

  _get_keyboard_layout() {
    this.debug("keyboard", "_get_keyboard_layout() keyboard_layout=", this.keyboard_layout);
    if (this.keyboard_layout) return this.keyboard_layout;
    return Utilities.getKeyboardLayout();
  }

  _get_keycodes() {
    //keycodes.append((nn(keyval), nn(name), nn(keycode), nn(group), nn(level)))
    const keycodes = [];
    let kc;
    for (const keycode in CHARCODE_TO_NAME) {
      kc = Number.parseInt(keycode);
      keycodes.push([kc, CHARCODE_TO_NAME[keycode], kc, 0, 0]);
    }
    return keycodes;
  }

  _get_desktop_size() {
    return [this.desktop_width, this.desktop_height];
  }

  _get_DPI() {
    const dpi_div = document.querySelector("#dpi");
    if (dpi_div && dpi_div.offsetWidth > 0 && dpi_div.offsetHeight > 0) {
      return Math.round((dpi_div.offsetWidth + dpi_div.offsetHeight) / 2);
    }
    //alternative:
    if ("deviceXDPI" in screen) {
      return (screen.systemXDPI + screen.systemYDPI) / 2;
    }
    //default:
    return 96;
  }

  _get_screen_sizes() {
    const dpi = this._get_DPI();
    const screen_size = [this.container.clientWidth, this.container.clientHeight];
    const wmm = Math.round((screen_size[0] * 25.4) / dpi);
    const hmm = Math.round((screen_size[1] * 25.4) / dpi);
    const monitor = ["Canvas", 0, 0, screen_size[0], screen_size[1], wmm, hmm];
    let name = "HTML";
    if (navigator.userAgentData) {
      const brands = navigator.userAgentData.brands;

      for (let index = 0; index < brands.length; index++) {
        const brand_info = brands[index];
        const brand = brand_info.brand;
        if (brand && !brand.startsWith("Not") && !brand.endsWith("Brand")) {
          name = brand + " " + brand_info.version;
        }
      }
    }
    const screen = [
      name,
      screen_size[0],
      screen_size[1],
      wmm,
      hmm,
      [monitor],
      0,
      0,
      screen_size[0],
      screen_size[1],
    ];
    //just a single screen:
    return [screen];
  }

  _update_capabilities(appendobj) {
    for (const attribute in appendobj) {
      this.capabilities[attribute] = appendobj[attribute];
    }
  }

  /**
   * Ping
   */
  _check_server_echo(ping_sent_time) {
    const last = this.server_ok;
    this.server_ok = this.last_ping_echoed_time >= ping_sent_time;
    if (last !== this.server_ok) {
      if (!this.server_ok) {
        this.clog("server connection is not responding, drawing spinners...");
      } else {
        this.clog("server connection is OK");
      }
      for (const index in this.id_to_window) {
        const win = this.id_to_window[index];
        win.set_spinner(this.server_ok);
      }
    }
  }

  _check_echo_timeout(ping_time) {
    if (this.reconnect_in_progress) {
      return;
    }
    if (this.last_ping_echoed_time > 0 && this.last_ping_echoed_time < ping_time) {
      if (this.reconnect && this.reconnect_attempt < this.reconnect_count) {
        this.warn("ping timeout - reconnecting");
        this.reconnect_attempt++;
        this.do_reconnect();
      } else {
        // no point in telling the server here...
        this.disconnect(`server ping timeout, waited ${this.PING_TIMEOUT}ms without a response`);
      }
    }
  }

  _emit_event(event_type) {
    const event = document.createEvent("Event");
    event.initEvent(event_type, true, true);
    document.dispatchEvent(event);
  }
  emit_connection_lost(event_type) {
    this._emit_event("connection-lost");
  }
  emit_connection_established(event_type) {
    this._emit_event("connection-established");
  }

  /**
   * Hello
   */
  _send_hello(counter) {
    counter = counter || 0;
    this.decode_worker_timeout = counter >= 100;
    if (!DECODE_WORKER || this.decode_worker || this.decode_worker_timeout) {
      // we don't need to wait for the decode worker (ie: disabled),
      // or we have successfully initialized it,
      // or we have already waited too long...
      this.do_send_hello(null, null);
      return;
    }
    if (counter === 0) {
      this.on_connection_progress("Waiting for decode worker", "", 70);
    }
    setTimeout(() => this._send_hello(counter + 1), 100);
  }

  do_send_hello(challenge_response, client_salt) {
    this.on_connection_progress("Sending handshake", "", 90);
    // make the base hello
    this._make_hello_base();
    // handle a challenge if we need to
    if (this.passwords.length > 0 && !challenge_response) {
      // tell the server we expect a challenge (this is a partial hello)
      this.capabilities["challenge"] = true;
      this.clog("sending partial hello");
    } else {
      this.clog("sending hello");
      // finish the hello
      this._make_hello();
    }
    if (challenge_response) {
      this._update_capabilities({
        "challenge_response": challenge_response
      });
      if (client_salt) {
        this._update_capabilities({
          "challenge_client_salt": client_salt
        });
      }
    }
    this.clog("sending hello capabilities", this.capabilities);
    // verify:
    for (const key in this.capabilities) {
      if (key === undefined || key === null) {
        throw new Error("invalid null or undefined key in hello packet data");
      }
      const value = this.capabilities[key];
      if (value === undefined || value === null) {
        throw new Error(`invalid null or undefined value for key ${key} in hello packet data`);
      }
    }
    // send the packet
    this.send([PACKET_TYPES.hello, this.capabilities]);
    this.schedule_hello_timer();
  }

  _make_hello_base() {
    this.capabilities = {};
    this._update_capabilities({
      "version": Utilities.VERSION,
      "client_type": "HTML5",
      "display": this._get_display_caps(),
      "build": this._get_build_caps(),
      "platform": this._get_platform_caps(),
      "session-type": Utilities.getSimpleUserAgentString(),
      "session-type.full": navigator.userAgent,
      "username": this.username,
      "uuid": this.uuid,
      "argv": [window.location.href],
      "share": this.sharing,
      "steal": this.steal,
      "mouse.show": true,
      "vrefresh": this.vrefresh,
      "file-chunks": FILE_CHUNKS_SIZE,
      "setting-change": true, // Required by v5 servers
      "xdg-menu-update": true,
      "xdg-menu": true,
      "control_commands": [
        "log", "redraw", "stop-audio", "toggle-keyboard",
        "toggle-float-menu", "toggle-window-preview",
      ],
    });
    this._update_capabilities(this._get_network_caps());
    if (this.encryption) {
      this.cipher_in_caps = this._get_cipher_caps()
      this._update_capabilities({
        "encryption": this.cipher_in_caps
      });
      console.info("setting cipher in caps=", JSON.stringify(this.cipher_in_caps));
      this.protocol.set_cipher_in(this.cipher_in_caps, this.encryption_key);
    }
    if (this.start_new_session) {
      this._update_capabilities({
        "start-new-session": this.start_new_session,
      });
    }
  }

  _make_hello() {
    this.desktop_width = this.container.clientWidth;
    this.desktop_height = this.container.clientHeight;
    this.key_layout = this._get_keyboard_layout();

    this._update_capabilities({
      auto_refresh_delay: 500,
      "metadata.supported": METADATA_SUPPORTED,
      "encodings": {
        "": this.supported_encodings,
        "core": this.supported_encodings,
        "rgb_formats": this.RGB_FORMATS,
        "window-icon": ["png"],
        "cursor": ["png"],
        "packet": true,
      },
      "encoding": this._get_encoding_caps(),
      "audio": this._get_audio_caps(),
      "clipboard": this._get_clipboard_caps(),
      "pointer": this._get_pointer_caps(),
      "keymap": this._get_keymap_caps(),
      "file": this._get_file_caps(),
      "wants": ["audio", ],
      // encoding stuff
      windows: true,
      "window.pre-map": true,
      //partial support:
      keyboard: true,
      screen_sizes: this._get_screen_sizes(),
      dpi: {
        "x": this._get_DPI(),
        "y": this._get_DPI(),
      },
      notifications: {
        "enabled": true,
      },
      cursors: true,
      bell: true,
      system_tray: true,
      //we cannot handle this (GTK only):
      named_cursors: false,
    });
  }

  _get_display_caps() {
    return {
      "refresh-rate": this.vrefresh,
      "desktop_size": [this.desktop_width, this.desktop_height],
      "desktop_mode_size": [this.desktop_width, this.desktop_height],
      "screen_sizes": this._get_screen_sizes(),
      "monitors": this._get_monitors(),
    }
  }

  _get_monitors() {
    const monitors = new Map();
    monitors.set(0, this._get_monitor());
    return monitors;
  }

  _get_monitor() {
      const dpi = this._get_DPI();
      const wmm = Math.round((this.desktop_width * 25.4) / dpi);
      const hmm = Math.round((this.desktop_height * 25.4) / dpi);
      return {
        "geometry": [0, 0, this.desktop_width, this.desktop_height],
        "primary": true,
        "refresh-rate": this.vrefresh,
        // "scale-factor": 1,
        "width-mm": wmm,
        "height-mm": hmm,
        "manufacturer": Utilities.getOS(),
        "model": Utilities.getBrowserName(),
        // "subpixel-layout": "BGR", - not available in browsers
        "workarea": [0, 0, this.desktop_width, this.desktop_height],
        "name": "Canvas",
      }
  }

  _get_file_caps() {
    return {
      "enabled": true,
      "printing": this.printing,
      "open-url": this.open_url,
      "size-limit": 32 * 1024 * 1024,
    }
  }

  _get_network_caps() {
    const digests = this._get_digests();
    return {
      "digest": digests,
      "salt-digest": digests,
      "compression_level": 1,
      "rencodeplus": true,
      "brotli": (typeof BrotliDecode === "function"),
      "lz4": Boolean(lz4 && lz4.decode),
      "bandwidth-limit": this.bandwidth_limit,
      "connection-data": Utilities.getConnectionInfo(),
      "network": {
        "pings": 5,
      }
    }
  }

  _get_digests() {
    const digests = ["xor", "keycloak", "hmac+sha256"];

    if (typeof crypto.subtle !== "undefined") {
      try {
        this.debug("network", "crypto.subtle=", crypto.subtle);
        for (const hash of ["sha1", "sha256", "sha384", "sha512"]) {
          digests.push("hmac+" + hash);
        }
        this.debug("network", "digests:", digests);
      } catch {
        this.cerror("Error probing crypto.subtle digests");
      }
    } else {
      this.clog("cryptography library 'crypto.subtle' not found");
    }
    return digests;
  }

  _get_cipher_caps() {
    const enc = this.encryption.split("-")[0];
    if (enc !== "AES") {
      throw `invalid encryption specified: '${enc}'`;
    }
    const mode = this.encryption.split("-")[1] || "CBC";
    return {
      "cipher": enc,
      "mode": mode,
      "iv": Utilities.getSecureRandomString(16),
      "key_salt": Utilities.getSecureRandomBytes(64),
      "key_size": 32, //256 bits
      "key_hash": "SHA1",
      "key_stretch_iterations": 1000,
      "padding.options": ["PKCS#7"],
      "always-pad": true,
      "stream": false,
    }
  }


  _get_build_caps() {
    return {
      "revision": Utilities.REVISION,
      "local_modifications": Utilities.LOCAL_MODIFICATIONS,
      "branch": Utilities.BRANCH,
    }
  }

  _get_platform_caps() {
    return {
      "": Utilities.getPlatformName(),
      "name": Utilities.getPlatformName(),
      "processor": Utilities.getPlatformProcessor(),
      "platform": navigator.appVersion,
    }
  }

  _get_audio_caps() {
    return {
      "receive": true,
      "send": true,
      "decoders": Object.keys(this.audio_codecs),
    }
  }

  _get_keymap_caps() {
    return {
      "layout": this.key_layout,
      "keycodes": this._get_keycodes(),
    }
  }

  _get_pointer_caps() {
    return {
      "double_click": {},
    }
  }

  _get_clipboard_caps() {
    let selections;
    if (navigator.clipboard && navigator.clipboard.readText && navigator.clipboard.writeText) {
      //we don't need the primary contents,
      //we can use the async clipboard
      selections = ["CLIPBOARD"];
      this.log("using new navigator.clipboard");
    } else {
      selections = ["CLIPBOARD", "PRIMARY"];
      this.log("legacy clipboard");
    }
    this.log("clipboard polling: ", this.clipboard_poll);

    this.clipboard_targets = [this.clipboard_preferred_format];
    for (const target of [TEXT_HTML, UTF8_STRING, "TEXT", "STRING", TEXT_PLAIN]) {
      if (target !== this.clipboard_preferred_format) {
        this.clipboard_targets.push(target);
      }
    }
    if (CLIPBOARD_IMAGES && navigator.clipboard && Object.hasOwn(navigator.clipboard, "write")) {
      this.clipboard_targets.push("image/png");
    } else {
      this.log("no clipboard write support: no images, navigator.clipboard=", navigator.clipboard);
    }
    this.log("clipboard targets: ", this.clipboard_targets);
    this.log("clipboard preferred format: ", this.clipboard_preferred_format);

    return {
      "enabled": this.clipboard_enabled,
      "want_targets": true,
      "greedy": true,
      "selections": selections,
      "preferred-targets": this.clipboard_targets,
    }
  }

  _get_encoding_caps() {
    return this.encoding_options;
  }

  on_first_ui_event() {
    //this hook can be overriden
  }

  _new_ui_event() {
    if (this.ui_events === 0) {
      this.on_first_ui_event();
    }
    this.ui_events++;
  }

  /**
   * Mouse handlers
   */
  getMouse(e) {
    const windowIsLocked = Boolean(document.pointerLockElement);

    // get mouse position take into account scroll
    let mx = e.clientX + jQuery(document).scrollLeft();
    let my = e.clientY + jQuery(document).scrollTop();

    if (windowIsLocked) {
      mx = e.movementX;
      my = e.movementY;
    }

    if (this.scale !== 1) {
      mx = Math.round(mx * this.scale);
      my = Math.round(my * this.scale);
    }

    // check last mouse position incase the event
    // hasn't provided it - bug #854
    if (isNaN(mx) || isNaN(my)) {
      if (!isNaN(this.last_mouse_x) && !isNaN(this.last_mouse_y)) {
        mx = this.last_mouse_x;
        my = this.last_mouse_y;
      } else {
        // should we avoid sending NaN to the server?
        mx = 0;
        my = 0;
      }
    } else {
      if (windowIsLocked) {
        this.last_mouse_x += mx;
        this.last_mouse_y += my;
      }
      this.last_mouse_x = mx;
      this.last_mouse_y = my;
    }

    let mbutton = 0;
    if ("which" in e)
      // Gecko (Firefox), WebKit (Safari/Chrome) & Opera
      mbutton = Math.max(0, e.which);
    else if ("button" in e)
      // IE, Opera (zero based)
      mbutton = Math.max(0, e.button) + 1;

    mx = this.last_mouse_x;
    my = this.last_mouse_y;

    // We return a simple javascript object (a hash) with x and y defined
    return {
      x: mx,
      y: my,
      button: mbutton
    };
  }

  on_mousedown(e, win) {
    this.mousedown_event = e;
    this.mouseup_event = null;
    this.do_window_mouse_click(e, win, true);
    return !win;
  }

  on_mouseup(e, win) {
    this.mouseup_event = e;
    this.do_window_mouse_click(e, win, false);
    return !win;
  }

  on_mousemove(e, win) {
    if (this.mouse_grabbed) {
      return true;
    }

    // Ignore events when server is readonly, disconnected or if the event is not over the screen while in shadow mode
    if (this.server_readonly || !this.connected || (!win && this.server_is_shadow)) {
      return !win;
    }
    const mouse = this.getMouse(e);
    const x = Math.round(mouse.x);
    const y = Math.round(mouse.y);
    const modifiers = this._keyb_get_modifiers(e);
    const buttons = [];
    const coords = [x, y];
    let wid = 0;
    if (this.server_is_desktop) {
      wid = 1;
    }
    if (win) {
      wid = win.wid;
      // add relative coordinates:
      const pos = win.get_internal_geometry();
      coords.push(Math.round(mouse.x - pos.x));
      coords.push(Math.round(mouse.y - pos.y));
      e.preventDefault();
    }
    this.send([PACKET_TYPES.pointer_position, wid, coords, modifiers, buttons]);
    return !win;
  }

  release_buttons(e, win) {
    const mouse = this.getMouse(e);
    const x = Math.round(mouse.x);
    const y = Math.round(mouse.y);
    const modifiers = this._keyb_get_modifiers(e);
    const pressed = false;
    const coords = [x, y];
    let wid = 0;
    if (win) {
      wid = win.wid;
      // add relative coordinates:
      const pos = win.get_internal_geometry();
      coords.push(Math.round(mouse.x - pos.x));
      coords.push(Math.round(mouse.y - pos.y));
    }
    for (const button of this.buttons_pressed) {
      this.send_button_action(wid, button, pressed, coords, modifiers);
    }
  }

  do_window_mouse_click(e, win, pressed) {
    if (win) {
      e.preventDefault();
    }

    // Ignore events when server is readonly, disconnected or if the event is not over the screen while in shadow mode
    if (this.server_readonly || this.mouse_grabbed || !this.connected || (!win && this.server_is_shadow)) {
      return;
    }
    // Skip processing if clicked on float menu
    if (
      $(e.target).attr("id") === FLOAT_MENU_SELECTOR.slice(1) ||
      $(e.target).parents(FLOAT_MENU_SELECTOR).length > 0
    ) {
      this.debug("clicked on float_menu, skipping event handler", e);
      return;
    }
    let send_delay = 0;
    const client = this;
    if (client.clipboard_direction !== "to-server" && this._poll_clipboard(e)) {
      send_delay = CLIPBOARD_EVENT_DELAY;
    }
    const mouse = this.getMouse(e, win);
    const x = Math.round(mouse.x);
    const y = Math.round(mouse.y);
    const modifiers = this._keyb_get_modifiers(e);
    const coords = [x, y];
    let wid = 0;
    if (win) {
      wid = win.wid;
      // add relative coordinates:
      const pos = win.get_internal_geometry();
      coords.push(Math.round(mouse.x - pos.x));
      coords.push(Math.round(mouse.y - pos.y));
    }
    // dont call set focus unless the focus has actually changed
    if (wid > 0 && this.focused_wid !== wid) {
      this.set_focus(win);
    }

    if (window.cursor_lock && win.canvas) {
      $("#cursor-lock-button").removeClass("icon-paused");
      win.canvas.requestPointerLock();
    }

    let button = mouse.button;
    const lbe = this.last_button_event;
    if (lbe[0] === button && lbe[1] === pressed && lbe[2] === x && lbe[3] === y) {
      //duplicate!
      this.debug("mouse", "skipping duplicate click event");
      return;
    }
    this.last_button_event = [button, pressed, x, y];
    this.debug("mouse", "click:", button, pressed, x, y);
    if (button === 4) {
      button = 8;
    } else if (button === 5) {
      button = 9;
    }
    function send_button_action() {
      client.clipboard_delayed_event_time = performance.now() + CLIPBOARD_EVENT_DELAY;
      client.send_button_action(wid, button, pressed, coords, modifiers);
    }
    if (send_delay) {
      setTimeout(send_button_action, send_delay)
    }
    else {
      send_button_action();
    }
  }

  send_button_action(wid, button, pressed, coords, modifiers) {
    const buttons = [];
    if (pressed) {
      this.buttons_pressed.add(button);
    } else {
      this.buttons_pressed.delete(button);
    }
    this.send([PACKET_TYPES.button_action, wid, button, pressed, coords, modifiers, buttons]);
  }

  // Source: https://deepmikoto.com/coding/1--javascript-detect-mouse-wheel-direction
  detect_vertical_scroll_direction(e) {
    if (!e) {
      //IE? In any case, detection won't work:
      return 0;
    }
    let delta = 0;
    if (e.wheelDelta) {
      // will work in most cases
      delta = e.wheelDelta;
    } else if (e.detail) {
      // fallback for Firefox
      delta = -e.detail;
    }
    if (!delta) {
      return 0;
    }
    if (delta > 0) {
      return -1;
    }
    if (delta < 0) {
      return 1;
    }
    return 0;
  }

  on_mousescroll(e, win) {
    // Ignore events when server is readonly, disconnected or if the event is not over the screen while in shadow mode
    if (this.server_readonly || this.mouse_grabbed || !this.connected || (!win && this.server_is_shadow)) {
      return false;
    }
    const mouse = this.getMouse(e);
    const x = Math.round(mouse.x);
    const y = Math.round(mouse.y);
    const modifiers = this._keyb_get_modifiers(e);
    const buttons = [];
    let wid = 0;
    const coords = [x, y];
    if (win) {
      wid = win.wid;
      // add relative coordinates:
      const pos = win.get_internal_geometry();
      coords.push(Math.round(mouse.x - pos.x));
      coords.push(Math.round(mouse.y - pos.y));
    }
    const wheel = Utilities.normalizeWheel(e);
    this.debug("mouse", "normalized wheel event:", wheel);
    //clamp to prevent event floods:
    let px = Math.min(1200, wheel.pixelX);
    let py = Math.min(1200, wheel.pixelY);
    if (this.scroll_reverse_x) {
      px = -px;
    }
    if (this.scroll_reverse_y == true || (this.scroll_reverse_x == "auto" && this.detect_vertical_scroll_direction(e) < 0 && py > 0)) {
      py = -py;
    }
    const apx = Math.abs(px);
    const apy = Math.abs(py);
    if (this.server_precise_wheel) {
      if (apx > 0) {
        const button_x = px >= 0 ? 7 : 6;
        const xdist = Math.round((px * 1000) / 120);
        this.send([PACKET_TYPES.wheel_motion, wid, button_x, -xdist, coords, modifiers, buttons]);
      }
      if (apy > 0) {
        const button_y = py >= 0 ? 5 : 4;
        const ydist = Math.round((py * 1000) / 120);
        this.send([PACKET_TYPES.wheel_motion, wid, button_y, -ydist, coords, modifiers, buttons]);
      }
      return;
    }
    //generate a single event if we can, or add to accumulators:
    if (apx >= 40 && apx <= 160) {
      this.wheel_delta_x = px > 0 ? 120 : -120;
    } else {
      this.wheel_delta_x += px;
    }
    if (apy >= 40 && apy <= 160) {
      this.wheel_delta_y = py > 0 ? 120 : -120;
    } else {
      this.wheel_delta_y += py;
    }
    //send synthetic click+release as many times as needed:
    let wx = Math.abs(this.wheel_delta_x);
    let wy = Math.abs(this.wheel_delta_y);
    const button_x = this.wheel_delta_x >= 0 ? 7 : 6;
    const button_y = this.wheel_delta_y >= 0 ? 5 : 4;
    while (wx >= 120) {
      wx -= 120;
      this.send([PACKET_TYPES.button_action, wid, button_x, true, coords, modifiers, buttons]);
      this.send([PACKET_TYPES.button_action, wid, button_x, false, coords, modifiers, buttons]);
    }
    while (wy >= 120) {
      wy -= 120;
      this.send([PACKET_TYPES.button_action, wid, button_y, true, coords, modifiers, buttons]);
      this.send([PACKET_TYPES.button_action, wid, button_y, false, coords, modifiers, buttons]);
    }
    //store left overs:
    this.wheel_delta_x = this.wheel_delta_x >= 0 ? wx : -wx;
    this.wheel_delta_y = this.wheel_delta_y >= 0 ? wy : -wy;
    e.preventDefault();
    return false;
  }

  init_clipboard() {
    this.clog("initializing clipboard: enabled=", this.clipboard_enabled,
      ", poll=", this.clipboard_poll, ", preferred format=", this.clipboard_preferred_format);
    if (!this.clipboard_enabled) {
      return;
    }
    window.addEventListener("paste", (e) => {
      let clipboardData = (e.originalEvent || e).clipboardData;
      if (clipboardData && clipboardData.files && clipboardData.files.length > 0) {
        const files = clipboardData.files;
        this.clog("paste got", files.length, "files");
        for (let index = 0; index < files.length; index++) {
          const file = files.item(index);
          this.send_file(file);
        }
        e.preventDefault();
        return;
      }
      const fmt = this.clipboard_preferred_format;
      if ((fmt === TEXT_PLAIN || fmt === UTF8_STRING) && navigator.clipboard && navigator.clipboard.readText) {
        navigator.clipboard.readText().then(
          (text) => {
            this.cdebug("clipboard", "paste event, text=", text);
            this.clipboard_buffer = text;
            const data = Utilities.StringToUint8(text);
            this.send_clipboard_token(data);
          },
          (error) => this.cdebug("clipboard", "paste event failed:", error)
        );
        return;
      }
      let clipboard_buffer = clipboardData.getData(fmt);
      if (clipboard_buffer) {
        this.cdebug("clipboard", "paste event, ", fmt, "=", clipboard_buffer);
        this.clipboard_buffer = clipboard_buffer;
        const data = Utilities.StringToUint8(clipboard_buffer);
        this.send_clipboard_token(data, [fmt]);
      }
    });
    window.addEventListener("copy", (e) => {
      const clipboard_buffer = this.get_clipboard_buffer();
      const pasteboard = $(PASTEBOARD_SELECTOR);
      pasteboard.text(clipboard_buffer);
      pasteboard.select();
      this.cdebug("clipboard", "copy event, clipboard buffer=", clipboard_buffer);
      this.clipboard_pending = false;
    });
    window.addEventListener("cut", (e) => {
      const clipboard_buffer = this.get_clipboard_buffer();
      const pasteboard = $(PASTEBOARD_SELECTOR);
      pasteboard.text(clipboard_buffer);
      pasteboard.select();
      this.cdebug("clipboard", "cut event, clipboard buffer=", clipboard_buffer);
      this.clipboard_pending = false;
    });
    const screen = $("#screen");
    screen.on("click", (e) => this.may_set_clipboard());
    screen.keypress(() => this.may_set_clipboard());
  }

  may_set_clipboard(e) {
    this.cdebug("clipboard", "pending=", this.clipboard_pending, "buffer=", truncate(this.clipboard_buffer));
    if (!this.clipboard_pending) {
      return;
    }
    let clipboard_buffer = this.get_clipboard_buffer();
    const clipboard_datatype = (this.get_clipboard_datatype() || "").toLowerCase();
    const is_text = clipboard_datatype.includes("text") || clipboard_datatype.includes("string");
    if (!is_text) {
      //maybe just abort here instead?
      clipboard_buffer = "";
    }
    const pasteboard = $(PASTEBOARD_SELECTOR);
    pasteboard.text(clipboard_buffer);
    pasteboard.select();
    this.cdebug("clipboard", "click event, with pending clipboard datatype=", clipboard_datatype, ", buffer=",
      clipboard_buffer
    );
    let success = false;
    if (
      Object.hasOwn(window, "clipboardData") &&
      Object.hasOwn(window.clipboardData, "setData") &&
      typeof window.clipboardData.setData === "function"
    ) {
      try {
        window.clipboardData.setData(clipboard_datatype, clipboard_buffer);
        success = true;
      } catch {
        success = false;
      }
    }
    if (!success && is_text) {
      success = document.execCommand("copy");
    } else {
      //probably no point in trying again?
    }
    if (success) {
      //clipboard_buffer may have been cleared if not set to text:
      this.clipboard_buffer = clipboard_buffer;
      this.clipboard_pending = false;
    }
  }

  _poll_clipboard(e) {
    if (!this.clipboard_poll) {
      return;
    }
    //see if the clipboard contents have changed:
    if (this.clipboard_pending) {
      //we're still waiting to set the clipboard..
      return false;
    }
    this.read_clipboard(e);
  }

  read_clipboard(e) {
    if (this.clipboard_enabled === false) {
      return;
    }
    if (navigator.clipboard && navigator.clipboard.clipboardData) {
      this.debug("clipboard", "polling using", navigator.clipboard.clipboardData);
      this.read_clipboard_data();
      return false;
    }
    if (navigator.clipboard && navigator.clipboard.readText) {
      this.debug("clipboard", "polling using", navigator.clipboard.readText);
      this.read_clipboard_text();
      return false;
    }
    //fallback code for legacy mode:
    let datatype = TEXT_PLAIN;
    let clipboardData = (e.originalEvent || e).clipboardData;
    if (!clipboardData) {
      this.debug("clipboard", "polling: no data available");
      return false;
    }
    const raw_clipboard_buffer = clipboardData.getData(datatype);
    if (raw_clipboard_buffer === null) {
      return false;
    }
    const clipboard_buffer = unescape(encodeURIComponent(raw_clipboard_buffer));
    this.debug("clipboard", "paste event, data=", clipboard_buffer);
    if (clipboard_buffer === this.clipboard_buffer) {
      return false;
    }
    this.debug("clipboard", "clipboard contents have changed");
    this.clipboard_buffer = clipboard_buffer;
    this.send_clipboard_token(clipboard_buffer, [datatype]);
    this.clipboard_delayed_event_time = performance.now() + CLIPBOARD_EVENT_DELAY;
    return true;
  }

  read_clipboard_data() {
    if (this.clipboard_enabled === false) {
      return;
    }
    navigator.clipboard.clipboardData.read(TEXT_HTML).then(
      (text) => {
        this.debug("clipboard", "paste event, text/html=", text);
        if (!text) {
          // try with plain text:
          read_clipboard_text();
          return;
        }
        const clipboard_buffer = text;
        if (clipboard_buffer !== this.clipboard_buffer) {
          this.debug("clipboard", "clipboard contents have changed");
          this.clipboard_buffer = clipboard_buffer;
          this.send_clipboard_token(clipboard_buffer, [TEXT_HTML]);
          this.clipboard_delayed_event_time = performance.now() + CLIPBOARD_EVENT_DELAY;
        }
        this.clipboard_pending = false;
      },
      (error) => {
        this.debug("clipboard", "paste event failed:", error);
        this.clipboard_pending = false;
      }
    );
  }

  read_clipboard_text() {
    if (this.clipboard_enabled === false) {
      return;
    }
    client.debug("clipboard", "read_clipboard_text()");
    //warning: this can take a while,
    //so we may send the click before the clipboard contents...
    navigator.clipboard.readText().then(
      (text) => {
        this.debug("clipboard", "paste event, text=", text);
        const clipboard_buffer = unescape(encodeURIComponent(text));
        if (clipboard_buffer !== this.clipboard_buffer) {
          this.debug("clipboard", "clipboard contents have changed");
          this.clipboard_buffer = clipboard_buffer;
          this.send_clipboard_token(clipboard_buffer);
          this.clipboard_delayed_event_time = performance.now() + CLIPBOARD_EVENT_DELAY;
        }
        this.clipboard_pending = false;
      },
      (error) => {
        this.debug("clipboard", "paste event failed:", error);
        this.clipboard_pending = false;
      }
    );
  }

  /**
   * Focus
   */
  set_focus(win) {
    if (!win || this.server_readonly || !this.connected) {
      return;
    }
    // don't send focus packet for override_redirect windows!
    if (win.override_redirect || win.tray) {
      return;
    }
    if (win.minimized) {
      //tell server to map it:
      win.toggle_minimized();
    }

    // keep modal windows on top:
    let modal = false;
    if (MODAL_FOCUS) {
      for (const index in this.id_to_window) {
        modal = modal || this.id_to_window[index].metadata.modal;
      }
    }
    if (modal && !win.metadata.modal) {
      // don't take focus from a modal window
      return;
    }

    const wid = win.wid;
    if (this.focused_wid === wid) {
      return;
    }

    // Keep DESKTOP-type windows per default settings lower than all other windows.
    // Only allow focus if all other windows are minimized.
    if (
      default_settings !== undefined &&
      default_settings.auto_fullscreen_desktop_class !== undefined &&
      default_settings.auto_fullscreen_desktop_class.length > 0
    ) {
      const auto_fullscreen_desktop_class = default_settings.auto_fullscreen_desktop_class;
      if (
        win.windowtype === "DESKTOP" &&
        win.metadata["class-instance"].includes(auto_fullscreen_desktop_class)
      ) {
        for (const index in this.id_to_window) {
          const otherwin = this.id_to_window[index];
          if (otherwin.wid !== win.wid && !otherwin.minimized) {
            return;
          }
        }
      }
    }

    const top_stacking_layer = Object.keys(this.id_to_window).length;
    const old_stacking_layer = win.stacking_layer;
    const had_focus = this.focused_wid;
    this.focused_wid = wid;
    this.send([PACKET_TYPES.focus, wid, []]);
    //set the focused flag on the window specified,
    //adjust stacking order:
    let iwin = null;
    for (const index in this.id_to_window) {
      iwin = this.id_to_window[index];
      iwin.focused = iwin.wid === wid;
      if (iwin.focused) {
        iwin.stacking_layer = top_stacking_layer;
        this.send_configure_window(iwin, {
          focused: true
        }, true);
      } else {
        //move it down to fill the gap:
        if (iwin.stacking_layer > old_stacking_layer) {
          iwin.stacking_layer--;
        }
        if (had_focus === index) {
          this.send_configure_window(iwin, {
            focused: false
          }, true);
        }
      }
      iwin.updateFocus();
      iwin.update_zindex();
    }
  }

  /*
   * detect DESKTOP-type window from settings
   */
  is_window_desktop(win) {
    if (
      default_settings !== undefined &&
      default_settings.auto_fullscreen_desktop_class !== undefined &&
      default_settings.auto_fullscreen_desktop_class.length > 0
    ) {
      const auto_fullscreen_desktop_class = default_settings.auto_fullscreen_desktop_class;
      if (
        win.windowtype === "DESKTOP" &&
        win.metadata["class-instance"].includes(auto_fullscreen_desktop_class)
      ) {
        return true;
      }
    }
    return false;
  }

  /*
   * Show/Hide the window preview list
   */
  toggle_window_preview(init_callback) {
    const preview_element = $(WINDOW_PREVIEW_SELECTOR);

    preview_element.on("init", (e, slick) => {
      if (init_callback) {
        init_callback(e, slick);
      }
    });

    preview_element.on("afterChange", (event, slick, currentSlide) => {
      const wid = $(".slick-current .window-preview-item-container").data("wid");
      const win = this.id_to_window[wid];
      if (!win.minimized) {
        win.focus();
      }
    });

    $(window).on("click", this._handle_window_list_blur);
    $(window).on("contextmenu", this._handle_window_list_blur);

    if (preview_element.is(":visible")) {
      // Restore the current selection if it's minimized.
      const wid = $(".slick-current .window-preview-item-container").data("wid");
      this.clog(`current wid: ${wid}`);
      const win = this.id_to_window[wid];
      if (win.minimized) {
        win.focus();
      }

      // Clear the list of window elements.
      preview_element.children().remove();

      preview_element.slick("unslick");
      preview_element.children().remove();
      preview_element.hide();
      preview_element.off("afterChange");
      preview_element.off("init");
      $(window).off("click", this._handle_window_list_blur);
      $(window).off("contextmenu", this._handle_window_list_blur);
      return;
    }

    // Clear the list of window elements.
    preview_element.children().remove();

    // Sort windows by stacking order.;
    const windows_sorted = Object.values(client.id_to_window).filter((win) => {
      // skip DESKTOP type windows.
      return !client.is_window_desktop(win);
    });

    if (windows_sorted.length === 0) {
      return;
    }

    const container_width = 200 * Math.min(4, windows_sorted.length);
    preview_element.css("width", `${container_width}px`);

    windows_sorted.sort((a, b) => {
      if (a.stacking_layer < b.stacking_layer) {
        return 1;
      }
      if (a.stacking_layer > b.stacking_layer) {
        return -1;
      }
      return 0;
    });

    // Add all open windows to the list.
    for (const index in windows_sorted) {
      const win = windows_sorted[index];
      const item_container = $("<div>");
      item_container.data("wid", win.wid);
      item_container.addClass("window-preview-item-container");

      // Text
      const item_text_element = $("<div>");
      item_text_element.addClass("window-preview-item-text");
      item_text_element.text(win.title);

      // Window image
      const png_base64 = win.canvas.toDataURL("image/png");
      const img_element = $("<img>");
      img_element.addClass("window-preview-item-img");
      img_element.attr("src", png_base64);

      item_container.append(item_text_element);
      item_container.append(img_element);

      preview_element.append(item_container);
    }

    preview_element.show();

    preview_element.slick({
      centerMode: true,
      focusOnSelect: true,
      focusOnChange: true,
      touchMove: false,
      centerPadding: "0px",
      slidesToShow: Math.max(1, Math.min(4, windows_sorted.length)),
      slidesToScroll: 1,
      infinite: true,
      adaptiveHeight: false,
      speed: 0,
      prevArrow: null,
      nextArrow: null,
      easing: "null",
      waitForAnimate: false,
    });
  }

  /*
   * Handle closing of window list if clickout outside of area.
   */
  _handle_window_list_blur(e) {
    if ($(WINDOW_PREVIEW_SELECTOR).is(":visible")) {
      if (e.target.id === WINDOW_PREVIEW_SELECTOR.slice(1)) {
        return;
      }
      if ($(e.target).parents(WINDOW_PREVIEW_SELECTOR).length > 0) {
        return;
      }
      if ($(e.target).hasClass("window-list-button")) {
        return;
      }
      if (
        $(e.target).parents(FLOAT_MENU_SELECTOR).length > 0 &&
        $(e.target).parent().has("#open_windows_list")
      ) {
        return;
      }
      // Clicked outside window list, close it.
      client.toggle_window_preview();
    }
  }

  /*
   * packet processing functions start here
   */

  on_open() {
    //this hook can be overriden
  }

  _process_open() {
    this.cancel_open_timer();
    // call the send_hello function
    this.on_connection_progress("WebSocket connection established", "", 60);
    // wait timeout seconds for a hello, then bomb
    this._send_hello();
    this.on_open();
  }

  schedule_open_timer() {
    this.cancel_open_timer();
    this.open_timer = setTimeout(() => {
      let reconnect = this.reconnect || this.reconnect_attempt < this.reconnect_count;
      if (reconnect) {
        this.close_protocol();
        this.reconnect_attempt++;
        this.do_reconnect();
      } else {
        this.disconnect_reason = "failed to open connection";
        this.close();
      }
    }, this.OPEN_TIMEOUT);
  }

  cancel_open_timer() {
    if (this.open_timer) {
      clearTimeout(this.open_timer);
      this.open_timer = null;
    }
  }

  schedule_hello_timer() {
    this.cancel_hello_timer();
    this.hello_timer = setTimeout(() => {
      this.disconnect_reason = "Did not receive hello before timeout reached, not an Xpra server?";
      this.close();
    }, this.HELLO_TIMEOUT);
  }

  cancel_hello_timer() {
    if (this.hello_timer) {
      clearTimeout(this.hello_timer);
      this.hello_timer = null;
    }
  }

  _process_error(packet) {
    const code = Number.parseInt(packet[2]);
    let reconnect = this.reconnect || this.reconnect_attempt < this.reconnect_count;
    if (reconnect && [0, 1006, 1008, 1010, 1014, 1015].includes(code)) {
      // don't re-connect unless we had actually managed to connect
      // (because these specific websocket error codes are likely permanent)
      reconnect = this.connected;
    }
    this.cerror("websocket error: ", packet[1], "code: ", code, "reason: ", this.disconnect_reason,
      ", connected: ", this.connected, ", reconnect: ", reconnect);
    if (this.reconnect_in_progress) {
      return;
    }
    this.packet_disconnect_reason(packet);
    this.close_audio();
    if (!reconnect) {
      // call the client's close callback
      this.close();
    }
  }

  packet_disconnect_reason(packet) {
    if (!this.disconnect_reason && packet[1]) {
      const code = packet[2];
      if (!this.connected && [0, 1006, 1008, 1010, 1014, 1015].includes(code)) {
        this.disconnect_reason = "connection failed, invalid address?";
      } else {
        this.disconnect_reason = packet[1];
        let index = 2;
        while (packet.length > index && packet[index]) {
          this.disconnect_reason += `\n${packet[index]}`;
          index++;
        }
      }
    }
  }

  do_reconnect() {
    //try again:
    this.reconnect_in_progress = true;
    setTimeout(() => {
      try {
        this.remove_windows();
        this.close_audio();
        this.cancel_all_files();
        this.clear_timers();
        this.init_state();
        this.close_protocol();
        this.emit_connection_lost();
        this.connect();
      } finally {
        this.reconnect_in_progress = false;
      }
    }, this.reconnect_delay);
  }

  _process_close(packet) {
    this.clog("websocket closed: ", packet[1], "reason: ", this.disconnect_reason,
      ", reconnect: ", this.reconnect, ", reconnect attempt: ", this.reconnect_attempt);
    if (this.reconnect_in_progress) {
      return;
    }
    this.packet_disconnect_reason(packet);
    if (this.reconnect && this.reconnect_attempt < this.reconnect_count) {
      this.emit_connection_lost();
      this.close_protocol();
      this.reconnect_attempt++;
      this.do_reconnect();
    } else {
      this.close();
    }
  }

  disconnect(reason) {
    this.disconnect_reason = reason || "unknown";
    this.close();
  }

  close() {
    if (this.reconnect_in_progress) {
      return;
    }
    this.clog("client closed");
    this.cancel_open_timer();
    this.cancel_hello_timer();
    this.cancel_all_files();
    this.emit_connection_lost();
    this.remove_windows();
    this.close_audio();
    this.clear_timers();
    this.close_protocol();
    // call the client's close callback
    this.callback_close(this.disconnect_reason);
  }

  _process_disconnect(packet) {
    this.debug("main", "disconnect reason:", packet[1]);
    if (this.reconnect_in_progress) {
      return;
    }
    // save the disconnect reason
    this.packet_disconnect_reason(packet);
    this.close();
    // call the client's close callback
    this.callback_close(this.disconnect_reason);
  }

  _process_startup_complete(packet) {
    this.log("startup complete");
    this.emit_connection_established();
  }

  _connection_change(e) {
    const ci = Utilities.getConnectionInfo();
    this.clog("connection status - change event=", e, ", connection info=", ci, "tell server:", this.server_connection_data);
    if (ci && this.server_connection_data) {
      this.send([PACKET_TYPES.connection_data, ci]);
    }
  }

  _process_hello(packet) {
    this.cancel_open_timer();
    this.cancel_hello_timer();
    const hello = packet[1];
    this.clog("received hello capabilities", hello);
    if (!hello["rencodeplus"]) {
      throw "no common packet encoders, 'rencodeplus' is required by this client";
    }

    this.session_name = hello["session_name"];
    $("title").text(this.session_name);

    this.server_display = hello["display"] || "";
    this.server_platform = hello["platform"] || "";
    this.server_remote_logging = hello["remote-logging.multi-line"];
    if (this.server_remote_logging && this.remote_logging) {
      //hook remote logging:
      Utilities.log = () => this.log(arguments);
      Utilities.warn = () => this.warn(arguments);
      Utilities.error = () => this.error(arguments);
      Utilities.exc = () => this.exc(arguments);
    }

    // check for server encryption caps update
    if (this.encryption) {
      this.cipher_out_caps = hello["encryption"];
      console.info("cipher out caps=", JSON.stringify(this.cipher_out_caps));
      this.protocol.set_cipher_out(this.cipher_out_caps, this.encryption_key);
    }

    const version = Utilities.s(hello["version"]);
    try {
      const vparts = version.split(".");
      const vno = vparts.map((x) => Number.parseInt(x));
      if (vno[0] <= 0 && vno[1] < 10) {
        this.disconnect(`unsupported version: ${version}`);
        this.close();
        return;
      }
    } catch {
      this.disconnect(`error parsing version number '${version}'`);
      this.close();
      return;
    }
    this.log("got hello: server version", version, "accepted our connection");
    // stuff that must be done after hello
    this._process_modifier_keycodes(hello["modifier_keycodes"] || {});
    this._process_audio_caps(hello["audio"] || {});
    if (SHOW_START_MENU) {
      this.xdg_menu = hello["xdg-menu"];
      if (this.xdg_menu) {
        this.process_xdg_menu();
      }
    }
    if (!hello["client-shutdown"]) {
      $("#shutdown_menu_entry").hide();
    }
    if (
      !this.file_transfer ||
      (!hello["file-transfer"] && (!hello["file"] || !hello["file"]["enabled"]))
    ) {
      $("#upload_menu_entry").hide();
      $("#download_menu_entry").hide();
    }

    this.server_is_desktop = Boolean(hello["desktop"]);
    this.server_is_shadow = Boolean(hello["shadow"]);
    this.server_readonly = Boolean(hello["readonly"]);
    if (this.server_is_desktop || this.server_is_shadow) {
      jQuery("body").addClass("desktop");
    }
    this.server_resize_exact = hello["resize_exact"] || false;
    this.server_screen_sizes = hello["screen-sizes"] || [];
    this.clog("server screen sizes:", this.server_screen_sizes);

    this.server_precise_wheel = hello["wheel.precise"] || false;

    this.remote_open_files = Boolean(hello["open-files"]);
    this.remote_file_transfer = Boolean(hello["file-transfer"]);
    this.remote_printing = Boolean(hello["printing"]);
    if (this.remote_printing && this.printing) {
      // send our printer definition
      const printers = {
        "HTML5 client": {
          "printer-info": "Print to PDF in client browser",
          "printer-make-and-model": "HTML5 client version",
          mimetypes: ["application/pdf"],
        },
      };
      this.send([PACKET_TYPES.printers, printers]);
    }
    this.server_connection_data = hello["connection-data"];
    if (Object.hasOwn(navigator, "connection")) {
      navigator.connection.addEventListener("change", this._connection_change);
      this._connection_change();
    }

    // don't send clipboard packets to servers that don't want them:
    this.clipboard_enabled = Boolean(hello["clipboard"] || false);

    // file transfer attributes:
    this.remote_file_size_limit = hello["max-file-size"];
    this.remote_file_chunks = Math.max(0, Math.min(this.remote_file_size_limit, hello["file-chunks"] || 0));

    // start sending our own pings
    this._send_ping();
    this.ping_timer = setInterval(() => this._send_ping(), this.PING_FREQUENCY);
    this.reconnect_attempt = 0;
    // Drop start_new_session to avoid creating new displays
    // on reconnect
    this.start_new_session = null;
    this.on_connection_progress("Session started", "", 100);
    this.on_connect();
    this.connected = true;

    this.send_keymap();
  }

  _process_control(packet) {
    const action = packet[1];
    console.info("control: ", action, packet);
    if (action === "log") {
        this.clog("log action:", packet);
    }
    else if (action === "redraw") {
        this.redraw_windows()
    }
    else if (action === "stop-audio") {
        this.close_audio();
    }
    else if (action === "toggle-keyboard") {
        toggle_keyboard();
    }
    else if (action === "toggle-float-menu") {
        toggle_float_menu();
    }
    else if (action === "toggle-window-preview") {
        toggle_window_preview();
    }
    else {
        this.cerror("unhandled control action:", action);
    }
  }

  _process_modifier_keycodes(modifier_keycodes) {
    // find the modifier to use for Num_Lock
    if (!modifier_keycodes) {
      return;
    }
    for (const modifier in modifier_keycodes) {
      if (Object.hasOwn(modifier_keycodes, modifier)) {
        const mappings = modifier_keycodes[modifier];
        for (const keycode in mappings) {
          const keys = mappings[keycode];
          for (const index in keys) {
            const key = keys[index];
            if (key === "Num_Lock") {
              this.num_lock_modifier = modifier;
            } else if (key === "Alt_L") {
              this.alt_modifier = modifier;
            } else if (key === "Meta_L") {
              this.meta_modifier = modifier;
            } else if (key === "ISO_Level3_Shift" || key === "Mode_switch") {
              this.altgr_modifier = modifier;
            } else if (key === "Control_L") {
              this.control_modifier = modifier;
            }
          }
        }
      }
    }
  }

  _process_audio_caps(audio_caps) {
    if (!this.audio_enabled) {
      this.on_audio_state_change("disabled", "");
      return;
    }
    if (!audio_caps["send"]) {
      this.audio_enabled = false;
      this.on_audio_state_change("disabled", "server does not support speaker forwarding");
      return;
    }
    this.server_audio_codecs = audio_caps["encoders"];
    if (!this.server_audio_codecs) {
      this.audio_enabled = false;
      this.on_audio_state_change("disabled", "audio codecs missing on the server");
      return;
    }
    this.log("audio codecs supported by the server:", this.server_audio_codecs);
    if (!this.server_audio_codecs.includes(this.audio_codec)) {
      this.warn(`audio codec ${this.audio_codec} is not supported by the server`);
      this.audio_codec = null;
      //find the best codec we can use:
      for (let codec of MediaSourceConstants.PREFERRED_CODEC_ORDER) {
        if (codec in this.audio_codecs && this.server_audio_codecs.includes(codec)) {
          this.audio_framework = this.mediasource_codecs[codec] ?
            "mediasource" :
            "aurora";
          this.audio_codec = codec;
          this.log("using", this.audio_framework, "audio codec", codec);
          break;
        }
      }
      if (!this.audio_codec) {
        this.audio_enabled = false;
        this.on_audio_state_change("disabled", "no matching audio codec");
        return;
      }
    }
    //with Firefox, we have to wait for a user event..
    if (this.audio_enabled && !Utilities.isFirefox()) {
      this._sound_start_receiving();
    }
  }

  _process_encodings(packet) {
    const caps = packet[1];
    this.log("update encodings:", Object.keys(caps));
  }

  process_xdg_menu() {
    this.log("received xdg start menu data");
    let key;
    //remove current menu:
    $("#startmenu li").remove();
    const startmenu = document.querySelector("#startmenu");
    for (key in this.xdg_menu) {
      const category = this.xdg_menu[key];
      const li = document.createElement("li");
      li.className = "-hasSubmenu";

      const catDivLeft = document.createElement("div");
      catDivLeft.className = "menu-divleft";
      catDivLeft.append(this.xdg_image(category.IconData, category.IconType));

      const a = document.createElement("a");
      a.append(catDivLeft);
      a.append(document.createTextNode(this.xdg_menu[key].Name));
      a.href = "#";
      li.append(a);

      const ul = document.createElement("ul");

      //TODO need to figure out how to do this properly
      a.addEventListener("mouseenter", function() {
        this.parentElement.childNodes[1].className = "-visible";
      });
      a.addEventListener("mouseleave", function() {
        this.parentElement.childNodes[1].className = "";
      });

      const xdg_menu_cats = category.Entries;
      for (key in xdg_menu_cats) {
        const entry = xdg_menu_cats[key];
        const li2 = document.createElement("li");
        const a2 = document.createElement("a");

        let name = entry.Name;
        name = Utilities.trimString(name, 15);
        let command = "";
        if (entry.Exec) {
          command = entry.Exec.replace(/%[FUfu]/g, "");
        }

        const divLeft = document.createElement("div");
        divLeft.className = "menu-divleft";
        divLeft.append(this.xdg_image(entry.IconData, entry.IconType));

        const titleDiv = document.createElement("div");
        titleDiv.append(document.createTextNode(name));
        titleDiv.className = "menu-content-left";
        divLeft.append(titleDiv);

        a2.append(divLeft);
        a2.title = command;

        const me = this;
        a2.addEventListener("click", function() {
          const ignore = "False";
          me.start_command(this.innerText, this.title, ignore);
          document.querySelector("#menu_list").className = "-hide";
        });
        a2.addEventListener("mouseenter", function() {
          this.parentElement.parentElement.className = "-visible";
        });
        a2.addEventListener("mouseleave", function() {
          this.parentElement.parentElement.className = "";
        });

        li2.append(a2);
        ul.append(li2);
      }
      li.append(ul);
      startmenu.append(li);
    }

    if (this.xdg_menu.length === 0) {
      startmenu.css("box-shadow", "none");
    }
  }

  _process_setting_change(packet) {
    const setting = packet[1];
    const value = packet[2];
    if ((setting === "xdg-menu" || setting === "menu") && SHOW_START_MENU) {
      this.xdg_menu = value;
      if (this.xdg_menu) {
        this.process_xdg_menu();
        $("#startmenuentry").show();
      }
    }
    else if (setting === "session_name") {
        this.session_name = value;
        jQuery("title").text(value);
    }
  }

  xdg_image(icon_data, icon_type) {
    const img = new Image();
    if (typeof icon_data !== "undefined") {
      let image_type = "image/" + icon_type;
      if (icon_type == "svg") {
        image_type = "image/svg+xml";
      }
      img.src = "data:" + image_type + ";base64," + Utilities.ArrayBufferToBase64(icon_data);
    }
    img.className = "menu-content-left";
    img.height = 24;
    img.width = 24;
    return img;
  }

  on_connect() {
    //this hook can be overriden
  }

  _process_challenge(packet) {
    this.cancel_open_timer();
    this.cancel_hello_timer();
    if (this.encryption) {
      if (packet.length >= 3) {
        this.cipher_out_caps = packet[2];
        this.protocol.set_cipher_out(this.cipher_out_caps, this.encryption_key);
      } else {
        this.disconnect("challenge does not contain encryption details to use for the response");
        return;
      }
    }
    const digest = packet[3];
    const server_salt = Uint8ToString(packet[1]);
    const salt_digest = packet[4] || "xor";
    const prompt = (packet[5] || "password").replace(/[^\d+,. /:a-z]/gi, "");
    this.clog("process challenge:", digest);
    const client = this;

    function call_do_process_challenge(password) {
      Utilities.clog("call_do_process_challenge(", password, ")");
      if (!client || !client.protocol) {
        return;
      }
      if (!password) {
        client.disconnect("password prompt cancelled");
        return;
      }
      client.do_process_challenge(digest, server_salt, salt_digest, password);
    }
    if (this.passwords.length > 0) {
      if (!this.is_digest_safe(digest)) {
        this.disconnect("refusing to send a password over an insecure connection");
        return;
      }
      const password = this.passwords.shift();
      call_do_process_challenge(password);
      return;
    }
    if (digest.startsWith("keycloak") && this.keycloak_prompt_fn) {
      this.keycloak_prompt_fn(server_salt, call_do_process_challenge);
      return;
    }
    if (this.password_prompt_fn && this.is_digest_safe(digest)) {
      if (!this.is_digest_safe(digest)) {
        this.disconnect("refusing to prompt for a password over an insecure connection");
        return;
      }
      const address = `${client.host}:${client.port}`;
      this.password_prompt_fn(`The server at ${address} requires a ${prompt}`, call_do_process_challenge);
      return;
    }
    this.disconnect("No password specified for authentication challenge");
  }

  is_digest_safe(digest) {
    return digest !== "xor" || this.ssl || this.encryption || this.insecure || Utilities.isSafeHost(this.host);
  }

  do_process_challenge(digest, server_salt, salt_digest, password) {
    let client_salt = null;
    let l = server_salt.length;
    //don't use xor over unencrypted connections unless explicitly allowed:
    if (!this.is_digest_safe(digest)) {
      this.disconnect(`server requested digest xor, cowardly refusing to use it without encryption with ${this.host}`);
      return;
    }

    if (salt_digest === "xor") {
      if (l < 16 || l > 256) {
        this.disconnect(`invalid server salt length for xor digest:${l}`);
        return;
      }
    } else {
      //other digest, 32 random bytes is enough:
      l = 32;
    }
    const challenge_digest = digest.startsWith("keycloak") ? "xor" : digest;
    client_salt = Utilities.getSecureRandomString(l);
    this.clog("combining client salt:", Utilities.convertToHex(client_salt));
    this.clog("with server salt:", Utilities.convertToHex(server_salt));
    this.clog("using", salt_digest);
    Utilities.gendigest(salt_digest, client_salt, server_salt)
      .then(salt => {
        const hex_salt = Utilities.convertToHex(salt);
        this.clog(salt_digest, ":", hex_salt);
        if (challenge_digest == "xor") {
          // shortcut: no need for async API, do not convert the result to hex
          const xored = Utilities.xor(password, hex_salt);
          this.do_send_hello(xored, client_salt);
          return;
        }

        Utilities.gendigest(challenge_digest, password, hex_salt)
          .then(challenge_response => {
            const hex_challenge = Utilities.convertToHex(challenge_response);
            this.do_send_hello(hex_challenge, client_salt)
          })
          .catch(err => {
            this.cerror("challenge digest error", err);
            this.disconnect("failed to generate challenge response " + err);
          });
      })
      .catch(err => {
        this.cerror("salt digest error", err);
        this.disconnect("failed to generate challenge response " + err);
      });
  }

  _send_ping() {
    if (this.reconnect_in_progress || !this.connected) {
      return;
    }
    const now_ms = Math.ceil(performance.now());
    this.send([PACKET_TYPES.ping, now_ms]);
    // add timeout to wait for ping timout
    this.ping_timeout_timer = setTimeout(
      () => this._check_echo_timeout(now_ms),
      this.PING_TIMEOUT
    );
    // add timeout to detect temporary ping miss for spinners
    const wait = 2000;
    this.ping_grace_timer = setTimeout(
      () => this._check_server_echo(now_ms),
      wait
    );
  }

  _process_ping(packet) {
    const echotime = packet[1];
    this.last_ping_server_time = echotime;
    if (packet.length > 2) {
      //prefer system time (packet[1] is monotonic)
      this.last_ping_server_time = packet[2];
    }
    let sid = "";
    if (packet.length >= 4) {
      sid = packet[3];
    }
    this.last_ping_local_time = Date.now();
    const l1 = 0;
    const l2 = 0;
    const l3 = 0;
    this.send([PACKET_TYPES.ping_echo, echotime, l1, l2, l3, 0, sid]);
  }

  _process_ping_echo(packet) {
    this.last_ping_echoed_time = packet[1];
    const l1 = packet[2];
    const l2 = packet[3];
    const l3 = packet[4];
    this.client_ping_latency = packet[5];
    this.server_ping_latency = Math.ceil(performance.now()) - this.last_ping_echoed_time;
    this.server_load = [l1 / 1000, l2 / 1000, l3 / 1000];
    // make sure server goes OK immediately instead of waiting for next timeout
    this._check_server_echo(0);
  }

  /**
   * Info
   */
  start_info_timer() {
    if (this.info_timer) {
        return;
    }
    this.info_timer = setInterval(() => {
      if (this.info_timer) {
        this.send_info_request();
      }
    }, this.INFO_FREQUENCY);
  }
  send_info_request() {
    if (!this.info_request_pending) {
      this.send([PACKET_TYPES.info_request, [this.uuid],
        [],
        []
      ]);
      this.info_request_pending = true;
    }
  }
  _process_info_response(packet) {
    this.info_request_pending = false;
    this.server_last_info = packet[1];
    this.debug("network", "info-response:", this.server_last_info);
    const event = document.createEvent("Event");
    event.initEvent("info-response", true, true);
    event.data = this.server_last_info;
    document.dispatchEvent(event);
  }
  stop_info_timer() {
    if (this.info_timer) {
      clearTimeout(this.info_timer);
      this.info_timer = null;
      this.info_request_pending = false;
    }
  }

  /**
   * System Tray forwarding
   */

  position_float_menu() {
    const float_menu_element = $(FLOAT_MENU_SELECTOR);
    const toolbar_height = float_menu_element.height();
    const toolbar_width = float_menu_element.width();
    let left = float_menu_element.offset().left || 0;
    let top = float_menu_element.offset().top || 0;
    const screen = $("#screen");
    const screen_width = screen.width();
    const screen_height = screen.height();

    if (this.toolbar_position === "custom") {
      //no calculations needed
    } else if (this.toolbar_position === "top-left") {
      left = 0;
      top = 0;
    } else if (this.toolbar_position === "top") {
      left = screen_width / 2 - toolbar_width / 2;
    } else if (this.toolbar_position === "top-right") {
      left = screen_width - toolbar_width;
    } else if (this.toolbar_position === "novnc") {
      left = 0;
      top = screen_height / 2 - toolbar_height / 2 - 100;
    }
    float_menu_element.offset({
      top,
      left
    });
  }

  _process_new_tray(packet) {
    const wid = packet[1];
    const metadata = packet[4];
    const mydiv = document.createElement("div");
    mydiv.id = String(wid);
    const mycanvas = document.createElement("canvas");
    mydiv.append(mycanvas);

    const float_tray = document.querySelector("#float_tray");
    const float_menu = document.querySelector(FLOAT_MENU_SELECTOR);
    const float_menu_element = $(FLOAT_MENU_SELECTOR);
    float_menu_element.children().show();
    //increase size for tray icon
    const new_width = float_menu_width + float_menu_item_size - float_menu_padding + 5;
    float_menu.style.width = `${new_width}px`;
    float_menu_width = float_menu_element.width() + 10;
    mydiv.style.backgroundColor = "white";

    float_tray.append(mydiv);
    const x = 0;
    const y = 0;
    const w = float_menu_item_size;
    const h = float_menu_item_size;

    mycanvas.width = w;
    mycanvas.height = h;
    this.id_to_window[wid] = new XpraWindow(this, wid,
      x, y, w, h,
      metadata, false, true, {},
      //TODO: send new tray geometry to the server using send_tray_configure
      () => this.debug("tray", "tray geometry changed (ignored)"),
      (event, window) => this.on_mousemove(event, window),
      (event, window) => this.on_mousedown(event, window),
      (event, window) => this.on_mouseup(event, window),
      (event, window) => this.on_mousescroll(event, window),
      () => this.debug("tray", "tray set focus (ignored)"),
      () => this.debug("tray", "tray closed (ignored)"),
      this.scale
    );
    this.send_tray_configure(wid);
  }

  send_tray_configure(wid) {
    const div = jQuery(`#${wid}`);
    const x = Math.round(div.offset().left);
    const y = Math.round(div.offset().top);
    const w = float_menu_item_size;
    const h = float_menu_item_size;
    this.clog("tray", wid, "position:", x, y);
    this.send([PACKET_TYPES.configure_window, Number(wid), x, y, w, h, {}]);
  }

  reconfigure_all_trays() {
    const float_menu = document.querySelector(FLOAT_MENU_SELECTOR);
    let float_menu_width = float_menu_item_size * float_menu_item_count + float_menu_padding;
    for (const twid in this.id_to_window) {
      const twin = this.id_to_window[twid];
      if (twin && twin.tray) {
        float_menu_width = float_menu_width + float_menu_item_size;
        this.send_tray_configure(twid);
      }
    }

    // only set if float_menu is visible
    if ($(FLOAT_MENU_SELECTOR).width() > 0) {
      float_menu.style.width = float_menu_width;
      this.position_float_menu();
    }
  }

  suspend() {
    // this is not a power event,
    // usually just triggered by the `visibilitychange` listener,
    // we only want to tell the server to slow down the refresh rate,
    const options = {
      "batch": {
        "reset": true,
        "delay": 1000,
        "locked": true,
        "always": true,
      },
    }
    this.clog("suspend event, sending control refresh with options=", options);
    this.send_control_refresh(1, options);
    for (const index in this.id_to_window) {
      const win = this.id_to_window[index];
      win.suspend();
    }
  }

  resume() {
    for (const index in this.id_to_window) {
      const win = this.id_to_window[index];
      win.resume();
    }
    const options = {
      "batch": {
        "reset": true,
      },
      "refresh-now": true,
    }
    this.clog("resume event, sending control refresh with options=", options);
    this.send_control_refresh(100, options);
    this.redraw_windows();
  }

  send_control_refresh(quality, options) {
    const wid = 0;
    const client_options = {};
    const packet = [PACKET_TYPES.buffer_refresh, wid, 0, quality, options, client_options];
    this.send(packet);
  }


/**
   * Windows
   */
  _new_window(wid, x, y, w, h, metadata, override_redirect, client_properties) {
    // each window needs their own DIV that contains a canvas
    const mydiv = document.createElement("div");
    mydiv.id = String(wid);

    const screen = document.querySelector("#screen");
    screen.append(mydiv);
    // create the XpraWindow object to own the new div
    const win = new XpraWindow(this, wid,
      x, y, w, h,
      metadata,
      override_redirect, false,
      client_properties,
      (window) => this.send_configure_window(window, {}, false),
      (event, window) => this.on_mousemove(event, window),
      (event, window) => this.on_mousedown(event, window),
      (event, window) => this.on_mouseup(event, window),
      (event, window) => this.on_mousescroll(event, window),
      (window) => this.set_focus(window),
      (window) => this.send_close_window(window),
      this.scale
    );
    if (this.server_is_desktop || this.server_is_shadow) {
      window.noWindowList();
    } else if (win && win.decorations) {
      const trimmedTitle = Utilities.trimString(win.title, 30);
      window.addWindowListItem(win, wid, trimmedTitle);
    }
    this.id_to_window[wid] = win;
    if (!override_redirect) {
      const geom = win.get_internal_geometry();
      this.send([PACKET_TYPES.map_window, wid, geom.x, geom.y, geom.w, geom.h, win.client_properties]);
      this.set_focus(win);
    }
  }

  _new_window_common(packet, override_redirect) {
    const wid = packet[1];
    let x = packet[2];
    let y = packet[3];
    let w = packet[4];
    let h = packet[5];
    const metadata = packet[6];
    if (wid in this.id_to_window)
      throw new Error(`we already have a window ${wid}`);
    if (w <= 0 || h <= 0) {
      this.error("window dimensions are wrong:", w, h);
      w = 1;
      h = 1;
    }
    let client_properties = {};
    if (packet.length >= 8) client_properties = packet[7];
    if (x === 0 && y === 0 && !metadata["set-initial-position"] && !metadata["fullscreen"]) {
      //find a good position for it
      const l = Object.keys(this.id_to_window).length;
      if (l === 0) {
        //first window: center it
        if (w <= this.desktop_width) {
          x = Math.round((this.desktop_width - w) / 2);
        }
        if (h <= this.desktop_height) {
          y = Math.round((this.desktop_height - h) / 2);
        }
      } else {
        x = Math.min(l * 10, Math.max(0, this.desktop_width - 100));
        y = 96;
      }
    }
    this._new_window(wid, x, y, w, h, metadata, override_redirect, client_properties);
    this._new_ui_event();
  }

  send_configure_window(win, state, skip_geometry) {
    const geom = win.get_internal_geometry();
    const wid = win.wid;
    const packet = [PACKET_TYPES.configure_window, wid, geom.x, geom.y, geom.w, geom.h,
      win.client_properties, 0, state, skip_geometry,
    ];
    this.send(packet);
  }

  _process_new_window(packet) {
    this._new_window_common(packet, false);
  }

  _process_new_override_redirect(packet) {
    this._new_window_common(packet, true);
  }

  _process_window_metadata(packet) {
    const wid = packet[1];
    const metadata = packet[2];
    const win = this.id_to_window[wid];
    if (win) {
      win.update_metadata(metadata);
    }
  }

  _process_initiate_moveresize(packet) {
    const wid = packet[1];
    const win = this.id_to_window[wid];
    if (!win) {
      this.log("cannot initiate moveresize, window", wid, "not found");
      return;
    }
    const x_root = packet[2];
    const y_root = packet[3];
    const direction = packet[4];
    const button = packet[5];
    const source_indication = packet[6];
    let event = this.mousedown_event;
    if (this.mouseup_event && direction === MOVERESIZE_CANCEL) {
      event = this.mouseup_event;
    }
    this.log("initiate moveresize on", win, "mouse event=", event);
    win.initiate_moveresize(event, x_root, y_root, direction, button, source_indication);
  }

  _process_pointer_position(packet) {
    const wid = packet[1];
    let x = packet[2];
    let y = packet[3];
    const win = this.id_to_window[wid];
    //we can use window relative coordinates:
    if (packet.length >= 6 && win) {
      const pos = win.get_internal_geometry();
      x = pos.x + packet[4];
      y = pos.y + packet[5];
    }
    const shadow_pointer = document.querySelector("#shadow_pointer");
    const style = shadow_pointer.style;
    let cursor_url;
    let w;
    let h;
    let xhot;
    let yhot;
    if (win.cursor_data) {
      cursor_url = win.cursor_data[0];
      xhot = win.cursor_data[1];
      yhot = win.cursor_data[2];
      w = win.cursor_data[3];
      h = win.cursor_data[4];
    } else {
      w = 32;
      h = 32;
      xhot = 8;
      yhot = 3;
      cursor_url = "icons/default_cursor.png";
    }
    x -= xhot;
    y -= yhot;
    style.width = `${w}px`;
    style.height = `${h}px`;
    shadow_pointer.src = cursor_url;
    style.left = `${x}px`;
    style.top = `${y}px`;
    style.display = "inline";
  }

  on_last_window() {
    //this hook can be overriden
  }

  _process_lost_window(packet) {
    const wid = packet[1];
    const win = this.id_to_window[wid];
    if (win && win.decorations) {
      window.removeWindowListItem(wid);
    }
    try {
      delete this.id_to_window[wid];
    } catch {}
    if (win) {
      win.destroy();
      this.clog("lost window, was tray=", win.tray);
      if (win.tray) {
        //other trays may have moved:
        this.reconfigure_all_trays();
      }
    }
    this.clog("lost window", wid, ", remaining: ", Object.keys(this.id_to_window));
    if (Object.keys(this.id_to_window).length === 0) {
      this.on_last_window();
      this.auto_focus();
    } else if (win && win.focused) {
      //it had focus, find the next highest:
      this.auto_focus();
    }
    if (this.decode_worker) {
      this.decode_worker.postMessage({cmd: "remove", wid});
    }
  }

  auto_focus() {
    let highest_window = null;
    let highest_stacking = -1;
    let modal = false;
    if (MODAL_FOCUS) {
      for (const index in this.id_to_window) {
        const win = this.id_to_window[index];
        modal = modal || win.metadata.modal;
      }
    }
    for (const index in this.id_to_window) {
      const win = this.id_to_window[index];
      if (win.minimized || win.tray) {
        continue;
      }
      if (modal && !win.metadata.modal) {
        continue;
      }
      if (win.stacking_layer > highest_stacking) {
        highest_window = win;
        highest_stacking = win.stacking_layer;
      }
    }
    if (highest_window) {
      this.set_focus(highest_window);
    } else {
      this.focused_wid = 0;
      this.send([PACKET_TYPES.focus, 0, []]);
    }
  }

  _process_raise_window(packet) {
    const wid = packet[1];
    const win = this.id_to_window[wid];
    this.set_focus(win);
  }

  _process_window_resized(packet) {
    const wid = packet[1];
    const width = packet[2];
    const height = packet[3];
    const win = this.id_to_window[wid];
    if (win) {
      win.resize(width, height);
    }
  }

  _process_window_move_resize(packet) {
    const [, wid, x, y, width, height] = packet;
    this.id_to_window[wid]?.move_resize(x, y, width, height);
  }

  _process_configure_override_redirect(packet) {
    const [, wid, x, y, width, height] = packet;
    this.id_to_window[wid]?.move_resize(x, y, width, height);
  }

  _process_desktop_size(packet) {
    //we don't use this yet,
    //we could use this to clamp the windows to a certain area
  }

  _process_bell(packet) {
    const percent = packet[3];
    const pitch = packet[4];
    const duration = packet[5];
    if (this.audio_context) {
      const oscillator = this.audio_context.createOscillator();
      const gainNode = this.audio_context.createGain();
      oscillator.connect(gainNode);
      gainNode.connect(this.audio_context.destination);
      gainNode.gain.setValueAtTime(percent, this.audio_context.currentTime);
      oscillator.frequency.setValueAtTime(pitch, this.audio_context.currentTime);
      oscillator.start();
      setTimeout(() => oscillator.stop(), duration);
    } else {
      const snd = new Audio(BELL_SOUND);
      snd.play();
    }
  }

  /**
   * Notifications
   */
  _process_notify_show(packet) {
    //TODO: add UI switch to disable notifications
    const nid = packet[2];
    const replaces_nid = packet[4];
    const summary = Utilities.s(packet[6]);
    const body = Utilities.s(packet[7]);
    const expire_timeout = packet[8];
    const icon = packet[9];
    const actions = packet[10];
    const hints = packet[11];
    if (window.closeNotification) {
      if (replaces_nid > 0) {
        window.closeNotification(replaces_nid);
      }
      window.closeNotification(nid);
    }

    const context = this;

    function notify() {
      let icon_url = "";
      if (icon && icon[0] === "png") {
        icon_url = `data:image/png;base64,${Utilities.ToBase64(icon[3])}`;
        context.clog("notification icon_url=", icon_url);
      }
      const notification = new Notification(summary, {
        body,
        icon: icon_url,
      });
      const reason = 2; //closed by the user - best guess...
      notification.addEventListener("close", () =>
        context.send([PACKET_TYPES.notification_close, nid, reason, ""])
      );
      notification.addEventListener("click", () =>
        context.log("user clicked on notification", nid)
      );
    }

    if ("Notification" in window && actions.length === 0) {
      //we have notification support in the browser
      if (Notification.permission === "granted") {
        notify();
        return;
      } else if (Notification.permission !== "denied") {
        Notification.requestPermission(function(permission) {
          if (permission === "granted") {
            notify();
          }
        });
        return;
      }
    }

    if (window.doNotification) {
      window.doNotification("info", nid, summary, body, expire_timeout, icon, actions, hints,
        function(nid, action_id) {
          context.send([PACKET_TYPES.notification_action, nid, action_id]);
        },
        function(nid, reason, text) {
          context.send([PACKET_TYPES.notification_close, nid, reason, text || ""]);
        }
      );
    }
    context._new_ui_event();
  }

  _process_notify_close(packet) {
    const nid = packet[1];
    if (window.closeNotification) {
      window.closeNotification(nid);
    }
  }

  /**
   * Cursors
   */
  reset_cursor() {
    for (const wid in this.id_to_window) {
      const win = this.id_to_window[wid];
      win.reset_cursor();
    }
  }

  _process_cursor(packet) {
    if (packet.length < 9) {
      this.reset_cursor();
      return;
    }
    //we require a png encoded cursor packet:
    const encoding = packet[1];
    if (encoding !== "png") {
      this.warn(`invalid cursor encoding: ${encoding}`);
      return;
    }
    const w = packet[4];
    const h = packet[5];
    const xhot = packet[6];
    const yhot = packet[7];
    const img_data = packet[9];
    for (const wid in this.id_to_window) {
      const win = this.id_to_window[wid];
      win.set_cursor(encoding, w, h, xhot, yhot, img_data);
    }
  }

  _process_window_icon(packet) {
    const wid = packet[1];
    const w = packet[2];
    const h = packet[3];
    const encoding = packet[4];
    const img_data = packet[5];
    this.debug("main", "window-icon: ", encoding, " size ", w, "x", h);
    const win = this.id_to_window[wid];
    if (win) {
      const source = win.update_icon(w, h, encoding, img_data);
      //update favicon too:
      if (wid === this.focused_wid || this.server_is_desktop || this.server_is_shadow) {
        jQuery("#favicon").attr("href", source);
      }
    }
  }

  /**
   * Window Painting
   */
  _process_draw(packet) {
    //ensure that the pixel data is in a byte array:
    const coding = Utilities.s(packet[6]);
    let img_data = packet[7];
    const raw_buffers = [];
    const now = performance.now();
    if (coding !== "scroll") {
      raw_buffers.push(img_data.buffer);
    }
    if (this.decode_worker) {
      this.decode_worker.postMessage({cmd: "decode", packet, start: now}, raw_buffers);
      //the worker draw event will call do_process_draw
    } else {
      this.do_process_draw(packet, now);
    }
  }

  _process_eos(packet) {
    this.do_process_draw(packet, 0);
    const wid = packet[1];
    if (this.decode_worker) {
      this.decode_worker.postMessage({cmd: "eos", wid});
    }
  }

  request_redraw(win) {
    if (document.hidden) {
      this.debug("draw", "not redrawing, document.hidden=", document.hidden);
      return;
    }

    if (this.offscreen_api && this.decode_worker) {
      this.decode_worker.postMessage({cmd: "redraw", wid: win.wid});
      return;
    }
    // request that drawing to screen takes place at next available opportunity if possible
    this.debug("draw", "request_redraw for", win);
    win.swap_buffers();
    if (!window.requestAnimationFrame) {
      // requestAnimationFrame is not available, draw immediately
      win.draw();
      return;
    }
    if (!this.pending_redraw.includes(win)) {
      this.pending_redraw.push(win);
    }
    if (this.draw_pending) {
      // already scheduled
      return;
    }
    // schedule a screen refresh if one is not already due:
    this.draw_pending = performance.now();
    window.requestAnimationFrame(() => {
      this.draw_pending_list();
    });
  }

  draw_pending_list() {
    const elapsed = performance.now() - this.draw_pending;
    this.debug("draw", "animation frame:", this.pending_redraw.length, "windows to paint, processing delay", elapsed, "ms");
    this.draw_pending = 0;
    // draw all the windows in the list:
    while (this.pending_redraw.length > 0) {
      const w = this.pending_redraw.shift();
      w.draw();
    }
  }

  do_send_damage_sequence(packet_sequence, wid, width, height, decode_time, message) {
    const protocol = this.protocol;
    if (!protocol) {
      return;
    }
    const packet = [PACKET_TYPES.damage_sequence, packet_sequence, wid, width, height, decode_time, message];
    if (decode_time < 0) {
      this.cwarn("decode error packet:", packet);
    }
    protocol.send(packet);
  }

  do_process_draw(packet, start) {
    if (!packet) {
      //no valid draw packet, likely handle errors for that here
      return;
    }
    const ptype = packet[0];
    const wid = packet[1];
    const win = this.id_to_window[wid];
    if (ptype === "eos") {
      this.debug("draw", "eos for window", wid);
      if (win) {
        win.eos();
      }
      return;
    }

    const width = packet[4];
    const height = packet[5];
    const coding = Utilities.s(packet[6]);
    const packet_sequence = packet[8];
    const options = packet[10] || {};
    const protocol = this.protocol;
    if (!protocol) {
      return;
    }
    const me = this;

    function send_damage_sequence(decode_time, message) {
      me.do_send_damage_sequence(packet_sequence, wid, width, height, decode_time, message);
    }
    const client = this;

    function decode_result(error) {
      const flush = options["flush"] || 0;
      let decode_time = Math.round(1000 * performance.now() - 1000 * start);
      if (flush === 0) {
        client.request_redraw(win);
      }
      if (error || start === 0) {
        client.request_redraw(win);
        decode_time = -1;
      }
      client.debug("draw", "decode time for ", coding, " sequence ", packet_sequence, ": ", decode_time, ", flush=", flush);
      send_damage_sequence(decode_time, error || "");
    }
    if (!win) {
      this.debug("draw", "cannot paint, window not found:", wid);
      send_damage_sequence(-1, `window ${wid} not found`);
      return;
    }
    if (coding === "offscreen-painted") {
      const decode_time = options["decode_time"];
      send_damage_sequence(decode_time || 0, "");
      return;
    }
    try {
      win.paint(packet, decode_result);
    } catch (error) {
      this.exc(error, "error painting", coding, "sequence no", packet_sequence);
      send_damage_sequence(-1, String(error));
      //there may be other screen updates pending:
      win.paint_pending = 0;
      win.may_paint_now();
      this.request_redraw(win);
    }
  }

  /**
   * Audio
   */
  init_audio(ignore_audio_blacklist) {
    this.debug("audio", "init_audio() enabled=", this.audio_enabled, ", mediasource enabled=",
      this.audio_mediasource_enabled, ", aurora enabled=", this.audio_aurora_enabled);
    if (this.audio_mediasource_enabled) {
      this.mediasource_codecs = MediaSourceUtil.getMediaSourceAudioCodecs(ignore_audio_blacklist);
      for (const codec_option in this.mediasource_codecs) {
        this.audio_codecs[codec_option] = this.mediasource_codecs[codec_option];
      }
    }
    if (this.audio_aurora_enabled) {
      this.aurora_codecs = MediaSourceUtil.getAuroraAudioCodecs();
      for (const codec_option in this.aurora_codecs) {
        if (codec_option in this.audio_codecs) {
          //we already have native MediaSource support!
          continue;
        }
        this.audio_codecs[codec_option] = this.aurora_codecs[codec_option];
      }
    }
    this.debug("audio", "codecs:", this.audio_codecs);
    if (!this.audio_codecs) {
      this.audio_codec = null;
      this.audio_enabled = false;
      this.warn("no valid audio codecs found");
      return;
    }
    if (!(this.audio_codec in this.audio_codecs)) {
      if (this.audio_codec) {
        this.warn(`invalid audio codec: ${this.audio_codec}`);
        this.warn(`codecs found: ${this.audio_codecs}`);
      }
      this.audio_codec = MediaSourceUtil.getDefaultAudioCodec(this.audio_codecs);
      if (this.audio_codec) {
        if (this.audio_mediasource_enabled && this.audio_codec in this.mediasource_codecs) {
          this.audio_framework = "mediasource";
        } else if (this.audio_aurora_enabled && !Utilities.isIE()) {
          this.audio_framework = "aurora";
        }
        if (this.audio_framework) {
          this.log(`using ${this.audio_framework} audio codec: ${this.audio_codec}`);
        } else {
          this.warn("no valid audio framework - cannot enable audio");
          this.audio_enabled = false;
        }
      } else {
        this.warn("no valid audio codec found");
        this.audio_enabled = false;
      }
    } else {
      this.log(`using ${this.audio_framework} audio codec: ${this.audio_codec}`);
    }
    this.log("audio codecs: ", Object.keys(this.audio_codecs));
  }

  _sound_start_receiving() {
    if (!this.audio_framework || !this.audio_codec) {
      //choose a codec + framework to use
      const codecs_supported = MediaSourceUtil.get_supported_codecs(this.audio_mediasource_enabled, this.audio_aurora_enabled, false);
      const audio_codec = MediaSourceUtil.get_best_codec(codecs_supported);
      if (!audio_codec) {
        this.log("no codec found");
        return;
      }
      const acparts = audio_codec.split(":");
      this.audio_framework = acparts[0];
      this.audio_codec = acparts[1];
    }
    try {
      this.audio_buffers = [];
      this.audio_buffers_count = 0;
      if (this.audio_framework === "mediasource") {
        this._sound_start_mediasource();
      } else {
        this._sound_start_aurora();
      }
    } catch (error) {
      this.exc(error, "error starting audio player");
    }
  }

  _send_sound_start() {
    this.log(`audio: requesting ${this.audio_codec} stream from the server`);
    this.send([PACKET_TYPES.sound_control, "start", this.audio_codec]);
  }

  _sound_start_aurora() {
    this.audio_aurora_ctx = AV.Player.fromXpraSource();
    this._send_sound_start();
  }

  _sound_start_mediasource() {
    const me = this;

    function audio_error(event) {
      if (!me.media_source) {
        //already closed
        me.debug("audio", `media_source is closed, ignoring audio error: ${event}`);
        return;
      }
      if (me.audio) {
        me.error(`${event} error: ${me.audio.error}`);
        if (me.audio.error) {
          me.error(MediaSourceConstants.ERROR_CODE[me.audio.error.code]);
        }
      } else {
        me.error(`${event} error`);
      }
      me.close_audio();
    }

    //Create a MediaSource:
    this.media_source = MediaSourceUtil.getMediaSource();
    if (this.debug) {
      MediaSourceUtil.addMediaSourceEventDebugListeners(this.media_source, "audio");
    }
    this.media_source.addEventListener("error", (e) =>
      audio_error("audio source")
    );

    //Create an <audio> element:
    this.audio = document.createElement("audio");
    this.audio.setAttribute("autoplay", true);
    if (this.debug) {
      MediaSourceUtil.addMediaElementEventDebugListeners(this.audio, "audio");
    }
    this.audio.addEventListener("play", () => this.clog("audio play!"));
    this.audio.addEventListener("error", () => audio_error("audio"));
    document.body.append(this.audio);

    //attach the MediaSource to the <audio> element:
    this.audio.src = window.URL.createObjectURL(this.media_source);
    this.audio_buffers = [];
    this.audio_buffers_count = 0;
    this.audio_source_ready = false;
    this.clog("audio waiting for source open event on", this.media_source);
    this.media_source.addEventListener("sourceopen", () => {
      this.log("audio media source open");
      if (this.audio_source_ready) {
        this.warn("ignoring: source already open");
        return;
      }
      //ie: codec_string = "audio/mp3";
      const codec_string = MediaSourceConstants.CODEC_STRING[this.audio_codec];
      if (!codec_string) {
        this.error(`invalid codec '${this.audio_codec}'`);
        this.close_audio();
        return;
      }
      this.log(`using audio codec string for ${this.audio_codec}: ${codec_string}`);

      //Create a SourceBuffer:
      let asb;
      try {
        asb = this.media_source.addSourceBuffer(codec_string);
      } catch (error) {
        this.exc(error, "audio setup error for", codec_string);
        this.close_audio();
        return;
      }
      this.audio_source_buffer = asb;
      asb.mode = "sequence";
      if (this.debug_categories.includes("audio")) {
        MediaSourceUtil.addSourceBufferEventDebugListeners(asb, "audio");
      }
      asb.addEventListener("error", (e) => audio_error("audio buffer"));
      this.audio_source_ready = true;
      this._send_sound_start();
    });
  }

  _send_sound_stop() {
    this.log("audio: stopping stream");
    this.send([PACKET_TYPES.sound_control, "stop"]);
  }

  close_audio() {
    if (this.connected && this.audio_enabled) {
      this._send_sound_stop();
    }
    if (this.audio_framework === "mediasource") {
      this._close_audio_mediasource();
    } else {
      this._close_audio_aurora();
    }
    this.on_audio_state_change("stopped", "closed");
  }

  _close_audio_aurora() {
    if (this.audio_aurora_ctx) {
      if (this.audio_aurora_ctx.context) {
        try {
          this.audio_aurora_ctx.context.close();
        } catch (error) {
          this.debug("audio", "error closing context", error);
        }
      }
      this.audio_aurora_ctx = null;
    }
  }

  _close_audio_mediasource() {
    this.log(`close_audio_mediasource: audio_source_buffer=${this.audio_source_buffer}, media_source=${this.media_source}, audio=${this.audio}`);
    this.audio_source_ready = false;
    if (this.audio) {
      if (this.media_source) {
        try {
          if (this.audio_source_buffer) {
            this.media_source.removeSourceBuffer(this.audio_source_buffer);
            this.audio_source_buffer = null;
          }
          if (this.media_source.readyState === "open") {
            this.media_source.endOfStream();
          }
        } catch (error) {
          this.exc(error, "audio media source EOS error");
        }
        this.media_source = null;
      }
      this._remove_audio_element();
    }
  }

  _remove_audio_element() {
    if (this.audio) {
      this.audio.src = "";
      this.audio.load();
      try {
        this.audio.remove();
      } catch (error) {
        this.debug("audio", "failed to remove audio from page:", error);
      }
      this.audio = null;
    }
  }

  _process_sound_data(packet) {
    try {
      const codec = Utilities.s(packet[1]);
      const buf = packet[2];
      const options = packet[3];
      const metadata = packet[4];

      if (codec !== this.audio_codec) {
        this.error(`invalid audio codec '${codec}' (expected ${this.audio_codec}), stopping audio stream`);
        this.close_audio();
        return;
      }

      if (options["start-of-stream"]) {
        this._audio_start_stream();
      }

      if (buf && buf.length > 0) {
        this.add_sound_data(codec, buf, metadata);
      }

      if (options["end-of-stream"]) {
        this.log("received end-of-stream from server");
        this.close_audio();
      }
    } catch (error) {
      this.on_audio_state_change("error", `${error}`);
      this.exc(error, "sound data error");
      this.close_audio();
    }
  }

  on_audio_state_change(newstate, details) {
    this.debug("on_audio_state_change:", newstate, details);
    this.audio_state = newstate;
    //can be overriden
  }

  add_sound_data(codec, buf, metadata) {
    let MIN_START_BUFFERS = 4;
    const MAX_BUFFERS = 250;
    const CONCAT = true;
    this.debug("audio", "sound-data: ", codec, ", ", buf.length, "bytes");
    if (this.audio_buffers.length >= MAX_BUFFERS) {
      this.warn(`audio queue overflowing: ${this.audio_buffers.length}, stopping`);
      this.on_audio_state_change("error", "queue overflow");
      this.close_audio();
      return;
    }
    if (metadata) {
      this.debug("audio", "audio metadata=", metadata);
      //push metadata first:
      for (const index in metadata) {
        const metadatum = metadata[index];
        this.debug("audio", "metadata[", index, "]=", metadatum, ", length=", metadatum.length, ", type=",
          Object.prototype.toString.call(metadatum)
        );
        this.audio_buffers.push(Utilities.u(metadatum));
      }
      //since we have the metadata, we should be good to go:
      MIN_START_BUFFERS = 1;
    }
    if (buf) {
      this.audio_buffers.push(buf);
    }
    const ab = this.audio_buffers;
    if (this._audio_ready() && (this.audio_buffers_count > 0 || ab.length >= MIN_START_BUFFERS)) {
      if (CONCAT) {
        if (ab.length === 1) {
          // shortcut, no need to copy!
          buf = ab[0];
        } else {
          // concatenate all pending buffers into one:
          let size = ab.reduce((accumulator, value) => accumulator + value.length, 0);
          buf = new Uint8Array(size);
          size = 0;
          for (let index = 0, stop = ab.length; index < stop; ++index) {
            const v = ab[index];
            if (v.length > 0) {
              buf.set(v, size);
              size += v.length;
            }
          }
        }
        this.audio_buffers_count += 1;
        this.push_audio_buffer(buf);
      } else {
        this.audio_buffers_count += ab.length;
        for (let index = 0, stop = ab.length; index < stop; ++index) {
          this.push_audio_buffer(ab[index]);
        }
      }
      this.audio_buffers = [];
    }
  }

  _audio_start_stream() {
    this.debug("audio", `audio start of ${this.audio_framework} ${this.audio_codec} stream`);
    if (this.audio_state === "playing" || this.audio_state === "waiting") {
      //nothing to do: ready to play
      return;
    }
    this.on_audio_state_change("waiting", `${this.audio_framework} playing ${this.audio_codec} stream`);
    if (this.audio_framework === "mediasource") {
      const play = this.audio.play();
      if (!play) {
        this.on_audio_state_change("error", "no promise");
        this.close_audio();
        return;
      }
      play.then(
        (result) => {
          this.debug("audio", "stream playing", result);
        },
        (error) => {
          this.on_audio_state_change("error", `stream failed:${error}`);
          this.close_audio();
        }
      );
    } else if (this.audio_framework === "http-stream") {
      this.log("invalid start-of-stream data for http-stream framework");
    } else if (this.audio_framework === "aurora") {
      this.audio_aurora_ctx.play();
    } else {
      this.on_audio_state_change("error", `unknown framework ${this.audio_framework}`);
      this.close_audio();
    }
  }

  _audio_ready() {
    if (this.audio_framework === "mediasource") {
      //check media source buffer state:
      if (this.audio) {
        this.debug("audio", "mediasource state=",
          MediaSourceConstants.READY_STATE[this.audio.readyState],
          ", network state=",
          MediaSourceConstants.NETWORK_STATE[this.audio.networkState]
        );
        this.debug("audio", "audio paused=", this.audio.paused,
          ", queue size=", this.audio_buffers.length, ", source ready=", this.audio_source_ready,
          ", source buffer updating=", this.audio_source_buffer.updating);
      }
      const asb = this.audio_source_buffer;
      return Boolean(asb && !asb.updating);
    } else {
      return Boolean(this.audio_aurora_ctx);
    }
  }

  push_audio_buffer(buf) {
    if (this.audio_framework === "mediasource") {
      this.audio_source_buffer.appendBuffer(buf);
      const b = this.audio_source_buffer.buffered;
      if (b && b.length > 0) {
        const e = b.end(0);
        const buf_size = Math.round(1000 * (e - this.audio.currentTime));
        this.debug("audio", "buffer size=", buf_size, "ms, currentTime=", this.audio.currentTime);
      }
    } else {
      this.audio_aurora_ctx.asset.source._on_data(buf);
      this.debug("audio", "playing=", this.audio_aurora_ctx.playing,
        "buffered=", this.audio_aurora_ctx.buffered,
        "currentTime=", this.audio_aurora_ctx.currentTime,
        "duration=", this.audio_aurora_ctx.duration,
      );
      if (this.audio_aurora_ctx.format) {
        this.debug("audio",
          "formatID=", this.audio_aurora_ctx.format.formatID,
          "sampleRate=", this.audio_aurora_ctx.format.sampleRate
        );
      }
      this.debug("audio",
        "active=", this.audio_aurora_ctx.asset.active,
        "decoder=", this.audio_aurora_ctx.asset.decoder,
        "demuxer=", this.audio_aurora_ctx.demuxer,
      );
    }
    this.on_audio_state_change("playing", "");
  }

  /**
   * Clipboard
   */
  get_clipboard_buffer() {
    return this.clipboard_buffer;
  }
  get_clipboard_datatype() {
    return this.clipboard_datatype;
  }

  send_clipboard_token(data, data_format) {
    if (!this.clipboard_enabled || !this.connected) {
      return;
    }
    const claim = true; //Boolean(navigator.clipboard && navigator.clipboard.readText && navigator.clipboard.writeText);
    const greedy = true;
    const synchronous = true;
    let actual_data_format = data_format;
    if (!actual_data_format) {
      actual_data_format = [TEXT_PLAIN, UTF8_STRING];
      if (this.clipboard_preferred_format === UTF8_STRING) {
        actual_data_format = [UTF8_STRING, TEXT_PLAIN];
      }
    }

    this.debug("clipboard", "sending clipboard token with data:", data, "as", actual_data_format);
    let packet;
    packet = data ?
      [
        PACKET_TYPES.clipboard_token,
        "CLIPBOARD",
        actual_data_format,
        UTF8_STRING,
        UTF8_STRING,
        8,
        "bytes",
        data,
        claim,
        greedy,
        synchronous,
      ] :
      [
        PACKET_TYPES.clipboard_token,
        "CLIPBOARD",
        [],
        "",
        "",
        8,
        "bytes",
        "",
        claim,
        greedy,
        synchronous,
      ];
    this.send(packet);
  }

  _process_clipboard_token(packet) {
    if (!this.clipboard_enabled) {
      return;
    }
    const selection = packet[1];
    let targets = [];
    let target = null;
    let dtype = null;
    let dformat = null;
    let wire_encoding = null;
    let wire_data = null;
    if (packet.length >= 3) {
      targets = packet[2];
    }
    if (packet.length >= 8) {
      target = packet[3];
      dtype = packet[4];
      dformat = packet[5];
      wire_encoding = packet[6];
      wire_data = packet[7];
      //always keep track of the latest server buffer
      this.clipboard_server_buffers[selection] = [target, dtype, dformat, wire_encoding, wire_data];
    }

    const is_valid_target = target && this.clipboard_targets.includes(target);
    this.debug("clipboard", "clipboard token received");
    this.debug("clipboard", "targets=", targets);
    this.debug("clipboard", "target=", target, "is valid:", is_valid_target);
    this.debug("clipboard", "dtype=", dtype, "dformat=", dformat, "wire-encoding=", wire_encoding);
    // if we have navigator.clipboard support in the browser,
    // we can just set the clipboard value here,
    // otherwise we don't actually set anything
    // because we can't (the browser security won't let us)
    // we just record the value and actually set the clipboard
    // when we get a click, control-C or control-X event
    // (when access to the clipboard is allowed)
    if (is_valid_target) {
      const is_text = dtype.toLowerCase().includes("text") || dtype.toLowerCase().includes("string");
      if (is_text) {
        try {
          wire_data = Utilities.Uint8ToString(wire_data);
        } catch {}
        if (this.clipboard_buffer !== wire_data) {
          this.clipboard_datatype = dtype;
          this.clipboard_buffer = wire_data;
          this.clipboard_pending = true;
          if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(wire_data).then(
              () => {
                this.debug("clipboard", "writeText succeeded");
                this.clipboard_pending = false;
              },
              () => this.debug("clipboard", "writeText failed")
            );
          }
        }
      } else if (CLIPBOARD_IMAGES && dtype === "image/png" && dformat === 8 && wire_encoding === "bytes" &&
        navigator.clipboard && Object.hasOwn(navigator.clipboard, "write")
      ) {
        this.debug("clipboard", "png image received");
        const blob = new Blob([wire_data], {
          type: dtype
        });
        this.debug("clipboard", "created blob", blob);
        const item = new ClipboardItem({
          "image/png": blob
        });
        this.debug("clipboard", "created ClipboardItem", item);
        const items = [item];
        this.debug("clipboard", "created ClipboardItem list", items);
        navigator.clipboard.write(items).then(
          () => this.debug("clipboard", "copied png image to clipboard"),
          (error) => this.debug("clipboard", "failed to set png image", error)
        );
      }
    }
  }

  _process_set_clipboard_enabled(packet) {
    if (!this.clipboard_enabled) {
      return;
    }
    this.clipboard_enabled = packet[1];
    this.log(`server set clipboard state to ${packet[1]} reason was: ${packet[2]}`);
  }

  _process_clipboard_request(packet) {
    // we shouldn't be handling clipboard requests
    // unless we have support for navigator.clipboard:
    const request_id = packet[1];
    const selection = packet[2];

    this.debug("clipboard", `${selection} request`);

    //we only handle CLIPBOARD requests,
    //PRIMARY is used read-only
    if (selection !== "CLIPBOARD") {
      this.send_clipboard_string(request_id, selection, "");
      return;
    }

    if (navigator.clipboard) {
      if (Object.hasOwn(navigator.clipboard, "read")) {
        this.debug("clipboard", "request using read()");
        navigator.clipboard.read().then(
          (data) => {
            this.debug("clipboard", "request via read() data=", data);
            for (const index in data) {
              const item = data[index];
              this.debug("clipboard", "item", index, "types:", item.types);
              for (const item_type of item.types) {
                if (item_type === TEXT_PLAIN) {
                  item.getType(item_type).then(
                    (blob) => {
                      const fileReader = new FileReader();
                      fileReader.addEventListener("load", (event) =>
                        this.send_clipboard_string(request_id, selection, event.target.result)
                      );
                      fileReader.readAsText(blob);
                    },
                    (error) => {
                      this.debug("clipboard", `getType('${item_type}') failed`, error);
                      //send last server buffer instead:
                      this.resend_clipboard_server_buffer();
                    }
                  );
                  return;
                } else if (item_type === "image/png") {
                  item.getType(item_type).then(
                    (blob) => {
                      const fileReader = new FileReader();
                      fileReader.addEventListener("load", (event) =>
                        this.send_clipboard_contents(request_id, selection, item_type, 8, "bytes", event.target.result)
                      );
                      fileReader.readAsText(blob);
                    },
                    (error) => {
                      this.debug("clipboard", `getType('${item_type}') failed`, error);
                      //send last server buffer instead:
                      this.resend_clipboard_server_buffer(request_id, selection);
                    }
                  );
                  return;
                }
              }
            }
          },
          (error) => {
            this.debug("clipboard", "read() failed:", error);
            //send last server buffer instead:
            this.resend_clipboard_server_buffer(request_id, selection);
          }
        );
        return;
      } else if (Object.hasOwn(navigator.clipboard, "readText")) {
        this.debug("clipboard", "clipboard request using readText()");
        navigator.clipboard.readText().then(
          (text) => {
            this.debug("clipboard", "clipboard request via readText() text=", text);
            const primary_server_buffer = this.clipboard_server_buffers["PRIMARY"];
            if (
              primary_server_buffer &&
              primary_server_buffer[2] === 8 &&
              primary_server_buffer[3] === "bytes" &&
              text === primary_server_buffer[4]
            ) {
              //we have set the clipboard contents to the PRIMARY selection
              //and the server is asking for the CLIPBOARD selection
              //send it back the last value it gave us
              this.debug("clipboard request: using backup value");
              this.resend_clipboard_server_buffer(request_id, selection);
              return;
            }
            this.send_clipboard_string(request_id, selection, text);
          },
          (error) => {
            this.debug("clipboard", "readText() failed:", error);
            //send last server buffer instead:
            this.resend_clipboard_server_buffer(request_id, selection);
          }
        );
        return;
      }
    }
    const clipboard_buffer = this.get_clipboard_buffer() || "";
    this.send_clipboard_string(request_id, selection, clipboard_buffer, UTF8_STRING);
  }

  resend_clipboard_server_buffer(request_id, selection) {
    const server_buffer = this.clipboard_server_buffers["CLIPBOARD"];
    this.debug("clipboard", "resend_clipboard_server_buffer:", server_buffer);
    if (!server_buffer) {
      this.send_clipboard_string(request_id, selection, "", UTF8_STRING);
      return;
    }
    //const target = server_buffer[0];
    const dtype = server_buffer[1];
    const dformat = server_buffer[2];
    const wire_encoding = server_buffer[3];
    const wire_data = server_buffer[4];
    this.send_clipboard_contents(request_id, selection, dtype, dformat, wire_encoding, wire_data);
  }

  send_clipboard_none(request_id, selection) {
    const packet = [PACKET_TYPES.clipboard_contents_none, request_id, selection];
    this.debug("clipboard", "sending clipboard-contents-none");
    this.send(packet);
  }

  send_clipboard_string(request_id, selection, clipboard_buffer, datatype) {
    if (clipboard_buffer === "") {
      this.send_clipboard_none(request_id, selection);
      return;
    }
    const packet = [PACKET_TYPES.clipboard_contents, request_id, selection, datatype || UTF8_STRING, 8, "bytes", clipboard_buffer];
    this.debug("clipboard", "send_clipboard_string: packet=", packet);
    this.send(packet);
  }

  send_clipboard_contents(request_id, selection, datatype, dformat, encoding, clipboard_buffer) {
    if (clipboard_buffer === "") {
      this.send_clipboard_none(request_id, selection);
      return;
    }
    const packet = [PACKET_TYPES.clipboard_contents, request_id, selection, datatype, dformat || 8, encoding || "bytes", clipboard_buffer];
    this.send(packet);
  }

  /**
   * File transfers and printing
   */
  _process_send_file(packet) {
    const basefilename = Utilities.s(packet[1]);
    const mimetype = Utilities.s(packet[2]);
    const printit = packet[3];
    const filesize = packet[5];
    const data = packet[6];
    const options = packet[7] || {};
    const send_id = Utilities.s(packet[8]);

    // check the data size for file
    if (filesize <= 0 || filesize > FILE_SIZE_LIMIT) {
      this.error("send-file: invalid data size, received", data.length, "bytes, expected", filesize);
      return;
    }
    // removed hash checks because crypto.subtle is asynchronous, which is a pain
    if (data.length === filesize) {
      // got the whole file
      for (const digest of ["sha512", "sha384", "sha256", "sha224", "sha1"]) {
        const digest_value = options[digest];
        if (digest_value) {
          // not implemented!
          this.log("digest check not implemented for", digest);
        }
      }
      this._got_file(basefilename, data, printit, mimetype, options);
      return;
    }
    if (!send_id) {
      this.cerror("send-file: partial file is missing send-id");
      return;
    }
    const chunk_id = Utilities.s(options["file-chunk-id"] || "");
    if (!chunk_id) {
      this.cerror("send-file: partial file is missing file-chunk-id");
      return;
    }
    const chunk = 0;
    if (this.receive_chunks_in_progress.size > MAX_CONCURRENT_FILES) {
      this.cancel_file(chunk_id, "too many concurrent files being downloaded", chunk);
      return;
    }
    //start receiving chunks:
    let writer = null;
    try {
      //try to use a stream saver:
      this.debug("file", "streamSaver=", streamSaver);
      streamSaver.mitm = "./mitm.html";
      const fileStream = streamSaver.createWriteStream(basefilename, {
        size: filesize,
      });
      writer = fileStream.getWriter();
      this.debug("file", "stream writer=", writer);
    } catch (error) {
      writer = [];
      this.error("cannot use streamSaver:", error);
    }
    const timer = setTimeout(
      () => this._check_chunk_receiving(chunk_id, chunk),
      CHUNK_TIMEOUT
    );
    const openit = true;
    const chunk_state = [Date.now(), writer, basefilename, mimetype, printit, openit, filesize,
      options, digest, 0, false, send_id, timer, chunk,
    ];
    this.receive_chunks_in_progress.set(chunk_id, chunk_state);
    this.send([PACKET_TYPES.ack_file_chunk, chunk_id, true, "", chunk]);
    this.log("receiving chunks for", basefilename, "with transfer id", chunk_id);
  }

  _check_chunk_receiving(chunk_id, chunk_no) {
    const chunk_state = this.receive_chunks_in_progress.get(chunk_id);
    this.debug("file", "check_chunk_receiving(", chunk_id, ",", chunk_no, ") chunk_state=", chunk_state);
    if (!chunk_state) {
      return;
    }
    if (chunk_state[10]) {
      //transfer has been cancelled
      return;
    }
    chunk_state[12] = 0; //this timer has been used
    if (chunk_state[13] === 0) {
      this.cerror("Error: chunked file transfer", chunk_id, "timed out");
      this.receive_chunks_in_progress.delete(chunk_id);
    }
  }

  cancel_all_files(reason = "closing") {
    this.clog("cancel_all_files(", reason, ") will cancel:", [
      ...this.receive_chunks_in_progress.keys(),
    ]);
    for (const chunk_id of this.receive_chunks_in_progress.keys()) {
      this.cancel_file(chunk_id, reason);
    }
  }

  active_file_transfers() {
    return this.receive_chunks_in_progress.size;
  }

  cancel_file(chunk_id, message, chunk) {
    const chunk_state = this.receive_chunks_in_progress.get(chunk_id);
    if (chunk_state) {
      //mark it as cancelled:
      chunk_state[10] = true;
      //free the buffers
      const writer = chunk_state[1];
      if (writer.abort) {
        writer.abort();
      }
      chunk_state[1] = null;
      //stop the timer
      const timer = chunk_state[12];
      if (timer) {
        clearTimeout(timer);
        chunk_state[12] = 0;
      }
      //remove this transfer after a little while,
      //so in-flight packets won't cause errors
      setTimeout(
        () => this.receive_chunks_in_progress.delete(chunk_id),
        20_000
      );
    }
    this.send([PACKET_TYPES.ack_file_chunk, chunk_id, false, message, chunk]);
  }

  _process_send_file_chunk(packet) {
    const chunk_id = Utilities.s(packet[1]);
    const chunk = packet[2];
    const file_data = packet[3];
    const has_more = packet[4];
    this.debug("file", "_process_send_file_chunk(", chunk_id, chunk, `${file_data.length} bytes`, has_more, ")");
    const chunk_state = this.receive_chunks_in_progress.get(chunk_id);
    if (!chunk_state) {
      this.error("Error: cannot find the file transfer id", chunk_id);
      this.cancel_file(chunk_id, `file transfer id${chunk_id}not found`, chunk);
      return;
    }
    if (chunk_state[10]) {
      this.debug("file", "got chunk for a cancelled file transfer, ignoring it");
      return;
    }
    const filesize = chunk_state[6];
    if (chunk_state[13] + 1 !== chunk) {
      this.cancel_file(chunk_id, `chunk number mismatch, expected ${chunk_state[13] + 1} but got ${chunk}`);
      return;
    }
    //update chunk number:
    chunk_state[13] = chunk;
    const written = chunk_state[9] + file_data.length;
    if (written > filesize) {
      this.cancel_file(chunk_id, "too much data received");
      return;
    }
    const writer = chunk_state[1];
    if (writer.write) {
      //this is a file stream writer:
      try {
        const p = writer.write(file_data);
        //depending on the implementation,
        //this may be a promise:
        if (p) {
          p.then(
            () => {
              chunk_state[9] = written;
              this.file_chunk_written(packet);
            },
            (error) => {
              let message = "cannot write file data, download cancelled?";
              if (error) {
                this.clog("write failed:", error);
                message = `cannot write file data: ${error}, download cancelled?`;
              }
              this.cancel_file(chunk_id, message);
            }
          );
          //we will continue when the promise resolves, see above
          return;
        }
        this.clog("write(..)=", p);
      } catch (error) {
        const message = "cannot write file data - download cancelled?";
        this.error(error);
        this.cancel_file(chunk_id, message);
        return;
      }
    } else {
      //just a plain array:
      writer.push(file_data);
    }
    chunk_state[9] = written;
    this.file_chunk_written(packet);
  }

  file_chunk_written(packet) {
    const chunk_id = Utilities.s(packet[1]);
    const chunk = packet[2];
    const file_data = packet[3];
    const has_more = packet[4];
    const chunk_state = this.receive_chunks_in_progress.get(chunk_id);
    const writer = chunk_state[1];
    const filesize = chunk_state[6];
    const digest = chunk_state[8];
    const written = chunk_state[9];
    if (digest) {
      digest.update(Utilities.Uint8ToString(file_data));
    }
    this.send([PACKET_TYPES.ack_file_chunk, chunk_id, true, "", chunk]);
    if (has_more) {
      const timer = chunk_state[12];
      if (timer) {
        clearTimeout(timer);
      }
      //remote end will send more after receiving the ack
      chunk_state[12] = setTimeout(
        () => this._check_chunk_receiving(chunk_id, chunk),
        CHUNK_TIMEOUT
      );
      return;
    }
    this.receive_chunks_in_progress.delete(chunk_id);
    //check file size and digest then process it:
    if (written !== filesize) {
      this.cancel_file(chunk_id, `file size mismatch: expected a file of ${filesize} bytes but got ${written}`);
      return;
    }
    const options = chunk_state[7];
    if (digest && !this.verify_digest(digest, options[digest.algorithm])) {
      this.cancel_file(chunk_id, `${digest.algorithm} checksum mismatch`);
      return;
    }
    const start_time = chunk_state[0];
    const elapsed = Date.now() - start_time;
    this.clog(filesize, "bytes received in", chunk, "chunks, took", Math.round(elapsed * 1000), "ms");
    const filename = chunk_state[2];
    const mimetype = chunk_state[3];
    const printit = chunk_state[4];
    //join all the data into a single typed array:
    const data = new Uint8Array(filesize);
    let start = 0;
    if (writer.close) {
      writer.close();
    } else {
      const chunks = chunk_state[1];
      for (const chunk_ of chunks) {
        data.set(chunk_, start);
        start += chunk_.length;
      }
      this._got_file(filename, data, mimetype, printit, mimetype, options);
    }
  }

  verify_digest(digest, expected_value) {
    const algo = digest.algorithm;
    const value = digest.digest().data;
    const hex_value = Utilities.convertToHex(value);
    if (hex_value !== expected_value.toLowerCase()) {
      this.error("Error verifying", algo, "file checksum");
      this.error(" expected", expected_value, "but got", hex_value);
      return false;
    }
    this.log("verified", algo, "digest of file transfer");
    return true;
  }

  _got_file(basefilename, data, printit, mimetype, options) {
    if (printit) {
      this.print_document(basefilename, data, mimetype);
    } else {
      this.save_file(basefilename, data, mimetype);
    }
  }

  save_file(filename, data, mimetype) {
    if (!this.file_transfer || !this.remote_file_transfer) {
      this.warn("Received file-transfer data but this is not enabled!");
      return;
    }
    if (!mimetype) {
      mimetype = "application/octet-binary";
    }
    this.log(`saving ${data.length} bytes of ${mimetype} data to filename ${filename}`);
    Utilities.saveFile(filename, data, {
      type: mimetype
    });
  }

  print_document(filename, data, mimetype) {
    if (!this.printing || !this.remote_printing) {
      this.warn("Received data to print but printing is not enabled!");
      return;
    }
    if (mimetype !== "application/pdf") {
      this.warn(`Received unsupported print data mimetype: ${mimetype}`);
      return;
    }
    this.log(`got ${data.length} bytes of PDF to print`);
    const file = new Blob([data], {
      type: mimetype
    });
    const fileURL = URL.createObjectURL(file);
    const win = window.open(fileURL);
    if (!win || win.closed || typeof win.closed == "undefined") {
      this.warn("popup blocked, saving to file instead");
      Utilities.saveFile(filename, data, {
        type: mimetype
      });
    } else {
      win.print();
    }
  }

  send_all_files(files) {
    for (let index = 0, f;
      (f = files[index]); index++) {
      this.send_file(f);
    }
  }

  send_file(f) {
    clog("send_file:", f.name, ", type:", f.type, ", size:", f.size);
    const fileReader = new FileReader();
    fileReader.onloadend = (event_) => {
      const u8a = new Uint8Array(event_.target.result);
      this.do_send_file(f.name, f.type, f.size, u8a);
    };
    fileReader.readAsArrayBuffer(f);
  }

  do_send_file(filename, mimetype, size, buffer) {
    if (!this.file_transfer || !this.remote_file_transfer) {
      this.warn("cannot send file: file transfers are disabled!");
      return;
    }
    let cdata = buffer;
    const options = {};
    const chunk_size = Math.min(FILE_CHUNKS_SIZE, this.remote_file_chunks || 0);
    if (chunk_size > 0 && size > chunk_size) {
      if (this.send_chunks_in_progress.size >= MAX_CONCURRENT_FILES) {
        throw Exception(`too many file transfers in progress:${this.send_chunks_in_progress.size}`);
      }
      //chunking is supported and the file is big enough
      const chunk_id = Utilities.getHexUUID();
      options["file-chunk-id"] = chunk_id;
      //timer to check that the other end is requesting more chunks:
      const timer = setTimeout(() => {
        this._check_chunk_sending(chunk_id, 0);
      }, CHUNK_TIMEOUT);
      const chunk_state = [Date.now(), buffer, chunk_size, timer, 0];
      this.send_chunks_in_progress.set(chunk_id, chunk_state);
      cdata = "";
      this.debug("file", "using chunks, sending initial file-chunk-id=", chunk_id, ", for chunk size", chunk_size);
    } else {
      //send everything now:
      this.debug("file", "sending full file:", size, "bytes, chunk size", chunk_size);
    }
    const packet = [PACKET_TYPES.send_file, filename, mimetype, false, this.remote_open_files, size, cdata, options];
    this.send(packet);
  }

  _check_chunk_sending(chunk_id, chunk_no) {
    const chunk_state = this.send_chunks_in_progress.get(chunk_id);
    this.debug("file", "chunk id", chunk_id, "chunk_no", chunk_no, "found chunk_state", Boolean(chunk_state));
    if (!chunk_state) {
      return;
    }
    chunk_state[3] = 0; //timer has fired
    if (chunk_state[13] === chunk_no) {
      this.error("Error: chunked file transfer", chunk_id, "timed out");
      this.error(" on chunk", chunk_no);
      this.cancel_sending(chunk_id);
    }
  }

  cancel_sending(chunk_id) {
    const chunk_state = this.send_chunks_in_progress.get(chunk_id);
    this.debug("file", "cancel_sending", chunk_id, "chunk state found:", Boolean(chunk_state));
    if (!chunk_state) {
      return;
    }
    const timer = chunk_state[3];
    if (timer) {
      chunk_state[3] = 0;
      clearTimeout(timer);
    }
    this.send_chunks_in_progress.delete(chunk_id);
  }

  _process_ack_file_chunk(packet) {
    //the other end received our send-file or send-file-chunk,
    //send some more file data
    this.debug("file", "ack-file-chunk: ", packet);
    const chunk_id = Utilities.s(packet[1]);
    const state = packet[2];
    const error_message = packet[3];
    let chunk = packet[4];
    if (!state) {
      this.debug("file", "the remote end is cancelling the file transfer:");
      this.debug("file", " %s", Utilities.s(error_message));
      this.cancel_sending(chunk_id);
      return;
    }
    const chunk_state = this.send_chunks_in_progress.get(chunk_id);
    if (!chunk_state) {
      this.error("Error: cannot find the file transfer id '%r'", chunk_id);
      return;
    }
    if (chunk_state[4] !== chunk) {
      this.error("Error: chunk number mismatch", chunk_state, "vs", chunk);
      this.cancel_sending(chunk_id);
      return;
    }
    const start_time = chunk_state[0];
    const chunk_size = chunk_state[2];
    let timer = chunk_state[3];
    let data = chunk_state[1];
    if (!data) {
      //all sent!
      const elapsed = Date.now() - start_time;
      const bps = (8 * chunk * chunk_size) / elapsed;
      this.log(chunk, "chunks of", chunk_size, "bytes sent in", Math.round(elapsed), "ms", bps, "bps");
      this.cancel_sending(chunk_id);
      return;
    }
    if (chunk_size <= 0) {
      throw Exception(`invalid chunk size ${chunk_size}`);
    }
    //carve out another chunk:
    const cdata = data.subarray(0, chunk_size);
    data = data.subarray(chunk_size);
    chunk += 1;
    if (timer) {
      clearTimeout(timer);
    }
    timer = setTimeout(
      () => this._check_chunk_sending(chunk_id, chunk),
      CHUNK_TIMEOUT
    );
    this.send_chunks_in_progress.set(chunk_id, [start_time, data, chunk_size, timer, chunk]);
    this.send([PACKET_TYPES.send_file_chunk, chunk_id, chunk, cdata, data.length > 0]);
  }

  start_command(name, command, ignore) {
    const packet = [PACKET_TYPES.start_command, name, command, ignore];
    this.send(packet);
  }

  _process_open_url(packet) {
    const url = packet[1];
    if (!this.open_url) {
      this.cwarn("Warning: received a request to open URL", url);
      this.clog(" but opening of URLs is disabled");
      return;
    }
    this.clog("opening url:", url);
    const new_window = window.open(url, "_blank");
    if (!new_window || new_window.closed || typeof new_window.closed == "undefined") {
      //Popup blocked, display link in notification
      const summary = "Open URL";
      const body = `<a href="${url}" rel="noopener" target="_blank">${url}</a>`;
      const timeout = 10;
      window.doNotification("", 0, summary, body, timeout, null, null, null, null, null);
    }
  }
}

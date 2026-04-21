/*
 * This file is part of Xpra.
 * Copyright (C) 2016 Antoine Martin <antoine@xpra.org>
 * Licensed under MPL 2.0, see:
 * http://www.mozilla.org/MPL/2.0/
 *
 */

const DEFAULT_BOX_COLORS = {
  png: "yellow",
  h264: "blue",
  vp8: "green",
  rgb24: "orange",
  rgb32: "red",
  jpeg: "purple",
  webp: "pink",
  "png/P": "indigo",
  "png/L": "teal",
  h265: "khaki",
  vp9: "lavender",
  mpeg4: "black",
  scroll: "brown",
  mpeg1: "olive",
  avif: "cyan",
};

const MOVERESIZE_SIZE_TOPLEFT = 0;
const MOVERESIZE_SIZE_TOP = 1;
const MOVERESIZE_SIZE_TOPRIGHT = 2;
const MOVERESIZE_SIZE_RIGHT = 3;
const MOVERESIZE_SIZE_BOTTOMRIGHT = 4;
const MOVERESIZE_SIZE_BOTTOM = 5;
const MOVERESIZE_SIZE_BOTTOMLEFT = 6;
const MOVERESIZE_SIZE_LEFT = 7;
const MOVERESIZE_MOVE = 8;
const MOVERESIZE_SIZE_KEYBOARD = 9;
const MOVERESIZE_MOVE_KEYBOARD = 10;
const MOVERESIZE_CANCEL = 11;
const MOVERESIZE_DIRECTION_STRING = {
  0: "SIZE_TOPLEFT",
  1: "SIZE_TOP",
  2: "SIZE_TOPRIGHT",
  3: "SIZE_RIGHT",
  4: "SIZE_BOTTOMRIGHT",
  5: "SIZE_BOTTOM",
  6: "SIZE_BOTTOMLEFT",
  7: "SIZE_LEFT",
  8: "MOVE",
  9: "SIZE_KEYBOARD",
  10: "MOVE_KEYBOARD",
  11: "CANCEL",
};
const MOVERESIZE_DIRECTION_JS_NAME = {
  0: "nw",
  1: "n",
  2: "ne",
  3: "e",
  4: "se",
  5: "s",
  6: "sw",
  7: "w",
};

const PACKET_TYPES = {
  control: "control",
  ack_file_chunk: "ack-file-chunk",
  bell: "bell",
  buffer_refresh: "buffer-refresh",
  button_action: "button-action",
  challenge: "challenge",
  clipboard_request: "clipboard-request",
  clipboard_token: "clipboard-token",
  clipboard_contents_none: "clipboard-contents-none",
  clipboard_contents: "clipboard-contents",
  close: "close",
  close_window: "close-window",
  configure_override_redirect: "configure-override-redirect",
  configure_window: "configure-window",
  connection_data: "connection-data",
  cursor: "cursor",
  damage_sequence: "damage-sequence",
  desktop_size: "desktop_size",
  configure_display: "configure-display",
  disconnect: "disconnect",
  draw: "draw",
  encodings: "encodings",
  eos: "eos",
  error: "error",
  focus: "focus",
  hello: "hello",
  info_request: "info-request",
  info_response: "info-response",
  initiate_moveresize: "initiate-moveresize",
  key_action: "key-action",
  layout_changed: "layout-changed",
  keymap_changed: "keymap-changed",
  logging: "logging",
  lost_window: "lost-window",
  map_window: "map-window",
  new_override_redirect: "new-override-redirect",
  new_tray: "new-tray",
  new_window: "new-window",
  notification_action: "notification-action",
  notification_close: "notification-close",
  notify_close: "notify_close",
  notify_show: "notify_show",
  open: "open",
  open_url: "open-url",
  ping: "ping",
  ping_echo: "ping_echo",
  pointer_position: "pointer-position",
  printers: "printers",
  raise_window: "raise-window",
  resume: "resume",
  send_file: "send-file",
  send_file_chunk: "send-file-chunk",
  set_clipboard_enabled: "set-clipboard-enabled",
  setting_change: "setting-change",
  sound_control: "sound-control",
  sound_data: "sound-data",
  startup_complete: "startup-complete",
  start_command: "start-command",
  suspend: "suspend",
  unmap_window: "unmap-window",
  wheel_motion: "wheel-motion",
  window_icon: "window-icon",
  window_metadata: "window-metadata",
  window_move_resize: "window-move-resize",
  window_resized: "window-resized",
};

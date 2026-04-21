/*
 * Copyright (c) 2013 Antoine Martin <antoine@xpra.org>
 * Copyright (c) 2014 Joshua Higgins <josh@kxes.net>
 * Copyright (c) 2015 Spikes, Inc.
 * Licensed under MPL 2.0
 *
 * xpra window
 *
 * Based on shape.js but no longer requires it
 *
 * requires:
 *   jQueryUI
 */

const TASKBAR_HEIGHT = 0;

function dummy() {
  //this placeholder function does nothing
}

/**
 * This is the class representing a window we draw on the canvas.
 * It has a geometry, it may have borders and a top bar.
 * The contents of the window is an image, which gets updated
 * when we receive pixels from the server.
 */
class XpraWindow {
  constructor(
    client,
    wid,
    x,
    y,
    w,
    h,
    metadata,
    override_redirect,
    tray,
    client_properties,
    geometry_callback,
    mouse_move_callback,
    mouse_down_callback,
    mouse_up_callback,
    mouse_scroll_callback,
    set_focus_callback,
    window_closed_callback,
    scale
  ) {
    // use me in jquery callbacks as we lose 'this'
    this.client = client;

    //xpra specific attributes:
    this.wid = wid;
    //enclosing div in page DOM
    this.div = document.getElementById(wid);

    //these values represent the internal geometry
    //i.e. geometry as windows appear to the compositor
    this.x = x;
    this.y = y;
    this.w = w;
    this.h = h;
    // scaling for client display width override
    this.scale = scale;

    this.metadata = {};
    this.override_redirect = override_redirect;
    this.tray = tray;
    this.has_alpha = false;
    this.client_properties = client_properties;

    this.set_focus_cb = set_focus_callback || dummy;
    this.mouse_move_cb = mouse_move_callback || dummy;
    this.mouse_down_cb = mouse_down_callback || dummy;
    this.mouse_up_cb = mouse_up_callback || dummy;
    this.mouse_scroll_cb = mouse_scroll_callback || dummy;
    this.geometry_cb = geometry_callback || dummy;
    this.window_closed_cb = window_closed_callback || dummy;

    this.debug_categories = client.debug_categories;

    this.canvas = null;
    this.init_canvas();

    //window attributes:
    this.title = "";
    this.windowtype = [];
    this.fullscreen = false;
    this.saved_geometry = null;
    this.minimized = false;
    this.maximized = false;
    this.focused = false;
    this.decorations = true;    // whether the window should be decorated or not
    this.decorated = true;      // whether it actually is (fullscreen windows are not)
    this.resizable = false;
    this.stacking_layer = 0;

    // Icon cache
    this.icon = null;

    // get offsets
    this.leftoffset = 0;
    this.rightoffset = 0;
    this.topoffset = 0;
    this.bottomoffset = 0;

    // update metadata that is safe before window is drawn
    this.update_metadata(metadata, true);

    // create the decoration as part of the window, style is in CSS
    jQuery(this.div).addClass("window");
    for (const windowtype in this.windowtype) {
      jQuery(this.div).addClass(`window-${windowtype}`);
    }

    const fullscreen = (metadata["fullscreen"]) ?? false;

    if (this.client.server_is_desktop || this.client.server_is_shadow) {
      jQuery(this.div).addClass("desktop");
      this.resizable = false;
    } else if (this.tray) {
      jQuery(this.div).addClass("tray");
      this.resizable = false;
    } else if (this.override_redirect) {
      jQuery(this.div).addClass("override-redirect");
      this.resizable = false;
    } else if (!fullscreen && ((this.windowtype.length === 0) || this.has_windowtype(["NORMAL", "DIALOG", "UTILITY"]))) {
      this.resizable = true;
    }

    this.configure_border_class();
    this.add_headerbar();
    this.make_draggable()
    this.update_offsets()

    // stop propagation if we're over the window:
    jQuery(this.div).mousedown((e) => e.stopPropagation());
    //bug 2418: if we stop 'mouseup' propagation,
    //jQuery can't ungrab the window with Firefox
    // assign callback to focus window if header is clicked.
    jQuery(this.d_header).click((e) => {
      if (
          !this.minimized &&
          $(e.target).parents(".windowbuttons").length === 0
      ) {
        this.focus();
      }
    });

    // create the spinner overlay div
    jQuery(this.div).prepend(
      `<div id="spinner${wid}" class="spinneroverlay"><div class="spinnermiddle"><div class="spinner"></div></div></div>`
    );
    this.spinnerdiv = jQuery(`#spinner${wid}`);

    this.cursor_data = null;
    this.pointer_down = -1;
    this.pointer_last_x = 0;
    this.pointer_last_y = 0;

    // adapt to screen size if needed (ie: shadow / desktop windows):
    this.screen_resized();
    // set the CSS geometry
    this.updateCSSGeometry();
    // now read all metadata
    this.update_metadata(metadata);
  }

  log() {
    if (this.client) this.client.log.apply(this.client, arguments);
  }
  warn() {
    if (this.client) this.client.warn.apply(this.client, arguments);
  }
  error() {
    if (this.client) this.client.error.apply(this.client, arguments);
  }
  exc() {
    if (this.client) this.client.exc.apply(this.client, arguments);
  }
  debug() {
    if (this.client) this.client.debug.apply(this.client, arguments);
  }

  configure_border_class() {
    if (this.resizable || this.decorated) {
      jQuery(this.div).addClass("border");
    }
    else {
      jQuery(this.div).removeClass("border");
    }
  }

  update_offsets() {
    this.leftoffset = Number.parseInt(jQuery(this.div).css("border-left-width"), 10);
    this.rightoffset = Number.parseInt(jQuery(this.div).css("border-right-width"), 10);
    this.topoffset = Number.parseInt(jQuery(this.div).css("border-top-width"), 10)
    this.bottomoffset = Number.parseInt(jQuery(this.div).css("border-bottom-width"), 10);
    if (this.decorated) {
      this.topoffset = this.topoffset + Number.parseInt(jQuery(this.d_header).css("height"), 10);
    }
    this.debug("geometry", "decorated=", this.decorated, "offsets=", [this.leftoffset, this.topoffset, this.rightoffset, this.bottomoffset]);
  }


  add_headerbar() {
    const wid = this.wid;
    // add a title bar to this window if we need to
    // create header
    let head =
        `<div id="head${wid}" class="windowhead"> ` +
        `<span class="windowicon"><img alt="window icon" class="windowicon" id="windowicon${wid}" /></span> ` +
        `<span class="windowtitle" id="title${wid}">${this.title}</span> ` +
        `<span class="windowbuttons"> `;
    if (!jQuery(this.div).hasClass("modal")) {
      //modal windows cannot be minimized (see #204)
      head += `<span id="minimize${wid}"><img alt="minimize" src="icons/minimize.png" /></span>`;
    }
    head +=
        `<span id="maximize${wid}"><img alt="maximize" src="icons/maximize.png" /></span> ` +
        `<span id="close${wid}"><img alt="close" src="icons/close.png" /></span> ` +
        `</span></div>`;
    jQuery(this.div).prepend(head);

    jQuery(`#head${wid}`).click(() => {
      if (!this.minimized) {
        this.focus();
      }
    });
    this.d_header = `#head${wid}`;
    this.d_closebtn = `#close${wid}`;
    this.d_maximizebtn = `#maximize${wid}`;
    this.d_minimizebtn = `#minimize${wid}`;

    if (this.resizable) {
      this.make_resizable();
      jQuery(this.d_header).dblclick(() => this.toggle_maximized());
      jQuery(this.d_closebtn).click(() => this.window_closed_cb(this));
      jQuery(this.d_maximizebtn).click(() => this.toggle_maximized());
      jQuery(this.d_minimizebtn).click(() => this.toggle_minimized());
    } else {
      jQuery(this.d_maximizebtn).hide();
      jQuery(`#windowlistitemmax${wid}`).hide();
    }

    // we must set a sensible default early
    // so geometry calculations have the correct offset:
    if (!("decorations" in this.metadata)) {
      let decorated = true;
      if (this.override_redirect) {
        decorated = false;
      }
      else {
        decorated = !this.has_windowtype(["DROPDOWN", "TOOLTIP", "POPUP_MENU", "MENU", "COMBO"]);
      }
      this._set_decorated(decorated);
      // console.log("decorated=", decorated, "for windowtype=", this.windowtype);
    }
  }

  has_windowtype(windowtypes) {
    const windowtypes_set = new Set(windowtypes);
    return this.windowtype.some(element => windowtypes_set.has(element));
  }


  make_draggable() {
    if (this.scale !== 1) {
      jQuery(this.div).draggable({
        transform: true
      });
    }
    jQuery(this.div).draggable({
      cancel: "canvas"
    });
    jQuery(this.div).on("dragstart", (event_) => {
      this.client.release_buttons(event_, this);
      this.focus();
      this.client.mouse_grabbed = true;
    });
    jQuery(this.div).on("dragstop", (event_, ui) => {
      this.client.mouse_grabbed = false;
      this.handle_moved(ui);
    });
  }

  make_resizable() {
    // Use transform if scaled
    // This disables helper highlight, so we
    // move the resizable borders in transform plugin
    if (this.scale !== 1) {
      jQuery(this.div).resizable({
        transform: true
      });
    }
    // attach resize handles
    jQuery(this.div).resizable({
      containment: "parent",
      helper: "ui-resizable-helper",
      handles: "n, e, s, w, ne, se, sw, nw",
    });
    jQuery(this.div).on("resizestart", (evt) => {
      this.client.do_window_mouse_click(evt, this, false);
      this.client.mouse_grabbed = true;
    });
    jQuery(this.div).on("resizestop", (evt, ui) => {
      this.handle_resized(ui);
      this.focus();
      this.client.mouse_grabbed = false;
      //workaround for the window going blank,
      //just force a refresh:
      setTimeout(() => this.client.request_refresh(this.wid), 200);
      setTimeout(() => this.client.request_refresh(this.wid), 500);
    });
  }

  init_canvas() {
    this.canvas = null;
    jQuery(this.div).find("canvas").remove();
    const canvas = document.createElement("canvas");
    if (this.client.try_gpu) {
      $(canvas).addClass("gpu-trigger");
    }
    // set initial sizes
    canvas.width = this.w;
    canvas.height = this.h;
    this.canvas = canvas;
    this.div.append(canvas);
    if (this.client.offscreen_api && this.client.decode_worker) {
      // Transfer canvas control.
      this.transfer_canvas(canvas);
    } else {
      //we're going to paint from this class:
      this.canvas_ctx = this.canvas.getContext("2d");
      this.canvas_ctx.imageSmoothingEnabled = false;

      this.init_offscreen_canvas();

      this.draw_canvas = this.offscreen_canvas;
      this.paint_queue = [];
      this.paint_pending = 0;
    }
    this.register_canvas_mouse_events(this.canvas);
    this.register_canvas_pointer_events(this.canvas);
  }

  transfer_canvas(canvas) {
    const offscreen_handle = canvas.transferControlToOffscreen();
    this.client.decode_worker.postMessage({
        cmd: "canvas",
        wid: this.wid,
        canvas: offscreen_handle,
        debug: this.debug_categories.includes("draw"),
      },
      [offscreen_handle]
    );
  }

  init_offscreen_canvas() {
    this.offscreen_canvas = document.createElement("canvas");
    this.offscreen_canvas.width = this.w;
    this.offscreen_canvas.height = this.h;
    this.offscreen_canvas_ctx = this.offscreen_canvas.getContext("2d");
    this.offscreen_canvas_ctx.imageSmoothingEnabled = false;
  }

  swap_buffers() {
    //the up to date canvas is what we'll draw on screen:
    this.debug("draw", "swap_buffers");
    this.draw_canvas = this.offscreen_canvas;
    this.init_offscreen_canvas();
    this.offscreen_canvas_ctx.drawImage(this.draw_canvas, 0, 0);
  }

  register_canvas_mouse_events(canvas) {
    // Hook up the events we want to receive:
    jQuery(canvas).mousedown((e) => {
      return this.mouse_down_cb(e, this);
    });
    jQuery(canvas).mouseup((e) => {
      return this.mouse_up_cb(e, this);
    });
    jQuery(canvas).mousemove((e) => {
      return this.mouse_move_cb(e, this);
    });
  }

  register_canvas_pointer_events(canvas) {
    if (!window.PointerEvent) {
      return;
    }
    canvas.addEventListener("pointerdown", (event_) => {
      this.debug("mouse", "pointerdown:", event_);
      if (event_.pointerType === "touch") {
        this.pointer_down = event_.pointerId;
        this.pointer_last_x = event_.offsetX;
        this.pointer_last_y = event_.offsetY;
      }
    });

    canvas.addEventListener("mousemove", (event_) => {
      this.debug("mouse", "mousemove:", event_);
      if (this.pointer_down === event_.pointerId) {
        const dx = event_.offsetX - this.pointer_last_x;
        const dy = event_.offsetY - this.pointer_last_y;
        this.pointer_last_x = event_.offsetX;
        this.pointer_last_y = event_.offsetY;
        const mult = 20 * (window.devicePixelRatio || 1);
        event_.wheelDeltaX = Math.round(dx * mult);
        event_.wheelDeltaY = Math.round(dy * mult);
        return this.mouse_scroll_cb(event_, this);
      }
    });
    canvas.addEventListener("pointerup", (event_) => {
      this.debug("mouse", "pointerup:", event_);
      this.pointer_down = -1;
    });
    canvas.addEventListener("pointercancel", (event_) => {
      this.debug("mouse", "pointercancel:", event_);
      this.pointer_down = -1;
    });
    canvas.addEventListener("pointerout", (event_) => {
      this.debug("mouse", "pointerout:", event_);
    });
    //wheel events on a window:
    const me = this;

    function on_mousescroll(e) {
      me.mouse_scroll_cb(e, me);
      e.stopPropagation();
      return e.preventDefault();
    }
    if (Utilities.isEventSupported("wheel")) {
      canvas.addEventListener("wheel", on_mousescroll, false);
    }
  }

  set_spinner(state) {
    if (state) {
      this.spinnerdiv.hide();
    } else {
      this.spinnerdiv.css("display", "table");
    }
  }

  ensure_visible() {
    if (this.client.server_is_desktop || this.client.server_is_shadow) {
      //those windows should usually be centered on screen,
      //moving them would mess that up
      return true;
    }
    if (this.override_redirect) {
      //OR windows cannot be moved server-side
      return true;
    }
    const oldx = this.x;
    const oldy = this.y;
    // for now make sure we don't out of top left
    // this will be much smarter!
    const min_w_visible = Math.min(80, this.w);
    const min_h_visible = Math.min(80, this.h);
    const desktop_size = this.client._get_desktop_size();
    const ww = desktop_size[0];
    const wh = desktop_size[1];
    this.debug("geometry", "ensure_visible() min_w_visible=", min_w_visible, "min_h_visible=", min_h_visible, "desktop_size=", desktop_size);
    if (oldx < this.leftoffset && oldx + this.w <= min_w_visible) {
      this.x = min_w_visible - this.w + this.leftoffset;
    } else if (oldx >= ww - min_w_visible) {
      this.x = Math.min(oldx, ww - min_w_visible);
    }
    if (oldy <= this.topoffset && oldy <= min_h_visible) {
      this.y = this.topoffset;
    } else if (oldy >= wh - min_h_visible) {
      this.y = Math.min(oldy, wh - min_h_visible);
    }
    this.debug("geometry", "ensure_visible() oldx=", oldx, "oldy=", oldy, "x=", this.x, "y=", this.y);
    if (oldx !== this.x || oldy !== this.y) {
      this.updateCSSGeometry();
      return false;
    }
    return true;
  }

  updateCanvasGeometry() {
    if (this.client.offscreen_api && this.client.decode_worker) {
      this.client.decode_worker.postMessage({
        cmd: "canvas-geo",
        wid: this.wid,
        w: this.w,
        h: this.h,
      });
      return;
    }
    // set size of both canvas if needed
    if (this.canvas.width !== this.w) {
      this.canvas.width = this.w;
    }
    if (this.canvas.height !== this.h) {
      this.canvas.height = this.h;
    }
    if (this.offscreen_canvas.width !== this.w) {
      this.offscreen_canvas.width = this.w;
    }
    if (this.offscreen_canvas.height !== this.h) {
      this.offscreen_canvas.height = this.h;
    }
  }

  updateCSSGeometry() {
    // set size of canvas
    this.updateCanvasGeometry();
    if (this.client.server_is_desktop || this.client.server_is_shadow) {
      if (this.client.server_resize_exact) {
        jQuery(this.div).css("top", 0);
        return;
      }
    }
    // work out outer size
    this.outerH = this.h + this.topoffset + this.bottomoffset;
    this.outerW = this.w + this.leftoffset + this.rightoffset;
    // set width and height
    jQuery(this.div).css("width", this.outerW);
    jQuery(this.div).css("height", this.outerH);
    // set CSS attributes to outerX and outerY
    this.outerX = this.x - this.leftoffset;
    this.outerY = this.y - this.topoffset;
    jQuery(this.div).css("left", this.outerX);
    jQuery(this.div).css("top", this.outerY);
    this.debug("geometry", "updateCSSGeometry() left=", this.outerX, ", top=", this.outerY, ", width=", this.outerW, ", height=", this.outerH);
  }

  focus() {
    this.set_focus_cb(this);
  }

  updateFocus() {
    if (this.focused) {
      // set focused style to div
      jQuery(this.div).addClass("windowinfocus");

      // Update window title
      if (this.client.session_name) {
        jQuery("title").text(client.session_name);
      }
      else {
        jQuery("title").text(
          `${location.pathname.replaceAll("/", "")}: ${this.title}`
        );
      }

      // Update the icon
      if (this.icon !== null) {
        const source = this.update_icon(this.icon.width, this.icon.height, this.icon.encoding, this.icon.img_data);
        jQuery("#favicon").attr("href", source);
      } else {
        jQuery("#favicon").attr("href", "favicon.png");
      }
    } else {
      // set not in focus style
      jQuery(this.div).removeClass("windowinfocus");
    }
  }

  suspend() {
    //perhaps we should suspend updates?
  }

  resume() {
    this.init_canvas();
  }

  /**
   * toString allows us to identify windows by their unique window id.
   */
  toString() {
    return `Window(${this.wid})`;
  }

  update_zindex() {
    let z = 5000 + this.stacking_layer;
    if (this.tray) {
      z = 0;
    } else if (this.override_redirect || this.client.server_is_desktop || this.client.server_is_shadow) {
      z = 30_000;
    } else if (this.has_windowtype(["DROPDOWN", "TOOLTIP", "POPUP_MENU", "MENU", "COMBO"]))
    {
      z = 20_000;
    } else if (this.has_windowtype(["UTILITY", "DIALOG"])) {
      z = 15_000;
    }
    const above = this.metadata["above"];
    if (above) {
      z += 5000;
    } else {
      const below = this.metadata["below"];
      if (below) {
        z -= 5000;
      }
    }
    if (this.focused) {
      z += 2500;
    }
    jQuery(this.div).css("z-index", z);
  }

  /**
   * Update our metadata cache with new key-values,
   * then call set_metadata with these new key-values.
   */
  update_metadata(metadata, safe) {
    //update our metadata cache with new key-values:
    this.debug("main", "update_metadata(", metadata, ")");
    for (const attrname in metadata) {
      this.metadata[attrname] = metadata[attrname];
    }
    if (safe) {
      this.set_metadata_safe(metadata);
    } else {
      this.set_metadata(metadata);
    }
    this.update_zindex();
  }

  /**
   * Apply only metadata settings that are safe before window is drawn
   */
  set_metadata_safe(metadata) {
    if ("title" in metadata) {
      let title = Utilities.s(metadata["title"]);
      if (this.title !== title) {
        this.title = title;
        this.log("title=", this.title);
        jQuery(`#title${this.wid}`).html(this.title);
        const trimmedTitle = Utilities.trimString(this.title, 30);
        jQuery(`#windowlistitemtitle${this.wid}`).text(trimmedTitle);
      }
    }
    if ("has-alpha" in metadata) {
      this.has_alpha = Boolean(metadata["has-alpha"]);
    }
    if ("window-type" in metadata) {
      this.windowtype = metadata["window-type"];
    }
    if ("opacity" in metadata) {
      let opacity = metadata["opacity"];
      opacity = opacity < 0 ? 1 : opacity / 0x1_00_00_00_00;
      jQuery(this.div).css("opacity", `${opacity}`);
    }
    if ("iconic" in metadata) {
      this.set_minimized(Boolean(metadata["iconic"]));
    }

    //if the attribute is set, add the corresponding css class:
    const attributes = ["modal", "above", "below"];
    for (const attribute of attributes) {
      if (attribute in metadata) {
        const value = metadata[attribute];
        if (value) {
          jQuery(this.div).addClass(attribute);
        } else {
          jQuery(this.div).removeClass(attribute);
        }
      }
    }
    if (this.resizable && "size-constraints" in metadata) {
      this.apply_size_constraints();
    }
    if ("class-instance" in metadata) {
      const wm_class = metadata["class-instance"];
      const classes = jQuery(this.div).prop("classList");
      if (classes) {
        //remove any existing "wmclass-" classes not in the new wm_class list:
        for (const class_ of classes) {
          const tclass = `${class_}`;
          if (tclass.indexOf("wmclass-") === 0 && wm_class && !wm_class.includes(tclass)) {
            jQuery(this.div).removeClass(tclass);
          }
        }
      }
      if (wm_class) {
        //add new wm-class:
        for (const element of wm_class) {
          const tclass = Utilities.s(element).replace(/[^\dA-Za-z]/g, "");
          if (tclass && !jQuery(this.div).hasClass(tclass)) {
            jQuery(this.div).addClass(`wmclass-${tclass}`);
          }
        }
      }
    }
  }

  apply_size_constraints() {
    if (!this.resizable) {
      return;
    }
    if (this.maximized) {
      jQuery(this.div).draggable("disable");
    } else {
      jQuery(this.div).draggable("enable");
    }
    let hdec = 0;
    const wdec = 0;
    if (this.decorated) {
      //adjust for header
      hdec = jQuery(`#head${this.wid}`).outerHeight(true);
    }
    let min_size = null;
    let max_size = null;
    const size_constraints = this.metadata["size-constraints"];
    if (size_constraints) {
      min_size = size_constraints["minimum-size"];
      max_size = size_constraints["maximum-size"];
    }
    let minw = 0;
    let minh = 0;
    if (min_size) {
      minw = min_size[0] + wdec;
      minh = min_size[1] + hdec;
    }
    let maxw = null;
    let maxh = null;
    if (max_size) {
      maxw = max_size[0] + wdec;
      maxh = max_size[1] + hdec;
    }
    if (minw > 0 && minw === maxw && minh > 0 && minh === maxh) {
      jQuery(this.d_maximizebtn).hide();
      jQuery(`#windowlistitemmax${this.wid}`).hide();
      jQuery(this.div).resizable("disable");
    } else {
      jQuery(this.d_maximizebtn).show();
      if (!this.maximized) {
        jQuery(this.div).resizable("enable");
      } else {
        jQuery(this.div).resizable("disable");
      }
    }
    if (!this.maximized) {
      if (minw) {
        jQuery(this.div).resizable("option", "minWidth", minw);
      }
      if (minh) {
        jQuery(this.div).resizable("option", "minHeight", minh);
      }
      if (maxw) {
        jQuery(this.div).resizable("option", "maxWidth", maxw);
      }
      if (maxh) {
        jQuery(this.div).resizable("option", "maxHeight", maxh);
      }
    }
    //TODO: aspectRatio, grid
  }

  /**
   * Apply new metadata settings.
   */
  set_metadata(metadata) {
    this.set_metadata_safe(metadata);
    if ("fullscreen" in metadata) {
      this.set_fullscreen(Boolean(metadata["fullscreen"]));
    }
    if ("maximized" in metadata) {
      this.set_maximized(Boolean(metadata["maximized"]));
    }
    if ("decorations" in metadata) {
      this.decorations = Boolean(metadata["decorations"]);
      this._set_decorated(this.decorations);
      this.updateCSSGeometry();
      this.handle_resized();
      this.apply_size_constraints();
    }
  }

  /**
   * Save the window geometry so we can restore it later
   * (ie: when un-maximizing or un-fullscreening)
   */
  save_geometry() {
    this.saved_geometry = {
      x: this.x,
      y: this.y,
      w: this.w,
      h: this.h,
    };
    this.debug("geometry", "save_geometry() saved-geometry=", this.saved_geometry);
  }
  /**
   * Restores the saved geometry (if it exists).
   */
  restore_geometry() {
    if (!this.saved_geometry) {
      return;
    }
    this.x = this.saved_geometry["x"];
    this.y = this.saved_geometry["y"];
    this.w = this.saved_geometry["w"];
    this.h = this.saved_geometry["h"];
    this.debug("geometry", "restore_geometry() saved-geometry=", this.saved_geometry);
    // delete saved geometry
    this.saved_geometry = null;
    // then call local resized callback
    this.handle_resized();
    this.focus();
  }

  /**
   * Maximize / unmaximizes the window.
   */
  set_maximized(maximized) {
    if (jQuery(this.div).is(":hidden")) {
      jQuery(this.div).show();
    }

    if (this.maximized === maximized) {
      return;
    }
    this.max_save_restore(maximized);
    this.maximized = maximized;
    this.handle_resized();
    this.focus();
    // this will take care of disabling the "draggable" code:
    this.apply_size_constraints();
  }

  /**
   * Toggle maximized state
   */
  toggle_maximized() {
    this.set_maximized(!this.maximized);
  }

  /**
   * Minimizes / unminimizes the window.
   */
  set_minimized(minimized) {
    if (this.minimized === minimized) {
      return;
    }
    this.minimized = minimized;
    if (minimized) {
      jQuery(this.div).hide(200);
    } else {
      jQuery(this.div).show(200);
    }
  }

  /**
   * Toggle minimized state
   */
  toggle_minimized() {
    //get the geometry before modifying the window:
    const geom = this.get_internal_geometry();
    this.set_minimized(!this.minimized);
    if (this.minimized) {
      this.client.send([PACKET_TYPES.unmap_window, this.wid, true]);
      this.stacking_layer = 0;
      if (this.client.focused_wid === this.wid) {
        this.client.auto_focus();
      }
    } else {
      this.client.send([PACKET_TYPES.map_window, this.wid, geom.x, geom.y, geom.w, geom.h, this.client_properties]);
      //ugly force focus switch:
      this.client.focused_wid = 0;
      this.client.set_focus(this);
    }
  }

  /**
   * Fullscreen / unfullscreen the window.
   */
  set_fullscreen(fullscreen) {
    //the browser itself:
    //we can't bring attention to the fullscreen widget,
    //ie: $("#fullscreen").fadeIn(100).fadeOut(100).fadeIn(100).fadeOut(100).fadeIn(100);
    //because the window is about to cover the top bar...
    //so just fullscreen the window:
    if (this.fullscreen === fullscreen) {
      return;
    }
    if (this.resizable) {
      if (fullscreen) {
        this._set_decorated(false);
      } else {
        this._set_decorated(this.decorations);
      }
    }
    this.max_save_restore(fullscreen);
    this.fullscreen = fullscreen;
    this.updateCSSGeometry();
    this.handle_resized();
    this.focus();
  }

  _set_decorated(decorated) {
    this.decorated = decorated;
    const head = document.getElementById("head"+this.wid);
    if (decorated) {
      head.style.display = 'block';
      jQuery(this.div).removeClass("undecorated");
      jQuery(this.div).addClass("window");
    } else {
      head.style.display = 'none';
      jQuery(this.div).removeClass("window");
      jQuery(this.div).addClass("undecorated");
    }
    this.update_offsets();
  }

  /**
   * Either:
   * - save the geometry and use all the space
   * - or restore the geometry
   */
  max_save_restore(use_all_space) {
    if (use_all_space) {
      this.save_geometry();
      this.fill_screen();
    } else {
      this.restore_geometry();
    }
  }

  /**
   * Use up all the available screen space
   */
  fill_screen() {
    // should be as simple as this
    // in future we may have a taskbar for minimized windows
    // which should be subtracted from screen size
    const screen_size = this.client._get_desktop_size();
    this.x = this.leftoffset;
    this.y = this.topoffset;
    this.w = screen_size[0] - this.leftoffset - this.rightoffset;
    this.h = screen_size[1] - this.topoffset - this.bottomoffset - TASKBAR_HEIGHT;
    this.debug("geometry", "fill_screen() ", this.x, this.y, this.w, this.h);
  }

  /**
   * We have resized the window, so we need to:
   * - work out new position of internal canvas
   * - update external CSS position
   * - resize the backing image
   * - fire the geometry_cb
   */
  handle_resized(e) {
    // this function is called on local resize only,
    // remote resize will call this.resize()
    // need to update the internal geometry
    this.debug("geometry", "handle_resized(", e, ")");
    if (e) {
      this.x = this.x + Math.round(e.position.left - e.originalPosition.left);
      this.y = this.y + Math.round(e.position.top - e.originalPosition.top);
      this.w = Math.round(e.size.width) - this.leftoffset - this.rightoffset;
      this.h = Math.round(e.size.height) - this.topoffset - this.bottomoffset;
    }
    // then update CSS and redraw backing
    this.updateCSSGeometry();
    // send geometry callback
    this.geometry_cb(this);
  }

  /**
   * Like handle_resized, except we should
   * store internal geometry, external is always in CSS left and top
   */
  handle_moved(e) {
    const left = Math.round(e.position.left);
    const top = Math.round(e.position.top);
    this.debug("geometry", "handle_moved(", e, ") left=", left, ", top=", top);
    // add on padding to the event position so that
    // it reflects the internal geometry of the canvas
    this.x = left + this.leftoffset;
    this.y = top + this.topoffset;
    // make sure we are visible after move
    this.ensure_visible();
    // tell remote we have moved window
    this.geometry_cb(this);
  }

  /**
   * The "screen" has been resized, we may need to resize our window to match
   * if it is fullscreen or maximized.
   */
  screen_resized() {
    this.debug("geometry", "screen_resized() server_is_desktop=", this.client.server_is_desktop,
      ", server_is_shadow=", this.client.server_is_shadow);
    if (this.client.server_is_desktop) {
      this.match_screen_size();
    }
    if (this.client.server_is_shadow) {
      //note: when this window is created,
      // it may not have been added to the client's list yet
      const ids = Object.keys(this.client.id_to_window);
      if (ids.length === 0 || ids[0] === this.wid) {
        //single window, recenter it:
        this.recenter();
      }
    }
    if (this.fullscreen || this.maximized) {
      this.fill_screen();
      this.handle_resized();
    }
    if (!this.ensure_visible()) {
      this.geometry_cb(this);
    }
  }

  recenter(force_update_geometry) {
    let x = this.x;
    let y = this.y;
    this.debug("geometry", "recenter() x=", x, ", y=", y, ", desktop size: ", this.client.desktop_width, this.client.desktop_height);
    x = Math.round((this.client.desktop_width - this.w) / 2);
    y = Math.round((this.client.desktop_height - this.h) / 2);
    if (this.x !== x || this.y !== y || force_update_geometry) {
      this.debug("geometry", "window re-centered to:", x, y);
      this.x = x;
      this.y = y;
      this.updateCSSGeometry();
      this.geometry_cb(this);
    } else {
      this.debug("geometry", "recenter() unchanged at ", x, y);
    }
    if (this.x < 0 || this.y < 0) {
      this.warn("window does not fit in canvas, offsets: ", x, y);
    }
  }

  match_screen_size() {
    const maxw = this.client.desktop_width;
    const maxh = this.client.desktop_height;
    let neww = 0;
    let newh = 0;
    if (this.client.server_resize_exact) {
      neww = maxw;
      newh = maxh;
      this.log("resizing to exact size:", neww, newh);
    } else {
      if (this.client.server_screen_sizes.length === 0) {
        this.recenter();
        return;
      }
      //try to find the best screen size to use,
      //cannot be larger than the browser area
      let best = 0;
      let w = 0;
      let h = 0;
      const screen_sizes = this.client.server_screen_sizes;
      for (const screen_size of screen_sizes) {
        w = screen_size[0];
        h = screen_size[1];
        if (w <= maxw && h <= maxh && w * h > best) {
          best = w * h;
          neww = w;
          newh = h;
        }
      }
      if (neww === 0 && newh === 0) {
        //not found, try to find the smallest one:
        best = 0;
        for (const screen_size of screen_sizes) {
          w = screen_size[0];
          h = screen_size[1];
          if (best === 0 || w * h < best) {
            best = w * h;
            neww = w;
            newh = h;
          }
        }
      }
      this.log("best screen size:", neww, newh);
    }
    this.w = neww;
    this.h = newh;
    this.recenter(true);
  }

  /**
   * Things ported from original shape
   */

  move_resize(x, y, w, h) {
    this.debug("geometry", "move_resize(", x, y, w, h, ")");
    // only do it if actually changed!
    if (this.w !== w || this.h !== h || this.x !== x || this.y !== y) {
      this.w = w;
      this.h = h;
      this.x = x;
      this.y = y;
      if (!this.ensure_visible()) {
        // we had to move the window so that it was visible
        // is this the right thing to do?
        this.geometry_cb(this);
      } else {
        this.updateCSSGeometry();
      }
    }
  }

  move(x, y) {
    this.debug("geometry", "move(", x, y, ")");
    this.move_resize(x, y, this.w, this.h);
  }

  resize(w, h) {
    this.debug("geometry", "resize(", w, h, ")");
    this.move_resize(this.x, this.y, w, h);
  }

  initiate_moveresize(mousedown_event, x_root, y_root, direction, button, source_indication) {
    const dir_str = MOVERESIZE_DIRECTION_STRING[direction];
    this.log("initiate_moveresize", dir_str, [x_root, y_root, direction, button, source_indication]);
    if (direction === MOVERESIZE_MOVE && mousedown_event) {
      const e = mousedown_event;
      e.type = "mousedown.draggable";
      e.target = this.div[0];
      jQuery(this.div).trigger(e);
    } else if (direction === MOVERESIZE_CANCEL) {
      jQuery(this.div).draggable("disable");
      jQuery(this.div).draggable("enable");
    } else if (direction in MOVERESIZE_DIRECTION_JS_NAME) {
      const js_dir = MOVERESIZE_DIRECTION_JS_NAME[direction];
      const resize_widget = jQuery(this.div)
        .find(`.ui-resizable-handle.ui-resizable-${js_dir}`)
        .first();
      if (resize_widget) {
        const pageX = resize_widget.offset().left;
        const pageY = resize_widget.offset().top;
        resize_widget.trigger("mouseover");
        resize_widget.trigger({
          type: "mousedown",
          which: 1,
          pageX,
          pageY,
        });
      }
    }
  }

  /**
   * Returns the geometry of the window backing image,
   * the inner window geometry (without any borders or top bar).
   */
  get_internal_geometry() {
    /* we store the internal geometry only
     * and work out external geometry on the fly whilst
     * updating CSS
     */
    return {
      x: this.x,
      y: this.y,
      w: this.w,
      h: this.h,
    };
  }

  update_icon(width, height, encoding, img_data) {
    // Cache the icon.
    this.icon = {
      width,
      height,
      encoding,
      img_data,
    };

    let source = "favicon.png";
    if (encoding === "png") {
      //move title to the right:
      $(`#title${this.wid}`).css("left", 32);
      if (typeof img_data === "string") {
        const uint = new Uint8Array(img_data.length);
        for (let index = 0; index < img_data.length; ++index) {
          uint[index] = img_data.charCodeAt(index);
        }
        img_data = uint;
      }
      source = this.construct_base64_image_url(encoding, img_data);
    }
    jQuery(`#windowicon${this.wid}`).attr("src", source);
    jQuery(`#windowlistitemicon${this.wid}`).attr("src", source);
    return source;
  }

  reset_cursor() {
    jQuery(`#${this.wid}`).css("cursor", "default");
    this.cursor_data = null;
  }

  set_cursor(encoding, w, h, xhot, yhot, img_data) {
    if (encoding !== "png") {
      this.warn("received an invalid cursor encoding:", encoding);
      return;
    }
    const window_element = jQuery(`#${this.wid}`);
    const cursor_url = this.construct_base64_image_url(encoding, img_data);
    const me = this;

    function set_cursor_url(url, x, y, w, h) {
      const url_string = `url('${url}')`;
      window_element.css("cursor", `${url_string}, default`);
      //CSS3 with hotspot:
      window_element.css("cursor", `${url_string} ${x} ${y}, auto`);
      me.cursor_data = [url, x, y, w, h];
    }
    let zoom = detectZoom.zoom();
    //prefer fractional zoom values if possible:
    if (Math.round(zoom * 4) === 2 * Math.round(zoom * 2)) {
      zoom = Math.round(zoom * 2) / 2;
    }
    if (zoom !== 1 && !Utilities.isMacOS()) {
      //scale it:
      this.debug("geometry", "scaling cursor by zoom factor:", zoom);
      const temporary_img = new Image();
      temporary_img.addEventListener("load", () => {
        const canvas = document.createElement("canvas");
        const context = canvas.getContext("2d");
        context.imageSmoothingEnabled = false;
        canvas.width = Math.round(w * window.devicePixelRatio);
        canvas.height = Math.round(h * window.devicePixelRatio);
        context.drawImage(temporary_img, 0, 0, canvas.width, canvas.height);
        const scaled_cursor_url = canvas.toDataURL();
        set_cursor_url(
          scaled_cursor_url,
          Math.round(xhot * window.devicePixelRatio),
          Math.round(yhot * window.devicePixelRatio),
          Math.round(canvas.width),
          Math.round(canvas.height),
        );
      });
      temporary_img.src = cursor_url;
    } else {
      set_cursor_url(cursor_url, xhot, yhot, w, h);
    }
  }

  eos() {
    //we don't handle video streams in this class,
    //so this should never be called
  }

  /**
   * This function draws the contents of the off-screen canvas to the visible
   * canvas. However the drawing is requested by requestAnimationFrame which allows
   * the browser to group screen redraws together, and automatically adjusts the
   * framerate e.g if the browser window/tab is not visible.
   */
  draw() {
    //pass the 'buffer' canvas directly to visible canvas context
    if (this.has_alpha || this.tray) {
      this.canvas_ctx.clearRect(0, 0, this.draw_canvas.width, this.draw_canvas.height);
    }
    this.canvas_ctx.drawImage(this.draw_canvas, 0, 0);
  }

  /**
   * Updates the window image with new pixel data
   * we have received from the server.
   * The image is painted into off-screen canvas.
   */
  paint() {
    if (this.client.decode_worker) {
      //no need to synchronize paint packets here
      //the decode worker ensures that we get the packets
      //in the correct order, ready to update the canvas
      Reflect.apply(this.do_paint, this, arguments);
      return;
    }
    //process all paint request in order using the paint_queue:
    const item = Array.prototype.slice.call(arguments);
    this.paint_queue.push(item);
    this.may_paint_now();
  }

  /**
   * Pick items from the paint_queue
   * if we're not already in the process of painting something.
   */
  may_paint_now() {
    this.debug("draw", "may_paint_now() paint pending=", this.paint_pending,
      ", paint queue length=", this.paint_queue.length);
    let now = performance.now();
    while (
      (this.paint_pending === 0 || now - this.paint_pending >= 2000) &&
      this.paint_queue.length > 0
    ) {
      this.paint_pending = now;
      const item = this.paint_queue.shift();
      this.do_paint.apply(this, item);
      now = performance.now();
    }
  }

  paint_box(color, px, py, pw, ph) {
    this.offscreen_canvas_ctx.strokeStyle = color;
    this.offscreen_canvas_ctx.lineWidth = 2;
    this.offscreen_canvas_ctx.strokeRect(px, py, pw, ph);
  }

  do_paint(packet, decode_callback) {
    const me = this;

    const x = packet[2];
    const y = packet[3];
    const width = packet[4];
    const height = packet[5];
    const img_data = packet[7];
    const options = packet[10] || {};
    let coding = Utilities.s(packet[6]);
    let enc_width = width;
    let enc_height = height;
    const scaled_size = options["scaled_size"];
    if (scaled_size) {
      enc_width = scaled_size[0];
      enc_height = scaled_size[1];
    }
    const bitmap = coding.startsWith("bitmap:");
    if (bitmap) {
      coding = coding.split(":")[1];
      this.debug("draw", coding, img_data, " at ", `${x},${y}`, ") focused=", this.focused);
    } else {
      this.debug("draw", "do_paint(", img_data.length, " bytes of", coding, " data ", width, "x", height,
        " at ", x, ",", y, ") focused=", this.focused);
    }

    function painted(skip_box) {
      me.paint_pending = 0;
      if (!skip_box && me.debug_categories.includes("draw")) {
        const color = DEFAULT_BOX_COLORS[coding] || "white";
        me.paint_box(color, x, y, width, height);
      }
      decode_callback();
    }

    function paint_error(e) {
      me.error("error painting", coding, e);
      me.paint_pending = 0;
      decode_callback(`${e}`);
    }

    function paint_bitmap() {
      //the decode worker is giving us a Bitmap object ready to use:
      me.offscreen_canvas_ctx.clearRect(x, y, img_data.width, img_data.height);
      me.offscreen_canvas_ctx.drawImage(img_data, x, y);
      painted();
      //this isn't really needed since we don't use the paint_queue at all
      //when decoding in the worker (bitmaps can only come from the decode worker)
      me.may_paint_now();
    }

    try {
      if (coding === "void") {
        painted(true);
        this.may_paint_now();
      } else if (coding === "rgb32" || coding === "rgb24") {
        if (bitmap) {
          paint_bitmap();
          return;
        }
        const rgb_data = decode_rgb(packet);
        const img = this.offscreen_canvas_ctx.createImageData(enc_width, enc_height);
        img.data.set(rgb_data);
        this.offscreen_canvas_ctx.putImageData(img, x, y, 0, 0, width, height);
        painted();
        this.may_paint_now();
      } else if (coding === "jpeg" || coding.startsWith("png") || coding === "webp") {
        if (bitmap) {
          paint_bitmap();
          return;
        }
        const image = new Image();
        image.addEventListener("load", () => {
          if (image.width === 0 || image.height === 0) {
            paint_error(`invalid image size: ${image.width}x${image.height}`);
          } else {
            this.offscreen_canvas_ctx.clearRect(x, y, width, height);
            this.offscreen_canvas_ctx.drawImage(image, x, y, width, height);
            painted();
          }
          this.may_paint_now();
        });
        image.onerror = () => {
          paint_error(`failed to load ${coding} into image tag`);
          this.may_paint_now();
        };
        const paint_coding = coding.split("/")[0]; //ie: "png/P" -> "png"
        image.src = this.construct_base64_image_url(paint_coding, img_data);
      } else if (coding === "h264") {
        paint_error("h264 decoding is only supported via the decode workers");
        this.may_paint_now();
      } else if (coding === "scroll") {
        // newer servers use options,
        // older ones overload the image data:
        const scrolls = options["scroll"] || img_data;
        for (let index = 0, stop = scrolls.length; index < stop; ++index) {
          const scroll_data = scrolls[index];
          this.debug("draw", "scroll", index, ":", scroll_data);
          const sx = scroll_data[0];
          const sy = scroll_data[1];
          const sw = scroll_data[2];
          const sh = scroll_data[3];
          const xdelta = scroll_data[4];
          const ydelta = scroll_data[5];
          this.offscreen_canvas_ctx.drawImage(
            this.draw_canvas,
            sx, sy, sw, sh,
            sx + xdelta, sy + ydelta, sw, sh
          );
          if (this.debug_categories.includes("draw")) {
            this.paint_box("brown", sx + xdelta, sy + ydelta, sw, sh);
          }
        }
        painted(true);
        this.may_paint_now();
      } else {
        paint_error("unsupported encoding");
      }
    } catch (error) {
      const packet_sequence = packet[8];
      this.exc(error, "error painting", coding, "sequence no", packet_sequence);
      paint_error(error);
    }
  }

  construct_base64_image_url(encoding, imageDataArrayBuffer) {
    const imageDataBase64 = Utilities.ArrayBufferToBase64(imageDataArrayBuffer);
    return `data:image/${encoding};base64,${imageDataBase64}`;
  }

  /**
   * Close the window and free all resources
   */
  destroy() {
    // remove div
    this.div.remove();
  }
}

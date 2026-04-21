/**
MIT License

Copyright (c) 2019 Mark Harkin

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

*/

const MENU_CONTENT_LEFT_CLASS_NAME = "menu-content-left";
const MENU_CONTENT_RIGHT_CLASS_NAME = "menu-content-right";

function noWindowList() {
  const open_windows = document.querySelector("#open_windows");
  if (open_windows) {
    open_windows.remove();
  }
}

function addWindowListItem(win, wid, title) {
  const li = document.createElement("li");
  li.className = "windowlist-li";
  li.id = `windowlistitem${wid}`;

  const a = document.createElement("a");

  a.id = `windowlistitemlink${wid}`;
  a.addEventListener("mouseover", function(e) {
    if (e.ctrlKey) {
      client._window_set_focus(win);
    }
  });
  a.addEventListener("click", function(e) {
    // Skip handling minimize, maximize, close events.
    if ($(e.target).hasClass(MENU_CONTENT_RIGHT_CLASS_NAME)) return;
    if (win.minimized) {
      win.toggle_minimized();
    } else {
      client.set_focus(win);
    }
    this.parentElement.parentElement.className = "-hide";
  });

  function hideWindowList() {
    document.querySelector("#open_windows_list").className = "";
  }

  const divLeft = document.createElement("div");
  divLeft.id = `windowlistdivleft${wid}`;
  divLeft.className = "menu-divleft";
  const img = new Image();
  img.id = `windowlistitemicon${wid}`;
  img.src = "favicon.png";
  img.className = MENU_CONTENT_LEFT_CLASS_NAME;
  divLeft.append(img);

  const titleDiv = document.createElement("div");
  titleDiv.append(document.createTextNode(title));
  titleDiv.id = `windowlistitemtitle${wid}`;
  titleDiv.className = MENU_CONTENT_LEFT_CLASS_NAME;
  divLeft.append(titleDiv);

  const divRight = document.createElement("div");
  divRight.className = "menu-divright";

  const img2 = new Image();
  img2.id = `windowlistitemclose${wid}`;
  img2.src = "icons/close.png";
  img2.title = "Close";
  img2.className = MENU_CONTENT_RIGHT_CLASS_NAME;
  img2.addEventListener("click", function(e) {
    client.send_close_window(win);
    e.stopPropagation();
    hideWindowList();
  });
  const img3 = new Image();
  img3.id = `windowlistitemmax${wid}`;
  img3.src = "icons/maximize.png";
  img3.title = "Maximize";
  img3.addEventListener("click", function(e) {
    win.toggle_maximized();
    e.stopPropagation();
    hideWindowList();
  });
  img3.className = MENU_CONTENT_RIGHT_CLASS_NAME;
  const img4 = new Image();
  img4.id = `windowlistitemmin${wid}`;
  img4.src = "icons/minimize.png";
  img4.title = "Minimize";
  img4.addEventListener("click", function(e) {
    win.toggle_minimized();
    e.stopPropagation();
    hideWindowList();
  });
  img4.className = MENU_CONTENT_RIGHT_CLASS_NAME;

  divRight.append(img2);
  divRight.append(img3);
  divRight.append(img4);
  a.append(divLeft);
  a.append(divRight);
  li.append(a);

  document.querySelector("#open_windows_list").append(li);
}

function removeWindowListItem(itemId) {
  const element = document.querySelector(`#windowlistitem${itemId}`);
  if (element && element.parentNode) {
    element.remove();
  }
}

$(function() {
  const float_menu = $("#float_menu");
  float_menu.draggable({
    cancel: ".noDrag",
    containment: "window",
    scroll: false,
  });
  float_menu.on("dragstart", function(event_, ui) {
    client.mouse_grabbed = true;
  });
  float_menu.on("dragstop", function(event_, ui) {
    client.mouse_grabbed = false;
    client.toolbar_position = "custom";
    client.reconfigure_all_trays();

    if (float_menu.children(".Menu").hasClass("-vertical")) {
      return;
    }

    // If the float menu is in the upper half of the screen, the menu_list and open_windows_list will open downwards, and vice versa.
    const float_menu_top_css = float_menu.css("top")
    const float_menu_top = float_menu_top_css.substring(0, float_menu_top_css.length - 2);

    if (Number(float_menu_top) > client.desktop_height / 2) {
      $("#menu_list").css("bottom", "30px");
      $("#open_windows_list").css({
        "bottom": "30px",
        "border-top-left-radius": "3px",
        "border-top-right-radius": "3px",
        "border-bottom-left-radius": "0px",
        "border-bottom-right-radius": "0px"
      });
    } else {
      $("#menu_list").css("bottom", "unset");
      $("#open_windows_list").css({
        "bottom": "unset",
        "border-top-left-radius": "0px",
        "border-top-right-radius": "0px",
        "border-bottom-left-radius": "3px",
        "border-bottom-right-radius": "3px"
      });
    }
  });
});

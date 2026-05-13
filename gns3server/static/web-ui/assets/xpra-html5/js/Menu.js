/**
MIT License

Copyright (c) 2019 Mark Harkin, 2016 Dylan Hicks (aka. dylanh333)

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

(function() {
  function $(selector, context) {
    context = context || document;
    return context["querySelectorAll"](selector);
  }

  function forEach(collection, iterator) {
    for (const key in Object.keys(collection)) {
      iterator(collection[key]);
    }
  }

  const ACTIVE_CLASS_NAME = "-active";
  const ANIMATING_CLASS_NAME = "-animating";
  const HAS_SUBMENU_CLASS_NAME = "-hasSubmenu";
  const HIDE_CLASS_NAME = "-hide";
  const MENU_CLASS_NAME = "Menu";
  const VISIBLE_CLASS_NAME = "-visible";

  function showMenu() {
    const menu = this;
    const ul = $("ul", menu)[0];
    //hack to hide the menu from javascript
    if (!ul) {
      return;
    }

    if (ul.classList.contains(HIDE_CLASS_NAME)) {
      ul.classList.remove(HIDE_CLASS_NAME);
      ul.parentElement.classList.remove(ACTIVE_CLASS_NAME);
      return;
    }

    if (ul.classList.contains(VISIBLE_CLASS_NAME)) {
      return;
    }

    menu.classList.add(ACTIVE_CLASS_NAME);
    ul.classList.add(ANIMATING_CLASS_NAME);
    ul.classList.add(VISIBLE_CLASS_NAME);
    setTimeout(function() {
      ul.classList.remove(ANIMATING_CLASS_NAME);
    }, 25);
  }

  function hideMenu() {
    const menu = this;
    const ul = $("ul", menu)[0];

    if (!ul || !ul.classList.contains(VISIBLE_CLASS_NAME)) return;

    menu.classList.remove(ACTIVE_CLASS_NAME);
    ul.classList.add(ANIMATING_CLASS_NAME);
    setTimeout(function() {
      ul.classList.remove(VISIBLE_CLASS_NAME);
      ul.classList.remove(ANIMATING_CLASS_NAME);
    }, 300);
  }

  function hideAllInactiveMenus() {
    const menu = this;
    forEach(
      $(
        `li.${HAS_SUBMENU_CLASS_NAME}.${ACTIVE_CLASS_NAME}:not(:hover)`,
        menu.parent
      ),
      function(e) {
        e.hideMenu && e.hideMenu();
      }
    );
  }

  function hideAllMenus() {
    const menu = this;
    forEach($(`li.${HAS_SUBMENU_CLASS_NAME}`, menu.parent), function(e) {
      e.hideMenu && e.hideMenu();
    });
  }

  window.addEventListener("load", function() {
    forEach(
      $(`.${MENU_CLASS_NAME} li.${HAS_SUBMENU_CLASS_NAME}`),
      function(e) {
        e.showMenu = showMenu;
        e.hideMenu = hideMenu;
      }
    );

    forEach(
      $(`.${MENU_CLASS_NAME} > li.${HAS_SUBMENU_CLASS_NAME}`),
      function(e) {
        e.addEventListener("click", showMenu);
      }
    );

    forEach(
      $(`.${MENU_CLASS_NAME} > li.${HAS_SUBMENU_CLASS_NAME} li`),
      function(e) {
        e.addEventListener("mouseenter", hideAllInactiveMenus);
      }
    );

    forEach(
      $(
        `.${MENU_CLASS_NAME} > li.${HAS_SUBMENU_CLASS_NAME} li.${HAS_SUBMENU_CLASS_NAME}`
      ),
      function(e) {
        e.addEventListener("mouseenter", showMenu);
      }
    );

    forEach($("a"), function(e) {
      e.addEventListener("click", hideAllMenus);
    });

    document.addEventListener("click", hideAllInactiveMenus);
  });
})();

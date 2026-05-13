# Xpra HTML5 Client Configuration

## Overview

Web Wireshark integration uses xpra's built-in HTML5 client to provide browser-based packet capture viewing. The xpra HTML5 client is located at `/usr/share/xpra/www` in the container.

## Configuration Methods

### 1. URL Parameters (Per-Session)

Control toolbar menu items via URL query parameters (default: true):

| Parameter | Menu Item | Description |
|-----------|-----------|-------------|
| xpramenu | Xpra Menu | Main menu (Server, Information submenus) |
| open_windows | Open Windows | List of open windows |
| fullscreen_button | Fullscreen | Fullscreen toggle button |
| keyboard_button | Keyboard | Keyboard layout/shortcuts |
| clipboard_button | Clipboard Copy | Clipboard copy functionality |
| sound_button | Audio | Audio toggle |
| cursor_lock_button | Lock Cursor | Game cursor lock mode |

```bash
# Examples
?fullscreen_button=false&sound_button=false
?xpramenu=false&keyboard_button=false&clipboard_button=false&sound_button=false&cursor_lock_button=false
```

### 2. default-settings.txt (Recommended - Global/Persistent)

Modify `html5/default-settings.txt` (INI format) for all users.

**Features:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| keyboard | auto-detect | Enable keyboard input |
| keyboard_layout | us | Keyboard layout |
| clipboard | yes | Clipboard sharing |
| printing | yes | Printer forwarding |
| file_transfer | yes | File transfer |
| swap_keys | MacOS yes | Swap Command/Control keys |
| scroll_reverse_x | no | Reverse mouse X-axis |
| floating_menu | yes | Show floating menu |
| toolbar_position | top-left | Toolbar position |
| autohide | no | Auto-hide toolbar |
| sound | yes | Audio forwarding |
| video | 64-bit yes | Video decoding |

**Connection Options:**

| Parameter | Description |
|-----------|-------------|
| server | Server address |
| port | Port number |
| username | Username |
| password | Password |
| ssl | Enable SSL |
| encryption | Encryption type (AES-CBC/CTR/CFB) |
| key | AES encryption key |
| sharing | Allow session sharing |
| steal | Steal session |
| reconnect | Auto-reconnect |
| bandwidth_limit | Bandwidth limit (bits/s) |
| override_width | Client desktop width |

**Advanced Options:**

| Parameter | Default | Description |
|-----------|---------|-------------|
| audio_codec | auto-detect | Audio codec |
| encoding | auto | Image encoding (png/jpeg/webp/etc) |
| remote_logging | yes | Send logs to server |
| action | connect | Connection mode (start/shadow) |
| submit | yes | Show diagnostics on disconnect |

### 3. default_settings in Code

Set directly in `<script>` tag in index.html:
```javascript
const default_settings = {};
default_settings["xpramenu"] = false;
```

### Priority Order

URL parameter > default_settings object > default-settings.txt > code default value

## Server-Controlled Submenu Items

The **Server submenu** items are controlled by server hello message:

| Menu Item ID | Content | Control Source |
|--------------|---------|----------------|
| clock_menu_entry | Clock | server-time in hello |
| upload_menu_entry | Upload file | file-transfer or file.enabled |
| download_menu_entry | Download file | file-transfer or file.enabled |
| shutdown_menu_entry | Shutdown Server | client-shutdown in hello |

**Information submenu** (About Xpra, Session Info, Bug Report) and fixed items (Reload, Disconnect) are always displayed.

To hide "Shutdown Server", set environment variable before starting xpra:
```bash
export XPRA_CLIENT_CAN_SHUTDOWN=false
xpra start :{display} ...
```
Code: `xpra/server/base.py:40` - `CLIENT_CAN_SHUTDOWN = envbool("XPRA_CLIENT_CAN_SHUTDOWN", True)`

## Customizing Background Image

Background image is defined in `html5/css/client.css`:
```css
body {
    margin: 0;
    padding: 0;
    overflow: hidden;
    background-color: #021d3a;
    background-image: url(../background.jpg);
    background-position: center center;
    background-repeat: no-repeat;
    background-size: cover;
}
```

### Methods

1. **Replace image file**: Create/replace `html5/background.jpg`
2. **Modify CSS**: Change `html5/css/client.css` line 9:
   ```css
   background-image: url(../your-image.jpg);
   ```

### Notes
- Supported formats: jpg, png, svg, etc.
- Recommended resolution: 1920x1080 or higher
- `background-size: cover` auto-stretches to fill

### Temporary Modification (via URL)

Cannot modify background via URL directly, but can use browser DevTools:
```css
body { background-image: url(your-image-url); }
```

## Related Files

- Container Dockerfile: `gns3server/agent/web_wireshark/docker/Dockerfile`
- Container HTML5 client path: `/usr/share/xpra/www`

# xpra-html5

HTML5 client for Xpra remote desktop server.

## Version

This is based on **xpra-html5 version 19** from the official Xpra project.

## License

This project is licensed under the Mozilla Public License Version 2.0 (MPL-2.0).

See the [LICENSE](LICENSE) file for the full license text.

## Copyright

Copyright (c) 2013 Antoine Martin <antoine@xpra.org>
Copyright (c) 2014 Joshua Higgins <josh@kxes.net>

## Source

This is a modified version of the xpra-html5 client from the official Xpra project:
- Official repository: https://github.com/Xpra-org/xpra-html5
- Project website: https://xpra.org/
- Version: 19

## Modifications from v19

This version has been modified for integration with GNS3 Web UI:

### Client.js
No modifications - using original v19 code.

### Protocol.js
- **Line 191**: Added documentation comment clarifying that the 'binary' subprotocol is required by xpra protocol
- Code remains unchanged from v19

### index.html
- **Lines 927-933**: Simplified connection close callback
  - **Before**: Redirected to connect.html with extensive parameter passing
  - **After**: Only logs the close reason, no redirection
  - **Impact**: Simplified error handling for embedded GNS3 Web UI usage
- Removed 82 lines of redirection logic

### TypeScript Service (xpra-console.service.ts)
- **buildXpraConsolePageUrl()**: Improved WebSocket URL parsing
  - **Before**: Manual parsing and concatenation of path and token
  - **After**: Using URL API to correctly extract pathname and search
  - **Impact**: More reliable handling of query parameters and tokens

## Summary of Changes

- **Total files modified**: 3
- **Lines added**: 11
- **Lines removed**: 95
- **Net change**: -84 lines (simplified)

All modifications maintain compliance with MPL-2.0 license requirements.

## License Compliance

This project complies with the MPL-2.0 license requirements:
- All source code modifications are made available under MPL-2.0
- Original copyright notices are preserved
- A copy of the MPL-2.0 license is included
- Modifications are clearly documented

For more information about MPL-2.0, see:
https://www.mozilla.org/en-US/MPL/2.0/FAQ/

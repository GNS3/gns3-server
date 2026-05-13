# Web Wireshark JWT Token Flow

## Background

Question: What is the purpose of `jwt_token` parameter in UDPLink and how is it transmitted?

## JWT Token Complete Flow

1. **User initiates request** → HTTP request with `Authorization: Bearer <jwt_token>`

2. **API layer extracts token** → `gns3server/api/routes/controller/links.py`:
   ```python
   auth_header = http_request.headers.get("Authorization", "")
   jwt_token = auth_header.replace("Bearer ", "") if auth_header else None
   ```

3. **Pass to Link layer** → `Link.start_capture(wireshark=True, jwt_token=xxx)`

4. **UDPLink forwards** → `UDPLink.start_capture()` calls `super().start_capture(jwt_token=jwt_token)`

5. **Start Web Wireshark container** → `Link._start_web_wireshark(jwt_token)` calls management script

6. **Container uses token** → `manage_wireshark.py` executes inside container:
   ```bash
   curl -N -H 'Authorization: Bearer {jwt_token}' \
     'http://controller:3080/v3/projects/{project_id}/links/{link_id}/capture/stream' | \
     wireshark -i - -k -display :{display}
   ```

## Why More Verbose Than gns3-copilot?

**gns3-copilot approach**:
- All code within the same process
- Uses `contextvars` to store and retrieve token
- Downstream code directly calls `get_current_jwt_token()`, no need to pass through layers

**Web Wireshark approach**:
- Token needs to be passed across processes (management script is separate process)
- Token needs to be passed across containers (Docker container isolation)
- Cannot use `contextvars`, must pass through command line arguments

## Conclusion

UDPLink does not use this token, it only forwards it to the parent class. Ultimately used by the curl command inside the Web Wireshark container to authenticate with the GNS3 controller's capture stream API.

Token flow: **Client → GNS3 API → Link → UDPLink → Web Wireshark container → GNS3 capture stream API**

## Related Files

- `gns3server/api/routes/controller/links.py:114-115` - JWT token extraction
- `gns3server/controller/link.py:321-360` - Web Wireshark startup logic
- `gns3server/controller/udp_link.py:178` - UDPLink start_capture signature
- `gns3server/agent/web_wireshark/manage_wireshark.py:527-529` - Container curl command with JWT

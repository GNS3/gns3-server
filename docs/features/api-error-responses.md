# API Error Response Format

## Overview

GNS3 Server uses a unified error response format across all API endpoints. All error responses return a JSON object with a `message` field containing the error details.

## Response Format

```json
{
  "message": "Error description here"
}
```

## Error Types

| Error Type | HTTP Status | Description |
|------------|-------------|-------------|
| `ControllerBadRequestError` | 400 | Invalid request parameters (e.g., validation failure) |
| `ControllerUnauthorizedError` | 401 | Missing or invalid authentication |
| `ControllerForbiddenError` | 403 | User lacks required privileges |
| `ControllerNotFoundError` | 404 | Resource not found |
| `ControllerError` | 409 | General conflict (e.g., duplicate name) |
| `ControllerTimeoutError` | 408 | Operation timed out |
| `ComputeConflictError` | 409 | Compute node returned a conflict |
| `RequestValidationError` | 422 | Pydantic/FastAPI validation error (field missing or type mismatch) |
| `SQLAlchemyError` | 500 | Database error |

## Error Response Examples

### Template Already Exists (409)
```json
{
  "message": "A template with name 'my-template' already exists"
}
```

### Validation Error (422)
```json
{
  "message": "image field is required"
}
```

### Permission Denied (403)
```json
{
  "message": "Permission denied (privilege Template.Allocate is required)"
}
```

### Invalid Template Type (400)
```json
{
  "message": "JSON schema error received while creating new template: ..."
}
```

## Client-Side Error Handling

When handling errors in the GNS3 Web UI or API clients:

```javascript
// Extract error message from response
function extractErrorMessage(error) {
  if (error.error && error.error.message) {
    return error.error.message;
  }
  if (error.message) {
    return error.message;
  }
  return 'Unknown error';
}
```

## References

- Exception handlers: `gns3server/api/server.py`
- Template validation: `gns3server/schemas/controller/templates/`
- Error classes: `gns3server/controller/controller_error.py`

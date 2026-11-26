"""Bound configuration requests and avoid logging invalid configuration bytes."""

from uuid import UUID

from fastapi import HTTPException, Request
from fastapi.dependencies.models import Dependant
from fastapi.dependencies.utils import solve_dependencies
from fastapi.exceptions import RequestValidationError, ResponseValidationError
from fastapi.routing import APIRoute
from pydantic import ValidationError

from gns3server.api.errors import error_response
from gns3server.services.configurations.shared.errors import (
    CAPTURE_FAILURES,
    VALIDATION_FIELDS,
    VALIDATION_REASONS,
    ConfigurationError,
    error_status,
)


def validation_details(error):
    # Only these field names are echoed back; anything else is reduced to
    # "field" so a request can never reflect attacker-chosen keys or values.
    problems = []
    for problem in error.errors()[:16]:
        location = []
        for part in problem.get("loc", ()):
            if isinstance(part, int) or part in VALIDATION_FIELDS:
                location.append(part)
            else:
                try:
                    location.append(str(UUID(str(part))))
                except (ValueError, TypeError, AttributeError):
                    location.append("field")
        item = {"location": location, "type": problem["type"]}
        reason = str(problem.get("ctx", {}).get("error", ""))
        if reason in VALIDATION_REASONS:
            item["reason"] = reason
        if item not in problems:
            problems.append(item)
    return {"validation_errors": problems}


def _authentication_calls():
    # Imported lazily: both modules import application settings and the database.
    from gns3server.api.routes.compute.dependencies.authentication import compute_authentication
    from gns3server.api.routes.controller.dependencies.authentication import get_current_active_user

    return {get_current_active_user, compute_authentication}


def _with_body(request, body):
    """The request again, with its already read body.

    The body is replayed once; after it come the connection's own messages, so a disconnect stays visible.
    """
    original = request.receive
    replayed = False

    async def replay():
        nonlocal replayed
        if replayed:
            return await original()
        replayed = True
        return {"type": "http.request", "body": body, "more_body": False}

    return Request(request.scope, replay)


class ConfigurationRoute(APIRoute):
    max_request_bytes = 16 * 1024

    async def authenticate_before_body(self, request: Request):
        """Run only the authentication dependencies of this route.

        FastAPI reads the body before it resolves dependencies, so without this
        an anonymous client could make the server buffer a full request body.
        """
        calls = _authentication_calls()
        auth = [dependency for dependency in self.dependant.dependencies if dependency.call in calls]
        if not auth:
            return
        result = await solve_dependencies(
            request=request,
            dependant=Dependant(dependencies=auth),
            dependency_overrides_provider=request.scope.get("app"),
            async_exit_stack=request.scope["fastapi_inner_astack"],
            embed_body_fields=False,
        )

    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded_handler(request: Request):
            if request.method in ("POST", "PUT"):
                await self.authenticate_before_body(request)
                try:
                    declared = int(request.headers.get("content-length", "0"))
                except ValueError:
                    declared = 0
                if declared > self.max_request_bytes:
                    raise HTTPException(status_code=413, detail="configuration_request_too_large")
                payload = bytearray()
                async for chunk in request.stream():
                    payload.extend(chunk)
                    if len(payload) > self.max_request_bytes:
                        raise HTTPException(status_code=413, detail="configuration_request_too_large")
                request = _with_body(request, bytes(payload))
            try:
                response = await handler(request)
                response.headers["Cache-Control"] = "no-store"
                return response
            except RequestValidationError as error:
                # The application-wide handler includes raw Pydantic inputs.
                return error_response(
                    422,
                    "invalid_configuration_request",
                    details=validation_details(error),
                    headers={"Cache-Control": "no-store"},
                )
            except ConfigurationError as error:
                code = error.code
                if code == "console_recovery_required" and error.previous_error in CAPTURE_FAILURES:
                    return error_response(
                        409,
                        code,
                        details={"previous_error": error.previous_error},
                        headers={"Cache-Control": "no-store"},
                    )
                status = error_status(code)
                if error.context:
                    return error_response(status, code, details=error.context, headers={"Cache-Control": "no-store"})
                raise HTTPException(status_code=status, detail=code) from None
            except (ValidationError, ResponseValidationError):
                raise HTTPException(status_code=502, detail="invalid_configuration_response") from None
            except TimeoutError:
                raise HTTPException(status_code=408, detail="configuration_export_timeout") from None
            except OSError:
                raise HTTPException(status_code=502, detail="configuration_export_failed") from None

        return bounded_handler

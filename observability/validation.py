"""Request/Response validation middleware using Pydantic models."""

from collections.abc import Callable
from functools import wraps

from flask import Response, g, jsonify, request
from pydantic import BaseModel, ValidationError

from domain.exceptions import ValidationError as DomainValidationError
from observability.logging import get_logger

logger = get_logger(__name__)


class RequestValidator:
    """Validates incoming request data against Pydantic models."""

    def __init__(self, request_model: type[BaseModel] | None = None):
        self.request_model = request_model

    def validate(self, data: dict) -> BaseModel:
        """Validate request data and return model instance."""
        if self.request_model is None:
            return None
        try:
            return self.request_model(**data)
        except ValidationError as e:
            raise DomainValidationError(
                "Request validation failed", field="request_body", details={"errors": e.errors()}
            )


class ResponseValidator:
    """Validates outgoing response data against Pydantic models."""

    def __init__(self, response_model: type[BaseModel] | None = None):
        self.response_model = response_model

    def validate(self, data: dict) -> dict:
        """Validate response data and return validated dict."""
        if self.response_model is None:
            return data
        try:
            model = self.response_model(**data)
            return model.model_dump(mode="json")
        except ValidationError as e:
            logger.error(
                "Response validation failed",
                errors=e.errors(),
                path=request.path if request else None,
            )
            # In production, might want to still return the data but log the error
            return data


def validate_request(request_model: type[BaseModel]):
    """Decorator to validate request body against a Pydantic model."""

    def decorator(f: Callable):
        @wraps(f)
        def wrapper(*args, **kwargs):
            validator = RequestValidator(request_model)
            try:
                if request.is_json:
                    validated = validator.validate(request.get_json() or {})
                    g.validated_request = validated
                else:
                    raise DomainValidationError("Request must be JSON", field="content_type")
            except DomainValidationError:
                raise
            except Exception as e:
                raise DomainValidationError(f"Request parsing failed: {e}", field="request_body")
            return f(*args, **kwargs)

        return wrapper

    return decorator


def validate_response(response_model: type[BaseModel]):
    """Decorator to validate response body against a Pydantic model."""

    def decorator(f: Callable):
        @wraps(f)
        def wrapper(*args, **kwargs):
            result = f(*args, **kwargs)
            # Handle different response types
            if isinstance(result, tuple):
                data, status_code = result[0], result[1] if len(result) > 1 else 200
                headers = result[2] if len(result) > 2 else {}
            else:
                data = result
                status_code = 200
                headers = {}

            if isinstance(data, Response):
                return data

            validator = ResponseValidator(response_model)
            try:
                validated_data = validator.validate(data)
                return jsonify(validated_data), status_code, headers
            except DomainValidationError:
                raise
            except Exception:
                # Log but don't fail on response validation in production
                logger.warning("Response validation error", path=request.path)
                return jsonify(data), status_code, headers

        return wrapper

    return decorator


def init_validation_middleware(app):
    """Initialize validation middleware for Flask app."""
    # This is a placeholder for global validation middleware
    # Individual routes should use @validate_request/@validate_response decorators

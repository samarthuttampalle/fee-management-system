"""HTTP API package — blueprints for health, students, and admin routes."""

from fee_management.api import admin, health, students

__all__ = ["admin", "health", "students"]

"""Deployment enforcement modes. Authorization authority remains deterministic."""

from __future__ import annotations

from enum import StrEnum


class EnforcementMode(StrEnum):
    ENFORCE = "ENFORCE"
    SHADOW = "SHADOW"
    AUDIT = "AUDIT"

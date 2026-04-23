"""Custom exceptions used by the framework."""


class AutoharnessError(Exception):
    """Base error for framework failures."""


class ConfigError(AutoharnessError):
    """Raised when an experiment config is invalid."""


class NotImplementedYetError(AutoharnessError):
    """Raised for scaffolded commands that are not implemented yet."""

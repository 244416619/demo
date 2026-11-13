"""Errors raised by domain objects and the sample-data catalog."""


class DomainError(ValueError):
    """A value cannot form the domain object it was passed to.

    This is a shape or unit problem (wrong grid size, negative depth,
    overlapping rainfall intervals). It is not a numerical solver failure.
    """


class FixtureNotFound(LookupError):
    """No bundled sample fixture has the requested id."""

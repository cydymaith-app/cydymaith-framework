"""The one exception the framework raises for bad content."""


class ContentError(ValueError):
    """The project's data files are inconsistent."""

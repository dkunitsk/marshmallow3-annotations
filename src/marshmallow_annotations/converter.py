from typing import _ClassVar  # type: ignore
from typing import AbstractSet, Union, get_type_hints

import marshmallow

from .base import (
    AbstractConverter,
    ConfigOptions,
    GeneratedFields,
    NamedConfigs,
    TypeRegistry,
)
from .registry import registry

NoneType = type(None)


def _is_optional(typehint):
    # only supports single type optionals/unions
    # as for the implementation... look, don't ask me
    return (
        hasattr(typehint, "__origin__")
        and typehint.__origin__ is Union
        and len(typehint.__args__) == 2
        and NoneType in typehint.__args__
    )


def _extract_optional(typehint):
    """Given Optional[X] return X."""
    optional_types = [t for t in typehint.__args__ if t is not NoneType]
    return optional_types[0]


def _is_class_var(typehint):
    try:
        return isinstance(typehint, _ClassVar)
    except TypeError:  # pragma: no branch
        return False


def should_include(typehint):
    return not _is_class_var(typehint)


class BaseConverter(AbstractConverter):
    """
    Default implementation of :class:`~marshmallow_annotations.base.AbstractConverter`.

    Handles parsing types for type hints and mapping those type hints into
    marshmallow field instances by way of a
    :class:`~marshmallow_annotations.base.TypeRegistry` instance.
    """

    def __init__(self, *, registry: TypeRegistry = registry) -> None:
        self.registry = registry

    def convert(
        self, typehint: type, opts: ConfigOptions = None
    ) -> marshmallow.fields.FieldABC:
        opts = opts if opts is not None else {}
        return self._field_from_typehint(typehint, opts)

    def convert_all(
        self,
        target: type,
        ignore: AbstractSet[str] = frozenset([]),  # noqa
        configs: NamedConfigs = None,
    ) -> GeneratedFields:
        configs = configs if configs is not None else {}
        for k, default in self._get_field_defaults(target).items():
            configs[k] = {"missing": default, **configs.get(k, {})}
        return {
            k: self.convert(v, configs.get(k, {}))
            for k, v in self._get_type_hints(target).items()
            if k not in ignore and should_include(v)
        }

    def is_scheme(self, typehint: type) -> bool:
        constructor = self.registry.get(typehint)
        return getattr(constructor, "__is_scheme__", False)

    def _field_from_typehint(self, typehint, kwargs=None):
        # need that immutable dict in the stdlib pls
        kwargs = kwargs if kwargs is not None else {}

        # sane defaults
        allow_none = False
        required = True
        missing = marshmallow.missing

        if _is_optional(typehint):
            allow_none = True
            required = False
            missing = None
            typehint = _extract_optional(typehint)

        # set this after optional check
        subtypes = getattr(typehint, "__args__", ())

        if subtypes != ():
            typehint = typehint.__base__

        kwargs.setdefault("allow_none", allow_none)
        kwargs.setdefault("required", required)
        kwargs.setdefault("missing", missing)

        field_constructor = self.registry.get(typehint)
        return field_constructor(self, subtypes, kwargs)

    def _get_type_hints(self, item):
        hints = {}
        for parent in item.__mro__[::-1]:
            hints.update(get_type_hints(parent))
        return hints

    def _get_field_defaults(self, item):
        """Read default values for fields from the target item."""
        return {}

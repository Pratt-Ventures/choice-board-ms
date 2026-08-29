"""Schema extensions: application-added columns on pvf-owned tables.

The application declares added columns (principally for customer, user, share, or
external api tables) before any pvf model is imported — the runner and
pvf_get_alembic_config both invoke the shell's optional register_schema_extensions()
hook first, then extensible pvf model modules build their table class through
extend_model_class().

Pattern for an extensible pvf model module:

    class PvfCustomerSpec(SQLModel):           # NOT a table; fields + methods live here
        id: int | None = Field(default=None, primary_key=True)
        ...
        def create_customer_system(self, ...): ...

    PvfCustomer = extend_model_class(PvfCustomerSpec, get_schema_extension_registry().for_table("pvf_customer"))

extend_model_class recreates the class (with table=True) re-declaring every field in
order, injecting each added column immediately after its predecessor field, and
carrying over all methods. The spec class is never mapped, so there is no metadata
conflict; when no columns are registered the spec class is used as-is by convention
(it must then be declared table=True itself — see note below).

Rules:
  - fields are injected immediately after the named predecessor field ('after')
  - nothing may be inserted before the standard 'id' field used in pvf tables
  - only registered extensible tables may be extended (EXTENSIBLE_TABLES)
  - added fields are otherwise moved around and stored by pvf only; the application
    populates them via extra_fields dictionaries on the appropriate internal calls
"""
import types
from typing import Any

from pydantic import BaseModel
from sqlmodel import Field, SQLModel

# pvf tables the application may add columns to (by table name)
EXTENSIBLE_TABLES = frozenset({"pvf_customer", "pvf_user", "pvf_sharelink", "pvf_apiaccessconfiguration"})


class PvfAddedColumn(BaseModel):
    table: str
    name: str
    type: str = "str"          # python type name: str | int | bool | float
    default: Any = None
    after: str                 # predecessor field name; nothing is allowed before 'id'
    description: str | None = None


_TYPE_MAP = {"str": str, "int": int, "bool": bool, "float": float}


class PvfSchemaExtensionError(RuntimeError):
    pass


class PvfSchemaExtensionRegistry(BaseModel):
    """Application-added columns on pvf-owned tables."""
    added_columns: list[PvfAddedColumn] = []

    def add_column(self, *, table: str, name: str, type: str = "str", default: Any = None,
                   after: str, description: str | None = None) -> None:
        if table not in EXTENSIBLE_TABLES:
            raise PvfSchemaExtensionError(
                f"table '{table}' is not extensible; allowed: {sorted(EXTENSIBLE_TABLES)}"
            )
        if type not in _TYPE_MAP:
            raise PvfSchemaExtensionError(f"unsupported added-column type '{type}'; allowed: {sorted(_TYPE_MAP)}")
        if any(c.table == table and c.name == name for c in self.added_columns):
            raise PvfSchemaExtensionError(f"duplicate added column '{name}' for table '{table}'")
        self.added_columns.append(
            PvfAddedColumn(table=table, name=name, type=type, default=default, after=after, description=description)
        )

    def for_table(self, table: str) -> list[PvfAddedColumn]:
        return [c for c in self.added_columns if c.table == table]


# The process-global registry populated by the startup logic (runner / alembic config)
# before any pvf model module is imported.
_active_registry: "PvfSchemaExtensionRegistry | None" = None


def get_schema_extension_registry() -> PvfSchemaExtensionRegistry:
    global _active_registry
    if _active_registry is None:
        _active_registry = PvfSchemaExtensionRegistry()
    return _active_registry


def extend_model_class(spec_cls: type[SQLModel], added: list[PvfAddedColumn]) -> type[SQLModel]:
    """Build the table class for an extensible pvf model.

    spec_cls is a non-table SQLModel carrying the base fields (in order) and all
    methods. The returned class is the real table class. With no added columns it is a
    plain table subclass of the spec; with added columns every field is re-declared in
    order and each added column is injected immediately after its predecessor field.
    Nothing may be inserted before the standard 'id' field.
    """
    if getattr(spec_cls, "__table__", None) is not None:
        raise PvfSchemaExtensionError(
            f"{spec_cls.__name__} is already a mapped table class; extensible pvf models must "
            "be defined as a non-table spec class"
        )

    # the built table class takes the spec's name minus any 'Spec' suffix, so
    # SQLModel derives the correct default table name from it
    class_name = spec_cls.__name__
    if class_name.endswith("Spec"):
        class_name = class_name[:-4]
    class_kwargs = {"table": True}

    if not added:
        return types.new_class(class_name, (spec_cls,), class_kwargs, lambda ns: None)

    base_fields = list(spec_cls.model_fields.items())  # ordered, includes inherited
    base_names = [name for name, _ in base_fields]
    if "id" not in base_names:
        raise PvfSchemaExtensionError(f"{spec_cls.__name__} has no standard 'id' field; cannot be extended")

    insertions: dict[str, list[PvfAddedColumn]] = {}
    for column in added:
        if column.after not in base_names:
            raise PvfSchemaExtensionError(
                f"added column '{column.name}' names unknown predecessor field '{column.after}' on {spec_cls.__name__}"
            )
        if base_names.index(column.after) < base_names.index("id"):
            raise PvfSchemaExtensionError(
                f"added column '{column.name}' may not be inserted before the standard 'id' field"
            )
        if column.name in base_names:
            raise PvfSchemaExtensionError(f"added column '{column.name}' collides with an existing field on {spec_cls.__name__}")
        insertions.setdefault(column.after, []).append(column)

    field_names = set(base_names)

    def _exec_body(namespace: dict) -> None:
        namespace["__module__"] = spec_cls.__module__
        if getattr(spec_cls, "__tablename__", None) is not None:
            namespace["__tablename__"] = spec_cls.__tablename__
        annotations: dict[str, Any] = {}
        namespace["__annotations__"] = annotations
        # carry over methods and other callable attributes from the spec class
        for base in reversed(spec_cls.__mro__):
            if base in (SQLModel, BaseModel, object):
                continue
            for attr_name, attr_value in base.__dict__.items():
                if attr_name in field_names or attr_name.startswith("__") and attr_name.endswith("__"):
                    continue
                if callable(attr_value) or isinstance(attr_value, (classmethod, staticmethod, property)):
                    namespace.setdefault(attr_name, attr_value)
        # re-declare all fields in order, with insertions after their predecessor
        for name, field_info in base_fields:
            annotations[name] = field_info.annotation
            namespace[name] = field_info
            for column in insertions.get(name, []):
                annotations[column.name] = _TYPE_MAP[column.type] | None
                namespace[column.name] = Field(default=column.default, description=column.description)

    return types.new_class(class_name, spec_cls.__bases__, class_kwargs, _exec_body)


def apply_extra_fields(row: SQLModel, extra_fields: dict | None) -> None:
    """Populate application-added columns on a pvf row; unknown fields are rejected."""
    if not extra_fields:
        return
    valid = set(row.model_fields)
    unknown = [name for name in extra_fields if name not in valid]
    if unknown:
        raise PvfSchemaExtensionError(f"unknown extra fields for {type(row).__name__}: {unknown}")
    for name, value in extra_fields.items():
        setattr(row, name, value)

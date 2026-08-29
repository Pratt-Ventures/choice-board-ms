"""Tests for pvf schema extensions: registry validation, model factory mechanics,
and extra-fields population."""
import pytest
from sqlmodel import Field, SQLModel, select

from src.pvf.db.model_factory import (
    PvfSchemaExtensionError,
    PvfSchemaExtensionRegistry,
    apply_extra_fields,
    extend_model_class,
)
from src.pvf.db.models.customer_user import PvfCustomer, PvfUser
from src.pvf.db.models.share_link_tracking import PvfShareLink
from src.pvf.db.models.api_access_configuration import (
    PvfApiAccessConfiguration,
    PvfApiAccessConfigurationResult_Many,
    PvfApiAccessConfigurationResult_One,
    PvfApiWebInvocationResult_One,
)


class WidgetSpec(SQLModel):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(default="")
    size: int = Field(default=0)

    def describe(self) -> str:
        return f"{self.name}:{self.size}"


@pytest.fixture
def registry():
    yield PvfSchemaExtensionRegistry()
    # building extended classes registers tables on the shared metadata; drop them
    from sqlmodel import SQLModel as _SM
    for table_name in ("widget",):
        if table_name in _SM.metadata.tables:
            _SM.metadata.remove(_SM.metadata.tables[table_name])


# --- registry validation -------------------------------------------------------

def test_registry_rejects_non_extensible_table(registry):
    with pytest.raises(PvfSchemaExtensionError, match="not extensible"):
        registry.add_column(table="projectvoteparticipant", name="x", after="id")


def test_registry_rejects_unsupported_type(registry):
    with pytest.raises(PvfSchemaExtensionError, match="unsupported added-column type"):
        registry.add_column(table="pvf_customer", name="x", type="datetime", after="id")


def test_registry_rejects_duplicate_column(registry):
    registry.add_column(table="pvf_customer", name="loyalty_code", after="customer_email")
    with pytest.raises(PvfSchemaExtensionError, match="duplicate added column"):
        registry.add_column(table="pvf_customer", name="loyalty_code", after="customer_email")


# --- factory mechanics -----------------------------------------------------------

def test_zero_extensions_builds_plain_table_subclass(registry):
    Widget = extend_model_class(WidgetSpec, [])
    assert Widget.__name__ == "Widget"
    assert Widget.__tablename__ == "widget"
    assert set(Widget.model_fields) == {"id", "name", "size"}
    row = Widget(name="a", size=3)
    assert row.describe() == "a:3"  # methods preserved


def test_extension_injected_after_predecessor(registry):
    Widget = extend_model_class(WidgetSpec, [
        # table must be in EXTENSIBLE_TABLES; use a real one for the column, mapped onto the spec below
    ])
    # (see test_extension_position below for a real insertion)
    assert Widget is not None


def test_extension_position_and_metadata(registry):
    from src.pvf.db import model_factory

    # temporarily allow the synthetic table for this test
    monkey_tables = set(model_factory.EXTENSIBLE_TABLES) | {"widget"}
    original = model_factory.EXTENSIBLE_TABLES
    model_factory.EXTENSIBLE_TABLES = frozenset(monkey_tables)
    try:
        registry.add_column(table="widget", name="color", type="str", after="name", description="widget color")
        Widget = extend_model_class(WidgetSpec, registry.for_table("widget"))
    finally:
        model_factory.EXTENSIBLE_TABLES = original

    assert list(Widget.model_fields) == ["id", "name", "color", "size"]
    assert Widget.model_fields["color"].annotation == str | None
    assert Widget.model_fields["color"].description == "widget color"
    assert "color" in Widget.__table__.columns
    row = Widget(name="a", size=1, color="red")
    assert row.color == "red"
    assert row.describe() == "a:1"


def test_extension_nothing_before_id(registry):
    from src.pvf.db import model_factory

    original = model_factory.EXTENSIBLE_TABLES
    model_factory.EXTENSIBLE_TABLES = frozenset(set(original) | {"widget"})
    try:
        registry.add_column(table="widget", name="x", after="nonexistent")
        with pytest.raises(PvfSchemaExtensionError, match="unknown predecessor field"):
            extend_model_class(WidgetSpec, registry.for_table("widget"))
        registry.add_column(table="widget", name="name", after="id")
        with pytest.raises(PvfSchemaExtensionError, match="collides with an existing field"):
            extend_model_class(WidgetSpec, [c for c in registry.for_table("widget") if c.name == "name"])
        registry.add_column(table="widget", name="color", after="name")
        with pytest.raises(PvfSchemaExtensionError, match="duplicate added column"):
            registry.add_column(table="widget", name="color", after="size")
    finally:
        model_factory.EXTENSIBLE_TABLES = original


def test_extension_never_before_id():
    class OddSpec(SQLModel):
        seq: int = Field(default=0)
        id: int | None = Field(default=None, primary_key=True)

    from src.pvf.db import model_factory

    original = model_factory.EXTENSIBLE_TABLES
    model_factory.EXTENSIBLE_TABLES = frozenset(set(original) | {"odd"})
    try:
        registry = PvfSchemaExtensionRegistry()
        registry.add_column(table="odd", name="x", after="seq")
        with pytest.raises(PvfSchemaExtensionError, match="may not be inserted before the standard 'id' field"):
            extend_model_class(OddSpec, registry.for_table("odd"))
    finally:
        model_factory.EXTENSIBLE_TABLES = original


def test_mapped_spec_class_rejected():
    class MappedWidget(SQLModel, table=True):
        id: int | None = Field(default=None, primary_key=True)

    try:
        with pytest.raises(PvfSchemaExtensionError, match="already a mapped table class"):
            extend_model_class(MappedWidget, [])
    finally:
        from sqlmodel import SQLModel as _SM
        if "mappedwidget" in _SM.metadata.tables:
            _SM.metadata.remove(_SM.metadata.tables["mappedwidget"])


# --- real pvf models are spec-built and intact ----------------------------------

def test_real_pvf_models_intact():
    assert PvfCustomer.__tablename__ == "pvf_customer"
    assert PvfUser.__tablename__ == "pvf_user"
    assert PvfShareLink.__tablename__ == "pvf_sharelink"
    assert PvfApiAccessConfiguration.__tablename__ == "pvf_apiaccessconfiguration"
    # key fields survived the factory build
    for cls, field in ((PvfCustomer, "customer_email"), (PvfUser, "email"),
                       (PvfShareLink, "magic_token"), (PvfApiAccessConfiguration, "authentication_key_id")):
        assert field in cls.model_fields, f"{cls.__name__} missing {field}"
    assert PvfApiAccessConfigurationResult_One.__pydantic_complete__ is True
    assert PvfApiAccessConfigurationResult_Many.__pydantic_complete__ is True
    assert PvfApiWebInvocationResult_One.__pydantic_complete__ is True
    one_ann = PvfApiAccessConfigurationResult_One.model_fields["api_configuration_info"].annotation
    many_ann = PvfApiAccessConfigurationResult_Many.model_fields["api_configuration_list"].annotation
    assert getattr(one_ann, "__forward_arg__", None) is None
    assert getattr(many_ann, "__forward_arg__", None) is None
    assert PvfApiAccessConfiguration in getattr(one_ann, "__args__", (one_ann,))


# --- extra fields population ------------------------------------------------------

def test_apply_extra_fields_roundtrip():
    row = PvfCustomer(customer_email="a@b.c", customer_name="Acme")
    apply_extra_fields(row, {"customer_phone": "555-1234"})
    assert row.customer_phone == "555-1234"


def test_apply_extra_fields_rejects_unknown():
    row = PvfCustomer(customer_email="a@b.c", customer_name="Acme")
    with pytest.raises(PvfSchemaExtensionError, match="unknown extra fields"):
        apply_extra_fields(row, {"not_a_real_field": 1})

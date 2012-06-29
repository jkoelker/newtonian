
import re
import uuid

import netaddr

import sqlalchemy as sa
from sqlalchemy import types
from sqlalchemy.dialects import postgresql


class INET(types.TypeDecorator):
    impl = types.CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.INET())

        return dialect.type_descriptor(types.CHAR(39))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value

        if not isinstance(value, netaddr.IPAddress):
                value = netaddr.IPAddress(value)

        if value.version == 4:
            value = value.ipv6()

        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value

        value = netaddr.IPAddress(value)

        if value.is_ipv4_mapped():
            return value.ipv4()

        return value


class MAC(types.TypeDecorator):
    impl = types.CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.MACADDR())

        return dialect.type_descriptor(types.CHAR(16))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value

        if not isinstance(value, netaddr.EUI):
                value = netaddr.EUI(value)

        value.dialect = netaddr.mac_unix
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value

        value = netaddr.EUI(value)
        value.dialect = netaddr.mac_unix

        return value


class UUID(types.TypeDecorator):
    impl = types.CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.UUID())

        return dialect.type_descriptor(types.CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)

        if not isinstance(value, uuid.UUID):
            return str(uuid.UUID(value))

        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value

        return uuid.UUID(value)


class EnumSymbol(object):
    """Define a fixed symbol tied to a parent class."""

    def __init__(self, cls_, name, value, description):
        self.cls_ = cls_
        self.name = name
        self.value = value
        self.description = description

    def __reduce__(self):
        """Allow unpickling to return the symbol
        linked to the DeclEnum class."""
        return getattr, (self.cls_, self.name)

    def __iter__(self):
        return iter([self.value, self.description])

    def __repr__(self):
        return "<%s>" % self.name


class EnumMeta(type):
    """Generate new DeclEnum classes."""

    def __init__(cls, classname, bases, dict_):
        cls._reg = reg = cls._reg.copy()
        for k, v in dict_.items():
            if isinstance(v, tuple):
                sym = reg[v[0]] = EnumSymbol(cls, k, *v)
                setattr(cls, k, sym)
        return type.__init__(cls, classname, bases, dict_)

    def __iter__(cls):
        return iter(cls._reg.values())


class DeclEnum(object):
    """Declarative enumeration."""

    __metaclass__ = EnumMeta
    _reg = {}

    @classmethod
    def from_string(cls, value):
        try:
            return cls._reg[value]
        except KeyError:
            raise ValueError("Invalid value for %r: %r" %
                             (cls.__name__, value))

    @classmethod
    def values(cls):
        return cls._reg.keys()

    @classmethod
    def db_type(cls):
        return DeclEnumType(cls)


class DeclEnumType(types.SchemaType, types.TypeDecorator):
    def __init__(self, enum):
        self.enum = enum
        name = "ck%s" % re.sub('([A-Z])',
                               lambda m: "_" + m.group(1).lower(),
                               enum.__name__)
        self.impl = sa.Enum(*enum.values(), name=name)

    def _set_table(self, table, column):
        self.impl._set_table(table, column)

    def copy(self):
        return DeclEnumType(self.enum)

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return value.value

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return self.enum.from_string(value.strip())

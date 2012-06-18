
import datetime
import re
import uuid

import netaddr

import sqlalchemy as sa
from sqlalchmey import orm
from sqlalchemy import types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext import associationproxy
from sqlalchemy.ext import declarative


class INET(types.TypeDecorator):
    impl = types.CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.INET())
        else:
            return dialect.type_descriptor(types.CHAR(39))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, netaddr.IPAddress):
                value = netaddr.IPAddress(value)
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return netaddr.IPAddress(value)


class UUID(types.TypeDecorator):
    impl = types.CHAR

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(postgresql.UUID())
        else:
            return dialect.type_descriptor(types.CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            else:
                return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            return uuid.UUID(value)


class NewtonianBase(object):
    uuid = sa.Column(UUID, primary_key=True, default=lambda: uuid.uuid4())
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.utcnow)
    updated_at = sa.Column(sa.DateTime, default=datetime.datetime.utcnow,
                           onupdate=datetime.datetime.now)

    @declarative.declared_attr
    def __tablename__(cls):
        # NOTE(jkoelker) Pluralize the unCamelCased version of the class.
        #                Subclasses can still define __tablename__ to
        #                override. Adapted from Kotti.util
        name = re.sub(r"((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))",
                      r"_\1",
                      cls.__name__).lower()
        return name + 's'


BASE = declarative.declarative_base(cls=NewtonianBase)


class IsHazTenant(object):
    """Teanant mixin to magically support the tenant_id"""
    # NOTE(jkoelker) tenant_id is just a free form string ;(
    tenant_id = sa.Column(sa.String(255), nullable=False)


class HasTags(object):
    @declarative.declared_attr
    def tag_association_id(cls):
        return sa.Column(UUID, sa.ForeignKey("tag_associations.uuid"))

    @declarative.declared_attr
    def tag_association(cls):
        discriminator = cls.__name__.lower()
        cls.tags = associationproxy.association_proxy(
                    "tag_association", "tags",
                    creator=TagAssociation.creator(discriminator)
                )
        backref = orm.backref("%s_parent" % discriminator, uselist=False)
        return orm.relationship("TagAssociation", backref=backref)


class TagAssociation(BASE):
    __tablename__ = "tag_associations"
    discriminator = sa.Column(sa.String(255))

    @classmethod
    def creator(cls, discriminator):
        """Provide a 'creator' function to use with
        the association proxy."""

        return lambda tags: TagAssociation(tags=tags,
                                           discriminator=discriminator)


class Tag(BASE):
    association_id = sa.Column(UUID, sa.ForeignKey("tagassociation.uuid"))
    tag = sa.Column(sa.String(255), nullable=False)


class Subnet(BASE, IsHazTenant):
    network_uuid = sa.Column(sa.String(36), sa.ForeignKey("networks.uuid"),
                             nullable=False)
    address = sa.Column(INET, nullable=False)
    prefix = sa.Column(sa.Integer, nullable=False)

    def as_netaddr(self):
        return netaddr.IPNetwork((self.address.value, self.prefix))


class IpAddress(BASE):
    __tablename__ = "ip_addresses"


class MacRange(BASE):
    pass


class MacAddress(BASE):
    __tablename__ = "mac_addresses"


class Port(BASE):
    pass


class Network(BASE):
    name = sa.Column(sa.String(255), nullable=False)
    subnets = orm.relationshipt("Subnet",
                                backref=orm.backref("network",
                                                    uselist=False))

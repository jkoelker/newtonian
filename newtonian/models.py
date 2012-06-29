
import datetime
import re
import uuid

import netaddr

import sqlalchemy as sa
from sqlalchemy import orm
#from sqlalchemy import exc as sa_exc
from sqlalchemy import types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext import associationproxy
from sqlalchemy.ext import declarative
#from sqlalchemy.orm import collections


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

        if dialect.name == 'postgresql':
            return str(value)

        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value

        value = netaddr.IPAddress(value)

        if value.is_ipv4_mapped():
            return value.ipv4()

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


Base = declarative.declarative_base(cls=NewtonianBase)


class IsHazTenant(object):
    """Teanant mixin to magically support the tenant_id"""
    # NOTE(jkoelker) tenant_id is just a free form string ;(
    tenant_id = sa.Column(sa.String(255), nullable=False)


class Tag(Base):
    association_uuid = sa.Column(UUID,
                                 sa.ForeignKey("tag_association.uuid"),
                                 nullable=False)
    tag = sa.Column(sa.String(255), nullable=False)
    parent = associationproxy.association_proxy("association", "parent")
    association = orm.relationship("TagAssociation",
                                   backref=orm.backref("tags_association"))


class TagAssociation(Base):
    __tablename__ = "tag_association"

    discriminator = sa.Column(sa.String)
    tags = associationproxy.association_proxy("tags_association", "tag",
                                              creator=lambda t: Tag(tag=t))

    @classmethod
    def creator(cls, discriminator):
        return lambda tags: TagAssociation(tags=tags,
                                           discriminator=discriminator)

    @property
    def parent(self):
        """Return the parent object."""
        return getattr(self, "%s_parent" % self.discriminator)


class IsHazTags(object):
    @declarative.declared_attr
    def tag_association_uuid(cls):
        return sa.Column(UUID, sa.ForeignKey("tag_association.uuid"),
                         nullalble=False)

    @declarative.declared_attr
    def tag_association(cls):
        discriminator = cls.__name__.lower()
        creator = TagAssociation.creator(discriminator)
        cls.tags = associationproxy.association_proxy("tag_association",
                                                      "tags",
                                                      creator=creator)
        backref = orm.backref("%s_parent" % discriminator, uselist=False)
        return orm.relationship("TagAssociation", backref=backref)


class MetaIp(Base):
    subnet_uuid = sa.Column(UUID, sa.ForeignKey("subnets.uuid"),
                            nullable=False)
    ip = sa.Column(INET)


class Subnet(Base, IsHazTenant, IsHazTags):
    network_uuid = sa.Column(sa.String(36), sa.ForeignKey("networks.uuid"),
                             nullable=False)
    address = sa.Column(INET, nullable=False)
    prefix = sa.Column(sa.Integer, nullable=False)

    dns = orm.relationship("MetaIp", backref=orm.backref("subnet",
                                                         uselist=False))
    gateway = sa.Column(INET)
    unique = sa.Column(sa.Boolean, default=False)

    @property
    def netaddr(self):
        return netaddr.IPNetwork((self.address.value, self.prefix))

    @property
    def version(self):
        return self.address.version


class IpAddress(Base):
    __tablename__ = "ip_addresses"


class MacRange(Base):
    pass


class MacAddress(Base):
    __tablename__ = "mac_addresses"


class Port(Base):
    pass


class Network(Base):
    name = sa.Column(sa.String(255), nullable=False)
    subnets = orm.relationship("Subnet",
                               backref=orm.backref("network",
                                                   uselist=False))

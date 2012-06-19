
import datetime
import re
import uuid

import netaddr

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy import exc as sa_exc
from sqlalchemy import types
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext import associationproxy
from sqlalchemy.ext import declarative
from sqlalchemy.orm import collections


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


Base = declarative.declarative_base(cls=NewtonianBase)


class IsHazTenant(object):
    """Teanant mixin to magically support the tenant_id"""
    # NOTE(jkoelker) tenant_id is just a free form string ;(
    tenant_id = sa.Column(sa.String(255), nullable=False)


class IsHazTags(object):
    @declarative.declared_attr
    def tag_association_uuid(cls):
        return sa.Column(UUID, sa.ForeignKey("tag_associations.uuid"))

    @declarative.declared_attr
    def tag_association(cls):
        discriminator = cls.__name__.lower()
        cls.tags = associationproxy.association_proxy(
                    "tag_associations", "tags",
                    creator=TagAssociation.creator(discriminator)
                )
        backref = orm.backref("%s_parent" % discriminator, uselist=False)
        return orm.relationship("TagAssociation", backref=backref)


class TagAssociation(Base):
    __tablename__ = "tag_associations"
    discriminator = sa.Column(sa.String(255))

    @classmethod
    def creator(cls, discriminator):
        """Provide a 'creator' function to use with
        the association proxy."""

        return lambda tags: TagAssociation(tags=tags,
                                           discriminator=discriminator)


class Tag(Base):
    association_uuid = sa.Column(UUID,
                                 sa.ForeignKey("tag_associations.uuid"))
    tag = sa.Column(sa.String(255), nullable=False)


class DictListCollection(collections.MappedCollection):
    def __init__(self, keyfunc=None, data=None):
        if not keyfunc:
            self._keyfunc = lambda i: i.kind
        else:
            self._keyfunc = keyfunc

    @collections.collection.appender
    @collections.collection.internally_instrumented
    def set(self, item, _sa_initiator=None):
        key = self._keyfunc(item)
        if key not in self:
            self.__setitem__(key, [], _sa_initiator)
        self[key].append(item)

    @collections.collection.remover
    @collections.collection.internally_instrumented
    def remove(self, item, _sa_initiator=None):
        key = self._keyfunc(item)
        if key not in self:
            raise sa_exc.InvalidRequestError(
                "Can not remove '%s': key '%s' not in collection. "
                "Flush needed?" % (item, key))
        if item not in self[key]:
            raise sa_exc.InvalidRequestError(
                "Can not remove '%s': collection holds '%s' for key '%s'. "
                "Flush needed?" % (item, self[key], key))
        self[key].remove(item)
        if not self[key]:
            self.__delitem__(key, _sa_initiator)

    @collections.collection.converter
    def _convert(self, dictlist):
        def check_key(incoming_key, value, new_key):
            if incoming_key != new_key:
                raise TypeError(
                    "Found incompatible_key %r for value %r; this "
                    "collections keying function requires a key of "
                    "%r for this value." % (incoming_key, value, new_key))

        for incoming_key, value in dictlist.iteritems():
            if not isinstance(value, (list, set)):
                new_key = self._keyfunc(value)
                check_key(incoming_key, value, new_key)
                yield value
            else:
                for item in value:
                    new_key = self._keyfunc(item)
                    check_key(incoming_key, item, new_key)
                    yield item


class IsHazMetaIps(object):
    @declarative.declared_attr
    def meta_ips_association(cls):
        discriminator = cls.__name__.lower()
        creator = MetaIpAssociation.creator(discriminator)
        args = ("meta_ip_association", "meta_ips")
        cls.meta_ips = associationproxy.association_proxy(*args,
                                                          creator=creator)
        return orm.relationship("MetaIpAssociation",
                                collection_class=DictListCollection)


class MetaIpAssociation(Base):
    descriminator = sa.Column(sa.String(255), nullable=False)

    @classmethod
    def creator(cls, discr):
        return lambda meta_ips: MetaIpAssociation(meta_ips=meta_ips,
                                                  discriminator=discr)


class MetaIp(Base):
    @declarative.declared_attr
    def association_uuid(cls):
        return sa.Column(UUID, sa.ForeignKey("meta_ip_associations.uuid"))

    kind = sa.Column(sa.String(255), nullable=False)
    ip = sa.Column(INET, nullable=False)


class Subnet(Base, IsHazTenant):
    network_uuid = sa.Column(sa.String(36), sa.ForeignKey("networks.uuid"),
                             nullable=False)
    address = sa.Column(INET, nullable=False)
    prefix = sa.Column(sa.Integer, nullable=False)

    def as_netaddr(self):
        return netaddr.IPNetwork((self.address.value, self.prefix))


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

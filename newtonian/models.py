
import datetime
import logging
import re
import uuid

import netaddr

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext import associationproxy
from sqlalchemy.ext import declarative

from newtonian import custom_types as ct


log = logging.getLogger(__name__)


class NewtonianBase(object):
    uuid = sa.Column(ct.UUID, primary_key=True,
                     default=lambda: uuid.uuid4())
    created_at = sa.Column(sa.DateTime, default=datetime.datetime.utcnow)
    updated_at = sa.Column(sa.DateTime, default=datetime.datetime.utcnow,
                           onupdate=datetime.datetime.now)

    @declarative.declared_attr
    def __tablename__(cls):
        return cls.__collection_name__

    @declarative.declared_attr
    def __display_name__(cls):
        return re.sub(r"((?<=[a-z])[A-Z]|(?<!\A)[A-Z](?=[a-z]))",
                      r"_\1", cls.__name__).lower()

    @declarative.declared_attr
    def __collection_name__(cls):
        # NOTE(jkoelker) Pluralize the unCamelCased version of the class.
        #                Subclasses can still define __collect_name__ to
        #                override. Adapted from Kotti.util
        return cls.__display_name__ + 's'

    @property
    def __name__(self):
        return str(self.uuid)

    # TODO(jkoelker) This needs to be fixed
    def dictify(self, revisit=False, expand=None):
        res = {}
        props = sa.orm.object_mapper(self).iterate_properties
        for prop in props:
            if not isinstance(prop, sa.orm.ColumnProperty):
                continue
            key = prop.key
            value = getattr(self, key)
            if hasattr(value, "dict"):
                value = value.dict()
            elif isinstance(value, (datetime.datetime, uuid.UUID)):
                value = str(value)
            elif isinstance(value, list):
                newvalue = []
                for item in value:
                    if hasattr(item, "dict"):
                        newvalue.append(item.dict())
                    else:
                        newvalue.append(str(item))
                value = newvalue
            res[key] = value
        return res


Base = declarative.declarative_base(cls=NewtonianBase)


def _default_list_getset(collection_class, proxy):
    attr = proxy.value_attr

    def getter(obj):
        if obj:
            return getattr(obj, attr, None)
        return []

    if collection_class is dict:
        setter = lambda o, k, v: setattr(o, attr, v)
    else:
        setter = lambda o, v: setattr(o, attr, v)
    return getter, setter


def ForeignKey(where, nullable=False):
    return sa.Column(ct.UUID, sa.ForeignKey(where), nullable=nullable)


class IsHazTenant(object):
    """Teanant mixin to magically support the tenant_id"""
    # NOTE(jkoelker) tenant_id is just a free form string ;(
    tenant_id = sa.Column(sa.String(255), nullable=False)


class Tag(Base):
    association_uuid = ForeignKey("tag_association.uuid")

    tag = sa.Column(sa.String(255), nullable=False)
    parent = associationproxy.association_proxy("association", "parent")
    association = orm.relationship("TagAssociation",
                                   backref=orm.backref("tags_association"))


class TagAssociation(Base):
    __collection_name__ = "tag_association"

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
        return ForeignKey("tag_association.uuid", nullable=True)

    @declarative.declared_attr
    def tag_association(cls):
        discriminator = cls.__name__.lower()
        creator = TagAssociation.creator(discriminator)
        kwargs = {'creator': creator,
                  'getset_factory': _default_list_getset}
        cls.tags = associationproxy.association_proxy("tag_association",
                                                      "tags", **kwargs)
        backref = orm.backref("%s_parent" % discriminator, uselist=False)
        return orm.relationship("TagAssociation", backref=backref)


class MetaIp(Base):
    subnet_uuid = ForeignKey("subnets.uuid")
    ip = sa.Column(ct.INET)


class PortState(ct.DeclEnum):
    up = ('U', "Up")
    down = ('D', "Down")


class NetworkState(ct.DeclEnum):
    up = ('U', "Up")
    down = ('D', "Down")


class Route(Base, IsHazTags):
    subnet_uuid = ForeignKey("subnets.uuid")
    subnet = orm.relationship("Subnet", backref="routes")

    address = sa.Column(ct.INET, nullable=False)
    prefix = sa.Column(sa.Integer, nullable=False)
    next_hop = sa.Column(ct.INET, nullable=False)


class Subnet(Base, IsHazTenant, IsHazTags):
    network_uuid = ForeignKey("networks.uuid")
    network = orm.relationship("Network", backref="subnets")
    address = sa.Column(ct.INET, nullable=False)
    prefix = sa.Column(sa.Integer, nullable=False)
    dns = orm.relationship("MetaIp", backref=orm.backref("subnet",
                                                         uselist=False))
    unique = sa.Column(sa.Boolean, default=False)
    active = sa.Column(sa.Boolean, default=True)

    @property
    def netaddr(self):
        return netaddr.IPNetwork((self.address.value, self.prefix))

    @property
    def version(self):
        return self.address.version


class AllocatableIp(Base):
    __table_args__ = (sa.UniqueConstraint("address", "subnet_uuid"),)
    subnet_uuid = ForeignKey("subnets.uuid")
    subnet = orm.relationship("Subnet", backref="allocatable_ips")

    address = sa.Column(ct.INET, nullable=False)
    available = sa.Column(sa.Boolean, default=False)


class Ip(Base, IsHazTenant, IsHazTags):
    __table_args__ = (sa.UniqueConstraint("address", "subnet_uuid"),)

    subnet_uuid = ForeignKey("subnets.uuid")
    subnet = orm.relationship("Subnet", backref="ips")
    port_uuid = ForeignKey("ports.uuid", nullable=True)
    port = orm.relationship("Port", backref="ips")

    address = sa.Column(ct.INET, nullable=False)

    def deallocate(self, session=None):
        session = orm.session.object_session(self)

        allocatable_ip = AllocatableIp(subnet_uuid=self.subnet_uuid,
                                       address=self.address)
        session.add(allocatable_ip)
        session.delete(self)
        return allocatable_ip


class MacPool(Base):
    network_uuid = ForeignKey("networks.uuid", nullable=True)
    network = orm.relationship("Network", backref="mac_pools")
    address = sa.Column(ct.MAC, nullable=False)
    prefix = sa.Column(sa.Integer, nullable=False)


class AllocatableMac(Base):
    __table_args__ = (sa.UniqueConstraint("address", "network_uuid"),)

    network_uuid = ForeignKey("networks.uuid", nullable=True)
    network = orm.relationship("Network",
                               backref=orm.backref("allocatable_macs",
                                                   lazy="dynamic"))

    address = sa.Column(ct.INET, nullable=False)
    available = sa.Column(sa.Boolean, default=False)


class Mac(Base):
    __table_args__ = (sa.UniqueConstraint("address", "network_uuid"),)

    network_uuid = ForeignKey("networks.uuid", nullable=True)
    network = orm.relationship("Network")
    pool_uuid = ForeignKey("mac_pools.uuid")
    pool = orm.relationship("MacPool", backref="macs")
    port_uuid = ForeignKey("ports.uuid")
    port = orm.relationship("Port", uselist=False, backref="mac")

    address = sa.Column(ct.MAC, nullable=False)

    def deallocate(self):
        session = orm.session.object_session(self)

        kwargs = {"address": self.address}

        if self.pool.network_uuid is not None:
            kwargs["network_uuid"] = self.pool.network_uuid

        allocatable_mac = AllocatableMac(**kwargs)
        session.add(allocatable_mac)
        session.delete(self)
        return allocatable_mac


class Port(Base, IsHazTenant, IsHazTags):
    network_uuid = ForeignKey("networks.uuid", nullable=True)
    network = orm.relationship("Network",
                               backref=orm.backref("ports",
                                                   lazy="dynamic"))

    device_id = sa.Column(sa.String(255), nullable=False)
    state = sa.Column(PortState.db_type())


class Network(Base, IsHazTenant, IsHazTags):
    name = sa.Column(sa.String(255), nullable=False)
    state = sa.Column(NetworkState.db_type())
    key = sa.Column(sa.String(255))
    parent_uuid = ForeignKey("networks.uuid", nullable=True)
    children = orm.relationship("Network", lazy="joined", join_depth=2)

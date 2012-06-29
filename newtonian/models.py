
import datetime
import re
import uuid

import netaddr

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext import associationproxy
from sqlalchemy.ext import declarative

from newtonian import custom_types as ct


class NewtonianBase(object):
    uuid = sa.Column(ct.UUID, primary_key=True,
                     default=lambda: uuid.uuid4())
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
    tag_association_uuid = ForeignKey("tag_association.uuid")

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

    @property
    def netaddr(self):
        return netaddr.IPNetwork((self.address.value, self.prefix))

    @property
    def version(self):
        return self.address.version


class Ip(Base, IsHazTenant, IsHazTags):
    __table_args__ = (sa.UniqueConstraint("address", "subnet_uuid"),)

    subnet_uuid = ForeignKey("subnets.uuid")
    subnet = orm.relationship("Subnet", backref="ips")
    port_uuid = ForeignKey("ports.uuid", nullable=True)
    port = orm.relationship("Port", backref="ips")

    address = sa.Column(ct.INET, nullable=False)


class MacPool(Base):
    network_uuid = ForeignKey("networks.uuid", nullable=True)
    network = orm.relationship("Network", backref="mac_pools")
    address = sa.Column(ct.MAC, nullable=False)
    prefix = sa.Column(sa.Integer, nullable=False)


class Mac(Base):
    port_uuid = ForeignKey("ports.uuid")
    port = orm.relationship("Port", userlist=False, backref="mac")

    address = sa.Column(ct.MAC, nullable=False)


class Port(Base, IsHazTenant, IsHazTags):
    network_uuid = ForeignKey("networks.uuid", nullable=True)
    network = orm.relationship("Network", backref="ports")

    device_id = sa.Column(sa.String(255), nullable=False)
    state = sa.Column(PortState.db_type())


class Network(Base):
    name = sa.Column(sa.String(255), nullable=False)
    state = sa.Column(NetworkState.db_type())

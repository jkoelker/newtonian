from zope import interface


class INetwork(interface.Interface):
    request = interface.Attribute('The request object')
    network = interface.Attribute('The network model object')


class IBeforeNetworkCreate(INetwork):
    """
    Event issued prior to the network model being persisted.
    """


class INetworkCreted(INetwork):
    """
    Event issued after the network model being persisted.
    """

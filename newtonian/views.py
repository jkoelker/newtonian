import cornice


def resource(name, collection_name=None):
    if collection_name is None:
        collection_name = name + 's'
    c = cornice.Service(name=collection_name, path='/%s' % collection_name)
    r = cornice.Service(name=name, path='/%s/{id}' % collection_name)
    return c, r


networks, network = resource('network')
ports, port = resource('port')
subnets, subnet = resource('subnet')
routes, route = resource('route')
ips, ip = resource('ip')


def get_info(request):
    """Returns Hello in JSON."""
    return {'Hello': 'World'}

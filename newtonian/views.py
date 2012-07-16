import cornice

from newtonian import models
from newtonian import sqla


def _get_session(request):
    return sqla.dbsession(request)


def _resource(name, collection_name=None):
    if collection_name is None:
        collection_name = name + 's'
    c = cornice.Service(name=collection_name, path='/%s' % collection_name)
    r = cornice.Service(name=name, path='/%s/{id}' % collection_name)
    return c, r


networks, network = _resource('network')
ports, port = _resource('port')
subnets, subnet = _resource('subnet')
routes, route = _resource('route')
ips, ip = _resource('ip')


@networks.get()
def get_networks(request):
    session = _get_session(request)

    query = session.query(models.Network)
    return {'networks': [n.dict() for n in query.all()]}

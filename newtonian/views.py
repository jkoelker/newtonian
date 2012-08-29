import cornice
from pyramid import httpexceptions as httpexc
from pyramid import view

from newtonian import models
from newtonian import sqla


@view.view_config(context=httpexc.WSGIHTTPException)
def _format_exception(exc, request):
    request.response_status = exc.status
    return {'code': exc.code, 'title': exc.title,
            'explanation': exc.explanation, 'detail': exc.detail}


def _get_session(request):
    return sqla.dbsession(request)


def _resource(name, collection_name=None):
    if collection_name is None:
        collection_name = name + 's'
    c = cornice.Service(name=collection_name, path='/%s' % collection_name)
    r = cornice.Service(name=name, path='/%s/{uuid}' % collection_name)
    return c, r


networks, network = _resource('network')
ports, port = _resource('port')
subnets, subnet = _resource('subnet')
routes, route = _resource('route')
ips, ip = _resource('ip')


def _object(obj, collection=False):
    value = obj.dictify()
    if collection:
        return value
    return {obj.__display_name__: value}


def _collection(col, model):
    return {model.__collection_name__: [_object(obj, col) for obj in col]}


def _get_network(uuid, session):
    query = session.query(models.Network)
    network = query.filter_by(uuid=uuid).first()
    if not network:
        raise httpexc.HTTPNotFound()
    return network


@networks.get()
def get_networks(request):
    session = _get_session(request)

    query = session.query(models.Network)
    return _collection(query.all(), models.Network)


@networks.post()
def create_network(request):
    session = _get_session(request)
    body = request.json_body
    if 'networks' in body:
        networks = [models.Network(**n) for n in body['networks']]
    elif isinstance(body, list):
        networks = [models.Network(**n) for n in body]
    else:
        networks = [models.Network(**body)]
    session.add_all(networks)
    session.flush()
    if len(networks) == 1:
        return _object(networks[0])
    return _collection(networks, models.Network)


@network.get()
def get_network(request):
    uuid = request.matchdict['uuid']
    session = _get_session(request)
    network = _get_network(uuid, session)
    return _object(network)


@network.delete()
def delete_network(request):
    uuid = request.matchdict['uuid']
    session = _get_session(request)
    network = _get_network(uuid, session)
    session.delete(network)
    return httpexc.HTTPNoContent()

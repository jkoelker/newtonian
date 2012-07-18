import cornice
from pyramid import httpexceptions as httpexc
from pyramid import response
from pyramid import view

from newtonian import models
from newtonian import sqla


class JSONException(httpexc.HTTPError):
    def __init__(self, exc):
        body = {'status': 'error', 'errors': errors}
        response.Response.__init__(self, json.dumps(body, use_decimal=True))
        self.status = status
        self.content_type = 'application/json'

#class HTTPExceptionRenderer(object):
#        def __call__(self, info):
#            def _render(value, system):


#@view.view_config(context=httpexc.WSGIHTTPException,
#                  renderer=HTTPExceptionRenderer)
#def _format_exception(exc, request):
#    return {'code': exc.code, 'title': exc.title,
#            'explanation': exc.explanation}


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


class Resource(dict):
    pass


class Collection(Resource):
    def __init__(self, model):
        self.model = model
        super(Collection, self).__init__()

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

import logging

from pyramid import renderers
from pyramid import interfaces as pyramid_interfaces
from zope.interface import registry


try:
    json_factory = renderers.JSON()
except AttributeError:
    json_factory = renderers.json_renderer_factory


_DEFAULT_SERIALIZERS = (('application/json', json_factory(None)), )
_MARKER = object()
LOG = logging.getLogger(__name__)


class Newtonian(object):
    def __init__(self, serializers=_DEFAULT_SERIALIZERS):
        self.components = registry.Components()
        self.content_types = []

        for content_type, serializer in serializers:
            self.add_serializer(content_type, serializer)

    def add_serializer(self, content_type, serializer):
        self.content_types.append(content_type)
        self.components.registerUtility(serializer,
                                        pyramid_interfaces.IRenderer,
                                        content_type)

    def get_serializer(self, content_type):
        result = self.components.queryUtility(pyramid_interfaces.IRenderer,
                                              content_type,
                                              default=_MARKER)
        if result is _MARKER:
            msg = 'No renderer for content-type: %s' % content_type
            raise TypeError(msg)
        return result

    def __call__(self, info):
        default_content_type = info.settings.get('default_content_type',
                                                 'application/json')

        def _render(value, system):
            LOG.debug(value)
            request = system.get('request')
            response = request.response

            content_type = request.accept.best_match(self.content_types,
                                                     default_content_type)
            response.content_type = content_type
            serializer = self.get_serializer(content_type)
            return serializer(value, system)

        return _render

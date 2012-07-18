from zope.interface import registry


from pyramid import renderers
from pyramid import interfaces as pyramid_interfaces


_DEFAULT_SERIALIZERS = (('application/json', renderers.JSON()), )
_MARKER = object()


class Newtonian(object):
    def __init__(self, serializers=_DEFAULT_SERIALIZERS):
        self.components = registry.Components()
        self.content_types = []

        for content_type, serializer in serializers:
            self.add_serializer(content_type, serializer)

    def add_serializer(self, content_type, serializer):
        self.content_types.append(content_type)
        self.components.registerAdapter(serializer, (content_type, ),
                                        pyramid_interfaces.IRenderer)

    def get_serializer(self, content_type):
        adapters = self.components.adapters
        result = adapters.lookup(content_type,
                                 pyramid_interfaces.IRenderer,
                                 default=_MARKER)
        if result is _MARKER:
            msg = 'No renderer for content-type: %s' % content_type
            raise TypeError(msg)
        return result

    def __call__(self, info):
        settings = info['settings']
        default_content_type = settings.get('default_content_type',
                                            'application/json')

        def _render(value, system):
            request = system.get('request')
            content_type = request.accept.best_match(self.content_types,
                                                     default_content_type)
            serializer = self.get_serializer(content_type)
            return serializer(value, system)

        return _render

from newtonian import sqla

class Resource(dict):
    def __init__(self, request, name, parent, model, column, filter):
        super(dict, self).__init__()
        self.__name__ = __name__
        self.__parent__ = parent
        self.__model__ = model
        self.__column__ = column
        self.__filter__ = filter

    def __getitem__(self, key):
        if key in self:
            return super(dict, self).__getitem__(key)

        session = sqla.dbsession(request)




def get_root(request):
    pass

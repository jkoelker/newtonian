"""Main entry point
"""
from pyramid.config import Configurator
from newtonian import models
from newtonian import renderers
from newtonian import sqla


def main(global_config, **settings):
    settings = dict(settings)
    settings.setdefault(sqla.SQLALCHEMY_URL, "sqlite:///newtonian.db")

    config = Configurator(settings=settings)

    config.include("pyramid_tm")
    sqla._setup_factory(config.registry)

    config.include("cornice")
    config.scan("newtonian.views")
    config.add_renderer(None, renderers.Newtonian())

    # NOTE(jkoelker) Ghetto db creation, fixit, fixit, fixit, fixit
    s = config.registry.settings
    models.Base.metadata.bind = s[sqla.DBSESSION_ENGINE]
    models.Base.metadata.create_all(s[sqla.DBSESSION_ENGINE])

    return config.make_wsgi_app()

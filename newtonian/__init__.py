"""Main entry point
"""
from pyramid.config import Configurator
from newtonian import sqla


def main(global_config, **settings):
    settings = dict(settings)
    settings.setdefault(sqla.SQLALCHEMY_URL, "sqlite:///newtonian.db")

    config = Configurator(settings=settings)

    config.include("pyramid_tm")
    sqla._setup_factory(config.registry)

    config.include("cornice")
    config.scan("newtonian.views")

    return config.make_wsgi_app()

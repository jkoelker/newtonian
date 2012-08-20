""" Setup file.
"""
import os
from setuptools import setup, find_packages

here = os.path.abspath(os.path.dirname(__file__))

with open(os.path.join(here, "README.rst")) as f:
    README = f.read()

install_requires = ["cornice",
                    "PasteScript",
                    "zope.sqlalchemy",
                    "sqlalchemy>=0.7",
                    "colanderalchemy",
                    "pyramid_tm",
                    "netaddr"]


setup(name="newtonian",
    version=0.1,
    description="A concrete implementation of NaaS",
    long_description=README,
    classifiers=[
        "Programming Language :: Python",
        "Framework :: Pylons",
        "Topic :: Internet :: WWW/HTTP",
        "Topic :: Internet :: WWW/HTTP :: WSGI :: Application"
    ],
    keywords="web services",
    author="",
    author_email=" -at- example.com",
    url="http://example.com",
    packages=find_packages(),
    include_package_data=True,
    zip_safe=False,
    install_requires=install_requires,
    entry_points="""\
    [paste.app_factory]
    main = newtonian:main
    """,
    paster_plugins=["pyramid"],
)

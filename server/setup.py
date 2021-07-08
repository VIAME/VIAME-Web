#!/usr/bin/env python
# -*- coding: utf-8 -*-

from setuptools import find_packages, setup

requirements = [
    "cheroot>=8.4.5",  # https://github.com/cherrypy/cheroot/issues/312
    "click",
    "girder==3.1.5.dev8",
    "diva-boiler",
    "girder_jobs==3.0.3",
    "girder_worker==0.8.1",
    "girder_worker_utils==0.8.5",
    "pydantic==1.8.2",
    "pyrabbit2==1.0.7",  # For rabbitmq_user_queues plugin
    "pysnooper",
    "typing_extensions",
    "gputil",
    # botocore requirement conflict
    "requests>=2.20.0",  # Match girder_worker_utils
    "urllib3<1.26",
]

dev_requirements = [
    "black>=20.8b0",
    "flake8",
    "isort",
    "mkdocs",
    "mkdocs-material",
    "mypy",
    "pytest",
    "ipykernel",
    "tabulate",
    "opencv-python",
    "python-dotenv",
    "pytest-cov",
    "tox",
]

setup(
    author_email="viame-web@kitware.com",
    classifiers=[
        "License :: OSI Approved :: Apache Software License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
    ],
    description="DIVE Data Server",
    install_requires=requirements,
    python_requires=">=3.7",
    extra_require={"dev": dev_requirements},
    license="Apache Software License 2.0",
    package_data={
        "": ["**/*.mako"],
    },
    keywords="DIVE, VIAME, VIAME-Web, Annotation",
    name="dive_server",
    packages=find_packages(exclude=["test", "test.*"]),
    url="https://github.com/Kitware/dive",
    version="1.4.1",
    zip_safe=False,
    entry_points={
        "console_scripts": ["dive=scripts.cli:cli"],
        "girder.plugin": [
            "dive_server = dive_server:GirderPlugin",
            "bucket_notifications = bucket_notifications:GirderPlugin",
            "rabbit_user_queues = rabbitmq_user_queues:GirderPlugin",
        ],
        "girder_worker_plugins": ["dive_tasks = dive_tasks:DIVEPlugin"],
    },
)

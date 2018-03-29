from setuptools import setup

setup(
    name='socialcar',
    packages=[ 'socialcar' ],
    include_package_data=True,
    install_requires=[
        'eve',
        'eve-docs',
        'flask-cors',
        'flask-bootstrap',
        'requests',
    ],
)
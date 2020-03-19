from distutils.core import setup

setup(
    name =             'oclude',
    version =          '0.9',
    description =      'OpenCL Universal Driving Environment',
    long_description = 'An OpenCL driver to test and run standalone kernels on arbitrary devices',
    author =           'Sotiris Niarchos',
    author_email =     'sot.niarchos@gmail.com',
    url =              'https://github.com/zehanort/oclude',

    py_modules =       ['oclude'],
    install_requires = ['pycparser>=2.18,<2.20', 'pycparserext==2019.1'],
    entry_points =     { 'console_scripts': ['oclude=oclude:run'] },
    packages =         ['utils']
)

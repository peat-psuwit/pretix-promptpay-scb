import os
from distutils.command.build import build

from django.core import management
from setuptools import find_packages, setup

from pretix_promptpay_scb import __version__


try:
    with open(os.path.join(os.path.dirname(__file__), 'README.rst'), encoding='utf-8') as f:
        long_description = f.read()
except:
    long_description = ''


class CustomBuild(build):
    def run(self):
        management.call_command('compilemessages', verbosity=1)
        build.run(self)


cmdclass = {
    'build': CustomBuild
}


setup(
    name='pretix-promptpay-scb',
    version=__version__,
    description='Pretix payment plugin for Thai PromptPay QR code, using SCB API',
    long_description=long_description,
    url='GitHub repository URL',
    author='Ratchanan Srirattanamet',
    author_email='peat@peat-network.xyz',
    license='Apache',

    install_requires=[],
    packages=find_packages(exclude=['tests', 'tests.*']),
    include_package_data=True,
    cmdclass=cmdclass,
    entry_points="""
[pretix.plugin]
pretix_promptpay_scb=pretix_promptpay_scb:PretixPluginMeta
""",
)

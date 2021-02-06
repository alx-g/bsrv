import atexit
import os
import sys

import setuptools
from setuptools.command.install import install

SERVICE_FILE_PREFIX = 'lib/systemd/system'


def find_prefix():
    for p in sys.path:
        if os.path.isdir(p) and 'bsrv' in os.listdir(p):
            return os.path.abspath(os.path.join(p, '../../../'))


def _post_install():
    prefix = find_prefix()

    files = ['bsrvd.service', 'bsrvstatd.service']
    paths = [os.path.join(prefix, SERVICE_FILE_PREFIX, f) for f in files]

    for p in paths:
        cnt = ''
        with open(p, 'r') as f:
            cnt = f.read()
        cnt_new = cnt.replace('{{INSTALL_PREFIX}}', prefix)
        with open(p, 'w') as f:
            f.write(cnt_new)


class NewInstall(install):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        atexit.register(_post_install)


with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="bsrv",
    version="0.0.1a6",
    author="Alexander Grathwohl",
    author_email="alex.grathwohl@gmail.com",
    description="Linux daemon to manage periodic borg backups",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="",
    license="BSD 3-Clause",
    packages=setuptools.find_packages(),
    py_modules=["bsrvd", "bsrvcli", "bsrvtray", "bsrvstatd"],
    classifiers=[
        # How mature is this project? Common values are
        #   3 - Alpha
        #   4 - Beta
        #   5 - Production/Stable
        'Development Status :: 2 - Pre-Alpha',

        'Topic :: System :: Archiving :: Backup',

        'License :: OSI Approved :: BSD License',

        'Operating System :: POSIX :: Linux',

        # Specify the Python versions you support here. In particular, ensure
        # that you indicate whether you support Python 2, Python 3 or both.
        'Programming Language :: Python :: 3 :: Only',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
    ],
    python_requires='>=3.7',
    install_requires=["dasbus", "PyGObject", "systemd-logging"],
    entry_points={
        'console_scripts': [
            'bsrvd=bsrvd:main',
            'bsrvcli=bsrvcli:main',
            'bsrvtray=bsrvtray:main',
            'bsrvstatd=bsrvstatd:main'
        ],
    },
    package_data={'bsrv': ['icons/*']},
    data_files=[('share/dbus-1/system-services', ['configs/dbus/de.alxg.bsrvd.service']),
                ('share/dbus-1/system.d', ['configs/dbus/de.alxg.bsrvd.conf']),
                (SERVICE_FILE_PREFIX, ['configs/systemd/bsrvd.service']),
                (SERVICE_FILE_PREFIX, ['configs/systemd/bsrvstatd.service'])],
    cmdclass={
        'install': NewInstall
    }
)

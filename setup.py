import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="bsrv",
    version="0.0.1a4",
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
                ('lib/systemd/system', ['configs/systemd/bsrvd.service'])]
)

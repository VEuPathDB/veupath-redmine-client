from setuptools import setup

setup(
    name='Veupath-Redmine-Client',
    version='0.1.0',
    description='A VeupathDB specific Redmine client',
    url='https://github.com/VEuPathDBveupath-redmine-client',
    author='Matthieu Barba',
    author_email='mbarba@ebi.ac.uk',
    license='Apache Software License',
    packages=['lib/veupathdb'],
    install_requires=['python-redmine'],

    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.8',
    ],
)

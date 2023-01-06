from setuptools import setup

setup(
    name='veupath-redmine-client',
    version='0.1.0',
    description='A VeupathDB specific Redmine client',
    url='https://github.com/VEuPathDB/veupath-redmine-client',
    author='Matthieu Barba',
    author_email='mbarba@ebi.ac.uk',
    license='Apache Software License',
    packages=['veupath/redmine/client'],
    install_requires=['python-redmine', 'wheel', 'biopython'],

    scripts=['scripts/check_genome_issues.py',
             'scripts/check_rnaseq_issues.py',
             'scripts/check_missed_issues.py',
             'scripts/check_organism_abbrevs.py',
             'scripts/check_single_issue.py'
             ],

    classifiers=[
        'Development Status :: 1 - Planning',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 3.8',
    ],
)

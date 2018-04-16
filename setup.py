from distutils.core import setup
setup(
    name = 'python-snake',
    packages = ['snake'],
    version = "0.0.7",
    description = 'Data workflow tool (rough copy of drake for python)',
    author = "Jason Trigg",
    author_email = "jasontrigg0@gmail.com",
    url = "https://github.com/jasontrigg0/snake",
    download_url = 'https://github.com/jasontrigg0/snake/tarball/0.0.7',
    scripts=['snake/snake'],
    install_requires=[
        "six"
    ],
    keywords = [],
    classifiers = [],
)

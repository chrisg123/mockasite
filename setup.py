from setuptools import setup, find_packages

setup(
    name='mockasite',
    version='0.1.0',
    packages=find_packages(),
    entry_points={
        'console_scripts': [
            'mockasite=mockasite.mockasite:main',
        ]
    },
    author='chrisg123',
    description="Record and serve back a mock version of a website.",
    url="https://github.com/chrisg123/mockasite"
)

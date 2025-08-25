from setuptools import setup, find_packages
setup(
    name='multi-eden',
    version='0.1.0',
    package_dir={'': 'src'},
    packages=find_packages(where='src'),
    description='A reusable Python library.',
    author='Your Name',
    author_email='youremail@example.com',
    install_requires=[
        'invoke>=2.0.0',
        'pyyaml>=6.0',
        'PyJWT>=2.0.0',
        'requests>=2.25.0',
        'firebase-admin>=5.0.0',
        'pydantic>=2.0.0',
        'google-genai>=0.3.0',
        'pathlib2;python_version<"3.4"',  # pathlib is built-in in Python 3.4+
    ],
)

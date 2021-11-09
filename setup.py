from setuptools import setup, find_packages

version = "0.0.1"

with open("OSS_VERSION", "rt") as f:
    mf_version = f.read()

setup(
    name="mycompany-metaflow",
    version=version,
    description="Metaflow Custom Extensions",
    author="Your team name",
    author_email="team@company.com",
    packages=find_packages(),
    py_modules=[
        "metaflow_extensions",
    ],
    install_requires=[
        # CONFIGURE: You can list any additional requirements for your
        # extensions here
        # Preferred: Pin a version of metaflow here.
        "metaflow=%s"
        % mf_version
    ],
)

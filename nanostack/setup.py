from setuptools import setup, find_packages

setup(
    name="nanostack",
    version="1.0.0",
    author="Your Name",
    author_email="you@email.com",
    description="Build Android apps without Java, Gradle or Android Studio",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourname/nanostack",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "nanostack": [
            "bin/runner.apk",
            "bin/aapt2",
            "bin/aapt2.exe",
            "bin/apksigner.jar",
            "templates/starter.nano",
        ]
    },
    install_requires=[
        "click>=8.0",
        "colorama>=0.4",
        "pyyaml>=6.0",
        "rich>=13.0",
    ],
    entry_points={
        "console_scripts": [
            "nano=nano_cli.nano:cli",
        ]
    },
    python_requires=">=3.8",
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: Software Development :: Build Tools",
        "Topic :: Software Development :: Compilers",
    ],
)

from setuptools import setup

setup(
    name="core-email-dedup",
    version="1.0.0",
    description="Email Transfer & Deduplication Tool by CORE SYSTEMS",
    author="CORE SYSTEMS",
    py_modules=["email_dedup"],
    python_requires=">=3.8",
    entry_points={
        "console_scripts": [
            "core-email-dedup=email_dedup:main",
        ],
    },
)

#!/bin/sh -e

if [ ! -f scripts/upload_to_pypi.sh -o ! -f setup.py ]; then
	echo "Please run from top dir of repository" >&2
	exit 1
fi

rm -rf dist
python3 setup.py sdist bdist_wheel
twine upload -s dist/*

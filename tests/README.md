# Running the tests

To run the tests inside the same environment as they are executed on gh workflow,
you need a [Docker](https://www.docker.com/) installation. This will also launch an extra container
with a database, so your own postgres installation is not affected at all.

To run the tests, go to the main directory of the project and do

```sh
export QGIS_TEST_VERSION=latest # See https://hub.docker.com/r/qgis/qgis/tags/
export GITHUB_WORKSPACE=$PWD # only for local execution
docker run -v ${GITHUB_WORKSPACE}:/usr/src -w /usr/src opengisch/qgis:${QGIS_TEST_VERSION} sh -c 'xvfb-run pytest-3'
```

In one line, removing all containers.
```sh
QGIS_TEST_VERSION=latest GITHUB_WORKSPACE=$PWD docker run -v ${GITHUB_WORKSPACE}:/usr/src -w /usr/src opengisch/qgis:${QGIS_TEST_VERSION} sh -c 'xvfb-run pytest-3'
```

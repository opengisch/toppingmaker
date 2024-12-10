# Running the tests

To run the tests inside the same environment as they are executed on gh workflow,
you need a [Docker](https://www.docker.com/) installation. This will also launch an extra container
with a database, so your own postgres installation is not affected at all.

To run the tests, go to the main directory of the project and do

In one line, removing all containers.
```sh
docker run -v $PWD:/usr/src -w /usr/src opengisch/qgis:latest sh -c 'xvfb-run pytest-3'
```

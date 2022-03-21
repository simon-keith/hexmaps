from hexmaps.earth.overpass.api import OverpassAPI
from pytest import fixture


@fixture(scope="session")
def overpass() -> OverpassAPI:
    return OverpassAPI()

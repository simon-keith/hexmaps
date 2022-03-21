import pyproj

WGS84_CRS = pyproj.CRS("OGC:CRS84")
WGS84_GEOD = WGS84_CRS.get_geod()

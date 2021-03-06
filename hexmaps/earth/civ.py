from enum import Enum


class Terrain(str, Enum):
    OCEAN = "TERRAIN_OCEAN"
    COAST = "TERRAIN_COAST"
    DESERT = "TERRAIN_DESERT"
    DESERT_HILLS = "TERRAIN_DESERT_HILLS"
    DESERT_MOUNTAIN = "TERRAIN_DESERT_MOUNTAIN"
    PLAINS = "TERRAIN_PLAINS"
    PLAINS_HILLS = "TERRAIN_PLAINS_HILLS"
    PLAINS_MOUNTAIN = "TERRAIN_PLAINS_MOUNTAIN"
    GRASS = "TERRAIN_GRASS"
    GRASS_HILLS = "TERRAIN_GRASS_HILLS"
    GRASS_MOUNTAIN = "TERRAIN_GRASS_MOUNTAIN"
    TUNDRA = "TERRAIN_TUNDRA"
    TUNDRA_HILLS = "TERRAIN_TUNDRA_HILLS"
    TUNDRA_MOUNTAIN = "TERRAIN_TUNDRA_MOUNTAIN"
    SNOW = "TERRAIN_SNOW"
    SNOW_HILLS = "TERRAIN_SNOW_HILLS"
    SNOW_MOUNTAIN = "TERRAIN_SNOW_MOUNTAIN"


class Feature(str, Enum):
    REEF = "FEATURE_REEF"
    OASIS = "FEATURE_OASIS"
    FLOODPLAINS = "FEATURE_FLOODPLAINS"
    FLOODPLAINS_PLAINS = "FEATURE_FLOODPLAINS_PLAINS"
    FLOODPLAINS_GRASSLAND = "FEATURE_FLOODPLAINS_GRASSLAND"
    MARSH = "FEATURE_MARSH"
    JUNGLE = "FEATURE_JUNGLE"
    FOREST = "FEATURE_FOREST"
    GEOTHERMAL_FISSURE = "FEATURE_GEOTHERMAL_FISSURE"
    VOLCANO = "FEATURE_VOLCANO"
    ICE = "FEATURE_ICE"

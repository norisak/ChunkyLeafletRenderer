import math

from config import Config


def get_tile_for_chunk(config: Config, chunk_x, chunk_z):
    """
    Returns top-left-most (lowest x/y) tile the chunk is in at the y=0 plane.
    """
    tile_x = chunk_x - (chunk_z + chunk_x) / 2
    tile_y = (chunk_z + chunk_x) / 4 + 0.5

    return math.floor(tile_x), math.floor(tile_y)


def get_camera_pos_of_tile(config: Config, tile_x, tile_y):
    center_x = tile_x + 2 * tile_y
    center_y = -tile_x + 2 * tile_y
    return center_x * 16.0, 0.0, center_y * 16.0


def get_chunks_for_tile(config: Config, tile_x: int, tile_y: int):
    """
    Returns the set of chunks that are visible in the tile at the y=0 plane.
    """
    center_x = tile_x + 2 * tile_y
    center_y = -tile_x + 2 * tile_y

    return {
        (center_x-2, center_y-1),
        (center_x-1, center_y-2),
        (center_x-1, center_y-1),
        (center_x-1, center_y),
        (center_x, center_y-1),
        (center_x, center_y),
        (center_x, center_y+1),
        (center_x+1, center_y),
    }


def get_tiles_for_chunk(config: Config, chunk_x: int, chunk_z: int) -> set[tuple[int, int]]:
    """
    Returns the set of tiles that the chunk is visible in.
    """
    base_tile_x, base_tile_y = get_tile_for_chunk(config, chunk_x, chunk_z)
    width = 2 if (chunk_x + chunk_z) % 2 == 1 else 1

    base_tile_y -= config.tile_padding_top
    height = config.tile_padding_top + config.tile_padding_bottom + 1

    tile_set = set()

    for x in range(base_tile_x, base_tile_x + width):
        for y in range(base_tile_y, base_tile_y + height):
            tile_set.add((x, y))

    return tile_set


def get_chunkset_for_tile(config: Config, tile_x, tile_z):
    base_x = tile_x - config.tile_border_size
    base_z = tile_z - config.tile_border_size - config.tile_padding_top

    width = config.tile_border_size * 2 + 1
    height = width + config.tile_padding_top + config.tile_padding_bottom

    chunkset = set()

    for i in range(width):
        for j in range(height):
            chunkset = chunkset.union(get_chunks_for_tile(config, base_x+i, base_z+j))
    return chunkset


def get_chunklist_for_tile(config: Config, tile_x, tile_z):
    return sorted(list(get_chunkset_for_tile(config, tile_x, tile_z)))

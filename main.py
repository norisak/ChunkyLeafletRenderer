import subprocess
import json
import io
import sqlite3
import argparse

import fs
import time
import itertools

import nbt
import numpy as np
from PIL import Image

from config import Config
from tile_math import get_camera_pos_of_tile, get_tiles_for_chunk, get_chunkset_for_tile, get_chunklist_for_tile
from image import ImageHandler, PngImageHandler, AvifImageHandler


def get_chunklist(config: Config, batch_x, batch_y):
    base_x = batch_x * config.tile_batch_size - config.tile_border_size
    base_y = batch_y * config.tile_batch_size - config.tile_border_size - config.tile_padding_top

    width = config.tile_batch_size + config.tile_border_size * 2 + 1
    height = width + config.tile_padding_top + config.tile_padding_bottom

    chunkset = set()

    for i in range(width):
        for j in range(height):
            chunkset = chunkset.union(get_chunkset_for_tile(config, base_x+i, base_y+j))
    return sorted(list(chunkset))


def run_chunky(config: Config, chunky_args: list[str]):
    args = ["java", f"-Dchunky.home={config.chunky_home_path}", "-jar", "chunky/ChunkyLauncher.jar", f"-threads", str(config.threads)]
    for arg in chunky_args:
        args.append(arg)
    subprocess.Popen(args).wait()


def create_scene(config: Config, batch_x, batch_y, tile_x, tile_y, chunk_set, reset=False):
    scene = json.load(open("default_settings.json", "r"))

    scenes = fs.open_fs("")
    scenes.makedirs("chunky/scenes/"+config.scene_name, recreate=True)
    scene_fs = scenes.opendir("chunky/scenes/"+config.scene_name)

    if scene_fs.exists(config.scene_name+".dump"):
        scene_fs.remove(config.scene_name+".dump")
    if reset and scene_fs.exists(config.scene_name+".octree2"):
        scene_fs.remove(config.scene_name+".octree2")

    camera = scene["camera"]
    camera["projectionMode"] = "PARALLEL"
    camera["dof"] = "Infinity"
    camera["focalOffset"] = 0.0
    camera["shift"]["x"] = 0.0
    camera["shift"]["y"] = 0.0
    scene["spp"] = 0
    scene["sppTarget"] = config.samples_per_pixel
    scene["name"] = config.scene_name
    scene["width"] = config.tile_pixel_size * config.tile_render_batch_size
    scene["height"] = config.tile_pixel_size * config.tile_render_batch_size
    scene["chunkList"] = [x for x in get_chunklist(config, batch_x, batch_y) if x in chunk_set]
    scene["entities"] = []
    scene["actors"] = []
    scene["world"]["path"] = config.world_path

    scene["waterOpacity"] = 0.42
    scene["waterVisibility"] = 15.0

    center_tile_x = tile_x + (config.tile_render_batch_size - 1) / 2
    center_tile_y = tile_y + (config.tile_render_batch_size - 1) / 2

    camera_x, camera_y, camera_z = get_camera_pos_of_tile(config, center_tile_x, center_tile_y)

    camera["position"]["x"] = camera_x
    camera["position"]["y"] = camera_y
    camera["position"]["z"] = camera_z
    camera["fov"] = 22.625 * config.tile_render_batch_size

    scene_fs.writebytes(config.scene_name + ".json", json.dumps(scene).encode("utf-8"))


def list_regions(config: Config):
    world_fs = fs.open_fs(config.world_path)
    regions = world_fs.listdir("region")
    regions = [region for region in regions if region.endswith(".mca")]
    regions = [(int(region.split(".")[1]), int(region.split(".")[2])) for region in regions]
    return regions


def run_batch(
        config: Config,
        image_handler: ImageHandler,
        batch_x,
        batch_y,
        chunk_set,
        tiles_to_render,
        cur: sqlite3.Cursor,
        tile_last_modified,
        zoom_tiles_to_render: set[tuple[int, int, int]]
):
    first = True

    scene_fs = fs.open_fs("chunky/scenes/" + config.scene_name, create=True)
    for sub_x in range(config.tile_batch_size//config.tile_render_batch_size):
        for sub_y in range(config.tile_batch_size//config.tile_render_batch_size):
            tile_x = batch_x * config.tile_batch_size + sub_x * config.tile_render_batch_size
            tile_y = batch_y * config.tile_batch_size + sub_y * config.tile_render_batch_size

            render_batch_tile_set = {(tile_x + x, tile_y + y) for x, y in itertools.product(range(config.tile_render_batch_size), range(config.tile_render_batch_size))}

            if len(render_batch_tile_set & tiles_to_render) == 0:
                continue

            create_scene(config, batch_x, batch_y, tile_x, tile_y, chunk_set, reset=first)
            first = False
            run_chunky(
                config,
                ["-f", "-render", "chunky/scenes/" + config.scene_name + "/" + config.scene_name + ".json"]
            )
            move_image(
                config,
                image_handler,
                scene_fs,
                tile_x,
                tile_y,
                config.samples_per_pixel,
                tiles_to_render,
                cur,
                tile_last_modified,
                zoom_tiles_to_render
            )


def move_image(
        config: Config,
        image_handler: ImageHandler,
        scene_fs,
        base_tile_x,
        base_tile_y,
        spp,
        tiles_to_render,
        cur: sqlite3.Cursor,
        tile_last_modified,
        zoom_tiles_to_render: set[tuple[int, int, int]]
):
    chunky_image_file = scene_fs.open(f"snapshots/{config.scene_name}-{spp}.png", "rb")

    image = Image.open(chunky_image_file)

    tiles_rendered = []

    for sub_x, sub_y in itertools.product(range(config.tile_render_batch_size), range(config.tile_render_batch_size)):
        tile_x = base_tile_x + sub_x
        tile_y = base_tile_y + sub_y
        if (tile_x, tile_y) not in tiles_to_render:
            continue
        cropped = image.crop((sub_x * config.tile_pixel_size, sub_y * config.tile_pixel_size, (sub_x + 1) * config.tile_pixel_size, (sub_y + 1) * config.tile_pixel_size))
        scene_fs.makedirs(f"tiles/zoom_0/{tile_x}", recreate=True)

        os_path = scene_fs.getospath(f"tiles/zoom_0/{tile_x}/{tile_y}")
        image_handler.save_image(cropped, os_path)

        cur.execute(
            "INSERT OR REPLACE INTO tiles (render_name, zoom_level, x, y, last_modified) VALUES (?, ?, ?, ?, ?)",
            (config.render_name, 0, tile_x, tile_y, tile_last_modified[(tile_x, tile_y)])
        )
        tiles_rendered.append((0, tile_x, tile_y, tile_last_modified[(tile_x, tile_y)]))
        tiles_to_render.remove((tile_x, tile_y))
        zoom_tiles_to_render.remove((0, tile_x, tile_y))

    check_make_zoom_tiles(config, image_handler, scene_fs.opendir("tiles"), tiles_rendered, zoom_tiles_to_render, cur)
    cur.execute("COMMIT")

    chunky_image_file.close()

    scene_fs.remove(f"snapshots/{config.scene_name}-{spp}.png")


def get_child_tiles(zoom_level, tile_x, tile_z):
    yield zoom_level + 1, tile_x * 2, tile_z * 2
    yield zoom_level + 1, tile_x * 2 + 1, tile_z * 2
    yield zoom_level + 1, tile_x * 2, tile_z * 2 + 1
    yield zoom_level + 1, tile_x * 2 + 1, tile_z * 2 + 1


def check_make_zoom_tiles(config: Config, image_handler: ImageHandler, tile_fs, tiles_rendered, zoom_tiles_to_render, cur: sqlite3.Cursor):
    upper_tiles = set()
    tile_last_modified = {}

    for zoom, x, y, last_modified in tiles_rendered:
        upper_tile = (zoom - 1, x // 2, y // 2)
        if upper_tile not in upper_tiles:
            upper_tiles.add(upper_tile)
            tile_last_modified[upper_tile] = last_modified
        else:
            tile_last_modified[upper_tile] = max(tile_last_modified[upper_tile], last_modified)

    upper_tiles = [x for x in upper_tiles if all(y not in zoom_tiles_to_render for y in get_child_tiles(*x))]

    size = config.tile_pixel_size
    half_size = size // 2

    for upper_tile in upper_tiles:
        zoom, x, y = upper_tile
        tile_fs.makedirs(f"zoom_{zoom}/{x}", recreate=True)
        dst_image = np.zeros((size, size, 4), dtype=np.uint8)

        for src_x, src_y in [0,0], [0,1], [1,0], [1,1]:
            src_path = f"zoom_{zoom+1}/{x*2+src_x}/{y*2+src_y}"
            src_path_os = tile_fs.getospath(src_path)
            if not image_handler.image_exists(src_path_os):
                continue
            with io.BytesIO(image_handler.load_image(src_path_os)) as bio:
                src = Image.open(bio)
                src = src.resize((size//2, size//2), Image.LANCZOS)
                src = np.array(src.convert("RGBA"))
                dst_image[src_y*half_size:(src_y+1)*half_size, src_x*half_size:(src_x+1)*half_size] = src

        image_handler.save_image(Image.fromarray(dst_image), tile_fs.getospath(f"zoom_{zoom}/{x}/{y}"))
        cur.execute(
            "INSERT OR REPLACE INTO tiles (render_name, zoom_level, x, y, last_modified) VALUES (?, ?, ?, ?, ?)",
            (config.render_name, zoom, x, y, tile_last_modified[upper_tile])
        )
        zoom_tiles_to_render.remove(upper_tile)

    if len(upper_tiles) > 0 and all(tile[0] > -config.zoom_levels for tile in upper_tiles):
        next_tiles_to_render = [(zoom, x, y, tile_last_modified[(zoom, x, y)]) for zoom, x, y in upper_tiles]
        check_make_zoom_tiles(config, image_handler, tile_fs, next_tiles_to_render, zoom_tiles_to_render, cur)


def tiles_to_batches(config: Config, tile_set: set):
    batches = set()

    for tile_x, tile_y in tile_set:
        batch_x = int(tile_x // config.tile_batch_size)
        batch_y = int(tile_y // config.tile_batch_size)
        batches.add((batch_x, batch_y))

    return batches


def get_all_existing_tiles(config: Config):
    tile_fs = fs.open_fs(f"chunky/scenes/{config.scene_name}/tiles/zoom_0", create=True)
    tile_set = set()
    for x in tile_fs.walk():
        if len(x.files) > 0:
            tile_x = int(x.path.split("/")[-1])
            for f in x.files:
                tile_y = int(f.name.split(".")[0])
                tile_set.add((tile_x, tile_y))
    return tile_set


def list_chunks_in_region(config: Config, region_x, region_z):
    region = nbt.region.RegionFile(f"{config.world_path}/region/r.{region_x}.{region_z}.mca")
    chunks = region.get_chunks()
    base_x = region_x * 32
    base_z = region_z * 32
    result = []

    for chunk in chunks:
        chunk_x = base_x + chunk["x"]
        chunk_z = base_z + chunk["z"]
        last_update = region.metadata[(chunk["x"], chunk["z"])].timestamp
        result.append((chunk_x, chunk_z, last_update))

    for chunk in region.iter_chunks():
        if "xPos" not in chunk:
            chunk = chunk.get("Level")
        chunk_x = chunk.get("xPos").value
        chunk_z = chunk.get("zPos").value
        status = chunk.get("Status").value
        if status not in ["minecraft:full", "minecraft:initialize_light", "minecraft:carvers", "full", "minecraft:structure_starts", "minecraft:biomes"]:
            result = [x for x in result if x[0] != chunk_x or x[1] != chunk_z]
    return result


def render(config: Config, image_handler: ImageHandler):

    regions = list_regions(config)
    fs.open_fs(f"chunky/scenes/{config.scene_name}", create=True)
    output_fs = fs.open_fs(f"chunky/scenes/{config.scene_name}", create=True)
    if not output_fs.exists("index.html"):
        with output_fs.open("index.html", "w") as index_output, open("index.template.html", "r") as index_template:
            index_output.write(
                index_template.read() \
                              .replace("#TILE_SIZE#", str(config.tile_pixel_size)) \
                              .replace("#ZOOM_LEVELS#", str(config.zoom_levels)) \
                              .replace("#FILE_FORMAT#", "avif" if config.use_avif else "png")
            )

    con = sqlite3.connect("chunky/scenes/" + config.scene_name + "/tiles.db")
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tiles (
            render_name TEXT NOT NULL,
            zoom_level INTEGER NOT NULL,
            x INTEGER NOT NULL,
            y INTEGER NOT NULL,
            last_modified INTEGER NOT NULL,
            PRIMARY KEY (render_name, zoom_level, x, y)
        )
    """)

    start_time = time.time()

    tile_set = set()
    chunk_set = set()
    chunk_last_modified = {}
    tile_last_modified = {}

    print(f"Listing chunks...", end="")
    region_index = 0
    for region_x, region_z in regions:
        region_index += 1
        print(f"\rListing chunks... ({region_index} of {len(regions)})", end="")
        for chunk_x, chunk_z, last_update in list_chunks_in_region(config, region_x, region_z):
            chunk_set.add((chunk_x, chunk_z))
            chunk_last_modified[(chunk_x, chunk_z)] = last_update
            tile_set = tile_set.union(get_tiles_for_chunk(config, chunk_x, chunk_z))

    print()
    print(f"There are {len(chunk_set)} chunks needing {len(tile_set)} tiles.")
    print("Generating tile list...")

    for tile_x, tile_z in tile_set:
        chunks_visible_in_tile = get_chunklist_for_tile(config, tile_x, tile_z)
        chunk_timestamps = [chunk_last_modified[chunk] for chunk in chunks_visible_in_tile if chunk in chunk_last_modified]
        last_modified = max(chunk_timestamps) if len(chunk_timestamps) > 0 else 0
        tile_last_modified[(tile_x, tile_z)] = last_modified

    existing_tiles_db = cur.execute(f"SELECT x, y, last_modified FROM tiles WHERE zoom_level = 0 AND render_name=?", (config.render_name,)).fetchall()
    existing_tiles_db_set = set((x[0], x[1]) for x in existing_tiles_db)

    existing_tiles_set = get_all_existing_tiles(config)

    tiles_missing_from_db_set = tile_set - existing_tiles_db_set

    num_unknown_tiles = len(existing_tiles_set - tile_set)
    if num_unknown_tiles > 0:
        print(f"{num_unknown_tiles} tiles exist in the file system but aren't needed. Ignoring them.")
    num_unknown_tiles_db = len(existing_tiles_db_set - tile_set)
    if num_unknown_tiles_db > 0:
        print(f"{num_unknown_tiles_db} tiles exist in the database but aren't needed. Ignoring them.")

    unchanged_tiles = [x for x in existing_tiles_db if (x[0], x[1]) in tile_set and tile_last_modified[(x[0], x[1])] == x[2]]
    unchanged_tiles_set = set((x[0], x[1]) for x in unchanged_tiles)

    if len(tiles_missing_from_db_set) > 0:
        print(f"{len(tiles_missing_from_db_set)} tiles missing from database. Assuming they need to be updated.")

    tiles_to_render = tile_set - unchanged_tiles_set

    zoom_tiles_to_render = {(0, x, y) for x, y in tiles_to_render}

    lower_tiles = tiles_to_render

    for zoom_level in reversed(range(-config.zoom_levels, 0)):
        higher_tiles = {(x // 2, y // 2) for x, y in lower_tiles}
        print("Zoom level", zoom_level, "has", len(higher_tiles), "tiles.")
        zoom_tiles_to_render = zoom_tiles_to_render.union({(zoom_level, x, y) for x, y in higher_tiles})
        lower_tiles = higher_tiles

    print(len(zoom_tiles_to_render))

    print(f"There are {len(existing_tiles_set & tile_set)} existing tiles. {len(unchanged_tiles_set)} are unchanged.")
    print(f"Total tiles to render: {len(tiles_to_render)}.")

    batches = tiles_to_batches(config, tiles_to_render)
    print(f"Render will consist of {len(batches)} batches.")

    #for tile_to_render in tiles_to_render:
    #    ttt = tile_last_modified[tile_to_render] if tile_to_render in tile_last_modified else 0
    #    cur.execute("INSERT OR REPLACE INTO tiles VALUES (?, ?, ?, ?, ?)", (config.render_name, 0, tile_to_render[0], tile_to_render[1], ttt))
    #cur.execute("COMMIT")

    batches_completed = 0
    total_batches = len(batches)

    batches = list(batches)
    batches.sort(key=lambda x: abs(x[0]) + abs(x[1]))

    print("First 5 batches: ", batches[:5])

    rendering_start_time = time.time()

    for batch_x, batch_y in batches:
        if batches_completed > 0:
            elapsed_time = time.time() - rendering_start_time
            print(f"Rendering batch {batch_x}, {batch_y}. Completed: ({batches_completed}/{total_batches}). ETA: {elapsed_time / batches_completed * (total_batches - batches_completed)} seconds")
        else:
            print(f"Rendering batch {batch_x}, {batch_y}")
        run_batch(
            config,
            image_handler,
            batch_x,
            batch_y,
            chunk_set,
            tiles_to_render,
            cur,
            tile_last_modified,
            zoom_tiles_to_render
        )
        batches_completed += 1

    print("Render completed in", time.time() - start_time, "seconds.")


if __name__ == '__main__':
    config = Config()
    parse = argparse.ArgumentParser()
    parse.add_argument("--config", type=str)
    args = parse.parse_args()
    if args.config:
        json_config = json.load(open(args.config, "r"))
        config.load_from_dict(json_config)

    image_handler = AvifImageHandler(crf=config.avif_crf) if config.use_avif else PngImageHandler()
    if not image_handler.check():
        print("Required dependencies for the chosen image format are not available. Exiting.")
        exit(1)

    print("Starting render. Config:")
    print(config)
    render(config, image_handler)

import math
from dataclasses import dataclass


@dataclass
class Config:
    world_path: str = None  # Absolute path to the world folder
    output_path: str = "~/output"
    render_name: str = "daylight"
    chunky_home_path: str = "chunky"
    scene_name: str = "scene_name"
    tile_batch_size: int = 16  # Number of tiles the load the chunks for at once
    tile_render_batch_size: int = 16  # Number of tiles to render at each chunky invocation
    tile_border_size: int = 4  # Number of tiles outside the render area to load chunks for
    tile_padding_bottom: int = math.ceil(64 / (16 * math.sqrt(2) / math.sin(math.radians(60))))
    tile_padding_top: int = math.ceil(320 / (16 * math.sqrt(2) / math.sin(math.radians(60))))
    tile_pixel_size: int = 384
    samples_per_pixel: int = 50
    zoom_levels: int = 8
    threads: int = 14

    def load_from_dict(self, data: dict):
        for key, value in data.items():
            setattr(self, key, value)

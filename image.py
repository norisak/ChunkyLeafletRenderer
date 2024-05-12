import os
import subprocess
import sys
from io import BytesIO
from typing import Union
from PIL import Image


def to_str_path(path: Union[str, bytes]) -> str:
    return path.decode("utf-8") if isinstance(path, bytes) else path


def image_exists(image_os_path: Union[str, bytes], file_extension: str) -> bool:
    path_str = to_str_path(image_os_path)
    return os.path.isfile(path_str+file_extension)


class ImageHandler:
    def __init__(self):
        pass

    def save_image(self, image: Image, image_os_path: Union[str, bytes]):
        pass

    def load_image(self, image_os_path: Union[str, bytes]):
        pass

    @staticmethod
    def image_exists(image_os_path: Union[str, bytes]) -> bool:
        pass

    def check(self):
        raise NotImplementedError("Check method not implemented.")


class PngImageHandler(ImageHandler):
    def __init__(self):
        super().__init__()

    def save_image(self, image: Image, image_os_path: Union[str, bytes]):
        path_str = to_str_path(image_os_path)
        with BytesIO() as bio, open(path_str+".png", "wb") as f:
            image.save(bio, format="png")
            bio.seek(0)
            f.write(bio.read())

    def load_image(self, image_os_path: Union[str, bytes]) -> bytes:
        path_str = to_str_path(image_os_path)

        with open(path_str+".png", "rb") as f:
            return f.read()

    @staticmethod
    def image_exists(image_os_path: Union[str, bytes]) -> bool:
        return image_exists(image_os_path, ".png")

    def check(self):
        return True


class AvifImageHandler(ImageHandler):
    crf = None

    def __init__(self, crf: int):
        super().__init__()
        self.crf = crf

    def save_image(self, image: Image, image_os_path: Union[str, bytes]):
        output_file = to_str_path(image_os_path) + ".avif"

        with subprocess.Popen(
            ["ffmpeg", "-f", "png_pipe", "-i", "pipe:0", "-c:v", "libaom-av1", "-crf", str(self.crf), "-cpu-used", "6", output_file],
            stdin=subprocess.PIPE,
            stderr=subprocess.DEVNULL
        ) as ffmpeg_process, BytesIO() as bio:
            image.save(bio, format="png")
            bio.seek(0)
            ffmpeg_process.stdin.write(bio.read())
            ffmpeg_process.stdin.close()
            ffmpeg_process.wait()

    def load_image(self, image_os_path: Union[str, bytes]) -> bytes:
        path_str = to_str_path(image_os_path) + ".avif"

        return subprocess.run(
            ["ffmpeg", "-i", path_str, "-c:v", "png", "-f", "image2pipe", "pipe:1"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        ).stdout

    @staticmethod
    def image_exists(image_os_path: Union[str, bytes]) -> bool:
        return image_exists(image_os_path, ".avif")

    def check(self):
        result = subprocess.run(
            ["ffmpeg", "-f", "lavfi", "-i", "nullsrc", "-frames:v", "1", "-c:v", "libaom-av1", "-f", "null", "-"],
            stderr=subprocess.DEVNULL
        )
        if result.returncode != 0:
            print("ffmpeg with libaom-av1 support is required to use the AVIF image format.", file=sys.stderr)
            return False
        return True

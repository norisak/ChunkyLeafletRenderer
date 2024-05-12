import os
import subprocess
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


class AvifImageHandler(ImageHandler):
    crf = None

    def __init__(self, crf: int):
        super().__init__()
        self.crf = crf

    def save_image(self, image: Image, image_os_path: Union[str, bytes]):
        pass

    @staticmethod
    def image_exists(image_os_path: Union[str, bytes]) -> bool:
        return image_exists(image_os_path, ".avif")

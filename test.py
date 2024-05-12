import unittest

import tile_math
from config import Config


class TestTileCoordinates(unittest.TestCase):
    def test_chunk_to_tile(self):
        config = Config()

        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, 2, 2),
            (0, 1)
        )
        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, 1, -1),
            (1, 0)
        )
        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, -1, 1),
            (-1, 0)
        )
        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, -1, 0),
            (-1, 0)
        )
        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, 0, 1),
            (-1, 0)
        )
        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, -2, -1),
            (-1, -1)
        )
        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, -1, -2),
            (0, -1)
        )
        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, 0, -1),
            (0, 0)
        )
        self.assertTupleEqual(
            tile_math.get_tile_for_chunk(config, 1, 0),
            (0, 0)
        )

    def test_tile_to_chunks(self):
        config = Config()
        self.assertSetEqual(
            tile_math.get_chunks_for_tile(config, 0, 1),
            {
                (0, 1),
                (1, 1),
                (1, 0),
                (1, 2),
                (2, 2),
                (2, 1),
                (2, 3),
                (3, 2),
            }
        )


if __name__ == "__main__":
    unittest.main()

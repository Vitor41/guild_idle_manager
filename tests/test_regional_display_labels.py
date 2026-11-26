from copy import deepcopy
import unittest

from app.routes.regional_routes import _localized_tier_counts


class RegionalDisplayLabelTests(unittest.TestCase):
    def test_tier_counts_use_pt_br_labels_without_changing_raw_counts(self):
        raw_counts = {"common": 4, "rare": 2, "future_rarity": 3}
        before = deepcopy(raw_counts)

        self.assertEqual(
            _localized_tier_counts(raw_counts),
            {"Comum": 4, "Raro": 2, "Sem classificação": 3},
        )
        self.assertEqual(raw_counts, before)


if __name__ == "__main__":
    unittest.main()

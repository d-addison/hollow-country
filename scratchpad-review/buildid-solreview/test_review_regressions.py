"""Synthetic authored-source regression; no DayZ/runtime acceptance evidence."""
import copy
import unittest

from tests.unit import test_search_economy_integration as integration
from tests.unit.build_identity_support import translate


class InteriorBuildAliasReloadTests(unittest.TestCase):
    def test_native_config_alias_preserves_a_canonical_legacy_layout(self):
        # Existing synthetic fixture, identical headers and assignments except
        # the newly admitted config spelling of the same observed engine build.
        fixture = integration.SearchIntegrationTests()
        fixture.setUp()
        stored = copy.deepcopy(fixture.layout)
        fixture.t.m_Config.Build = "1.30.164289.70"
        fixture.layout.Build = fixture.t.m_Config.Build
        self.assertTrue(translate().SameBuild(fixture.layout.Build, stored.Build))
        self.assertTrue(
            fixture.call("PreserveLegacyManifest", fixture.layout, stored),
            "admitted native config alias refuses an otherwise identical canonical legacy layout",
        )


if __name__ == "__main__":
    unittest.main()

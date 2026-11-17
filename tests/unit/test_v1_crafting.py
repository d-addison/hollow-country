"""V1 policy execution with explicit synthetic inventory; never engine proof."""
from types import SimpleNamespace as NS
import unittest

from tests.unit.test_crafting_families import source_policy, state_for
from tests.unit.test_salvage_tools import SyntheticItem


class V1LeatherTests(unittest.TestCase):
    def test_beige_small_garments_share_one_panel_policy_and_retain_containers(self):
        actor = NS(IsAlive=lambda: True, IsUnconscious=lambda: False)
        policy = source_policy()
        for kind in ('LeatherGloves_Beige', 'LeatherHat_Beige'):
            with self.subTest(kind=kind):
                self.assertTrue(policy.AllowsSource('HCRecoverMediumLeather', kind))
                state = state_for('HCRecoverMediumLeather')
                material, tool = SyntheticItem(kind, actor, 50), SyntheticItem('KitchenKnife', actor, 6)
                self.assertTrue(state.CanDo([material, tool], actor))
                self.assertEqual([1], state.m_ResultSetQuantity)
                for cargo, attachments, worn in ((1, 0, False), (0, 1, False), (0, 0, True)):
                    material.inventory = NS(IsAttachment=lambda: worn,
                                            AttachmentCount=lambda: attachments,
                                            GetCargo=lambda: NS(GetItemCount=lambda: cargo))
                    self.assertFalse(state.CanDo([material, tool], actor))
                    self.assertIs(tool, [material, tool][1])
                    self.assertFalse(material.deleted)


if __name__ == '__main__':
    unittest.main()

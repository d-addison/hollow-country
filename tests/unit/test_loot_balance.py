"""Loot family detection and the balance rules on plain data; these do not prove engine spawning."""
import unittest

from tools.package import loot_balance as bal
from tools.package import loot_boost as boost


def rows(**spec):
    return {n: {'category': v[0], 'nominal': v[1], 'stock': v[2] if len(v) > 2 else 1, 'locked': False, 'name': n}
            for n, v in spec.items()}


class Families(unittest.TestCase):
    def test_colour_tokens_are_removed(self):
        self.assertEqual(bal.family('Jeans_Blue'), bal.family('Jeans_Black'))
        self.assertEqual(bal.family('NBCBootsGray'), bal.family('NBCBootsYellow'))
        self.assertEqual(bal.family('Shemag_Brown'), bal.family('Shemag_Red'))

    def test_a_word_that_merely_contains_a_modifier_keeps_its_name(self):
        self.assertEqual(bal.family('Flashlight'), 'Flashlight')
        self.assertEqual(bal.family('Jeans_Dark_Blue'), bal.family('Jeans_Blue'))

    def test_the_override_table_wins(self):
        self.assertEqual(bal.family('Engraved1911'), 'Colt1911')
        self.assertEqual(bal.family('engraved1911'), 'Colt1911')

    def test_deterministic(self):
        names = ['SKS', 'SKS_Black', 'SKS_Desert', 'Mag_STANAG_30Rnd']
        self.assertEqual([bal.family(n) for n in names], [bal.family(n) for n in names])

    def test_table_validation(self):
        doc = bal.load_table()
        self.assertEqual(doc['schema'], 1)
        self.assertIn('engraved1911', {k.lower() for k in doc['overrides']})


class Split(unittest.TestCase):
    def test_every_share_is_at_least_one_and_the_total_holds(self):
        shares = bal.split([('a', 10), ('b', 1), ('c', 1)], 6)
        self.assertEqual(sum(shares.values()), 6)
        self.assertTrue(all(v >= 1 for v in shares.values()))

    def test_total_below_member_count_is_raised(self):
        self.assertEqual(sum(bal.split([('a', 1), ('b', 1), ('c', 1)], 1).values()), 3)


class Balance(unittest.TestCase):
    def test_r3_caps_a_colour_family_at_one_and_a_half_times_its_largest(self):
        data = rows(Shirt_Blue=('clothes', 40), Shirt_Red=('clothes', 40), Shirt_Green=('clothes', 40), Other=('clothes', 60))
        changed, report = bal.balance(data)
        total = sum(changed.get(n, data[n]['nominal']) for n in ('Shirt_Blue', 'Shirt_Red', 'Shirt_Green'))
        self.assertLessEqual(total, 60)
        self.assertGreater(report['clothes']['r3_freed'], 0)

    def test_kept_categories_are_never_touched_by_r3(self):
        data = rows(Can_Blue=('food', 40), Can_Red=('food', 40))
        changed, _ = bal.balance(data)
        self.assertEqual(changed, {})

    def test_locked_rows_keep_their_nominal(self):
        data = rows(Gun_Black=('weapons', 40), Gun_Green=('weapons', 40))
        data['Gun_Black']['locked'] = True
        changed, _ = bal.balance(data)
        self.assertNotIn('Gun_Black', changed)

    def test_r2b_raises_a_family_below_the_floor_and_zero_rows_stay_zero(self):
        data = rows(Rare=('tools', 1), Plenty=('tools', 90), Gone=('tools', 0))
        changed, _ = bal.balance(data)
        self.assertGreaterEqual(changed.get('Rare', 1), 3)
        self.assertNotIn('Gone', changed)

    def test_r1_caps_a_dominant_family(self):
        data = {'Big': {'category': 'tools', 'nominal': 900, 'stock': 10, 'locked': False, 'name': 'Big'}}
        for i in range(30):
            data['T%d' % i] = {'category': 'tools', 'nominal': 10, 'stock': 10, 'locked': False, 'name': 'T%d' % i}
        changed, report = bal.balance(data)
        self.assertLess(changed['Big'], 900)
        self.assertGreater(report['tools']['r1_freed'], 0)

    def test_rows_are_matched_by_their_name_field_not_the_lowercase_key(self):
        data = {n.lower(): dict(v) for n, v in rows(Boots_Gray=('clothes', 21), Boots_Yellow=('clothes', 21),
                                                    Boots_White=('clothes', 21), Other=('clothes', 20)).items()}
        changed, _ = bal.balance(data)
        self.assertLessEqual(sum(changed.get(n, data[n]['nominal']) for n in ('boots_gray', 'boots_yellow', 'boots_white')), 32)

    def test_reinvestment_stays_inside_the_category(self):
        data = rows(Shirt_Blue=('clothes', 40), Shirt_Red=('clothes', 40), Small=('clothes', 4), Mid=('clothes', 20),
                    Tool=('tools', 9))
        changed, _ = bal.balance(data)
        self.assertNotIn('Tool', changed)

    def test_the_result_is_deterministic(self):
        data = rows(A_Blue=('clothes', 30), A_Red=('clothes', 30), B=('clothes', 2), C=('clothes', 12))
        self.assertEqual(bal.balance(data), bal.balance(data))


class SupportFloors(unittest.TestCase):
    def test_base_ammo_folds_boxes_and_tracers(self):
        self.assertEqual(bal.base_ammo('AmmoBox_9x19_25rnd'), 'Ammo_9x19')
        self.assertEqual(bal.base_ammo('Ammo_762x39Tracer'), 'Ammo_762x39')

    def test_ammo_and_magazine_pools_are_raised_to_the_ratio(self):
        guns = {'G1': {'nominal': 10, 'ammo': ['Ammo_9x19'], 'magazines': ['Mag_G']}}
        added, report = bal.support_floors(guns, {'Ammo_9x19': 2}, {'Mag_G': 1})
        self.assertEqual(added['Ammo_9x19'], 13)
        self.assertEqual(added['Mag_G'], 9)
        self.assertEqual(report['raised_ammo'], 13)

    def test_a_pool_without_a_row_is_reported_not_invented(self):
        guns = {'G1': {'nominal': 4, 'ammo': ['Ammo_x'], 'magazines': []}}
        added, report = bal.support_floors(guns, {}, {})
        self.assertEqual(added, {})
        self.assertEqual(report['no_row'], ['Ammo_x'])

    def test_only_raisable_rows_are_raised_but_all_count_as_supply(self):
        guns = {'G1': {'nominal': 10, 'ammo': ['Ammo_a'], 'magazines': []}}
        added, _ = bal.support_floors(guns, {'Ammo_a': 5, 'AmmoBox_a_25rnd': 5}, {}, raisable={'Ammo_a'})
        self.assertEqual(added, {'Ammo_a': 5})

    def test_guns_sharing_a_cartridge_share_a_pool(self):
        guns = {'G1': {'nominal': 4, 'ammo': ['Ammo_a'], 'magazines': []}, 'G2': {'nominal': 4, 'ammo': ['Ammo_a'], 'magazines': []}}
        added, report = bal.support_floors(guns, {'Ammo_a': 6}, {})
        self.assertEqual(report['ammo_pools'], 1)
        self.assertEqual(added['Ammo_a'], 6)


class BalanceKnob(unittest.TestCase):
    GOOD = {'FamilyFactor': 1.5, 'FamilyFloor': 3, 'ShareCap': 0.03, 'StockFactor': 2.0, 'AmmoPerGun': 1.5, 'MagazinePerGun': 1.0}

    def test_shipped_value_is_valid(self):
        self.assertEqual(boost._balance(self.GOOD), boost._balance(dict(self.GOOD)))
        self.assertIsNone(boost._balance(None))

    def test_missing_or_out_of_range_fields_are_refused(self):
        bad = dict(self.GOOD)
        del bad['ShareCap']
        with self.assertRaises(ValueError):
            boost._balance(bad)
        with self.assertRaises(ValueError):
            boost._balance(dict(self.GOOD, FamilyFloor=0))

    def test_capacity_ceiling_allows_eight(self):
        self.assertEqual(boost.MAX_CAPACITY, 8.0)


if __name__ == '__main__':
    unittest.main()

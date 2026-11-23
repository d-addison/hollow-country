"""Loot family detection and the balance rules on plain data; these do not prove engine spawning."""
import math
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

    def test_largest_remainder_uses_exact_ties_and_name_order(self):
        weights = [('z', 1), ('a', 1), ('b', 1)]
        self.assertEqual({'a': 2, 'b': 2, 'z': 1}, bal.split(weights, 5))
        self.assertEqual(bal.split(weights, 10**18 + 2), bal.split(list(reversed(weights)), 10**18 + 2))
        self.assertEqual(10**18 + 2, sum(bal.split(weights, 10**18 + 2).values()))


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

    def _pass2_data(self):
        data = rows(Shirt_Blue=('clothes', 60), Shirt_Red=('clothes', 60), Shirt_Green=('clothes', 60))
        for i in range(30):
            data['Item%d' % i] = {'category': 'clothes', 'nominal': 20, 'stock': 20, 'locked': False, 'name': 'Item%d' % i}
        for key in ('Shirt_Blue', 'Shirt_Red', 'Shirt_Green'):
            data[key]['stock'] = 20
        return data

    def test_pass_two_returns_the_unspent_nominal_to_every_family_proportionally(self):
        data = self._pass2_data()
        changed, report = bal.balance(data)
        row = report['clothes']
        self.assertGreater(row['reinvested2'], 0)
        self.assertEqual(row['reinvested'] + row['reinvested2'] + row['unspent'], row['r3_freed'] + row['r1_freed'])
        self.assertGreater(sum(changed.get('Item%d' % i, 20) for i in range(30)), 600)
        # nothing exceeds the R1 cap of the final category total
        total = sum(changed.get(n, v['nominal']) for n, v in data.items())
        for i in range(30):
            self.assertLessEqual(changed.get('Item%d' % i, 20), max(0.03, 2.0 * 20 / 1100) * total + 1)

    def test_pass_two_never_lifts_a_colour_family_past_its_budget(self):
        data = self._pass2_data()
        names = ('Shirt_Blue', 'Shirt_Red', 'Shirt_Green')
        after = bal.balance(data)[0]
        before = bal.balance(data, pass2_share=0.0)[0]
        self.assertEqual([after.get(n) for n in names], [before.get(n) for n in names])

    def test_pass_two_share_scales_the_return_and_skip_withholds_a_category(self):
        data = self._pass2_data()
        _, full = bal.balance(data)
        _, half = bal.balance(data, pass2_share=0.5)
        _, none = bal.balance(data, pass2_skip={'clothes'})
        self.assertLess(half['clothes']['reinvested2'], full['clothes']['reinvested2'])
        self.assertGreater(half['clothes']['reinvested2'], 0)
        self.assertEqual(none['clothes']['reinvested2'], 0)
        self.assertEqual(none['clothes']['unspent'], none['clothes']['r3_freed'] - none['clothes']['reinvested'])

    def test_capacity_aware_pass_two_feeds_only_buckets_with_room(self):
        data = self._pass2_data()
        names = ['Item%d' % i for i in range(30)]
        table = {'bucket': {'roomy': 400, 'full': 0}, 'class': {n.lower(): ('roomy' if i < 10 else 'full')
                                                                   for i, n in enumerate(names)}}
        table['class'].update({n.lower(): 'full' for n in ('Shirt_Blue', 'Shirt_Red', 'Shirt_Green')})
        data = {n.lower(): dict(v, name=n) for n, v in data.items()}
        changed, report = bal.balance(data, slack=table, slack_share=1.0)
        gained = {n: changed.get(n.lower(), 20) - 20 for n in names}
        self.assertEqual(sum(gained[n] for n in names[10:]), 0)
        self.assertGreater(sum(gained[n] for n in names[:10]), 0)
        self.assertLessEqual(sum(gained.values()), 400)
        self.assertEqual(report['clothes']['reinvested'] + report['clothes']['reinvested2'] + report['clothes']['unspent'],
                         report['clothes']['r3_freed'])

    def test_slack_share_scales_what_a_bucket_may_take(self):
        data = {n.lower(): dict(v, name=n) for n, v in self._pass2_data().items()}
        table = {'bucket': {'b': 100}, 'class': {'item%d' % i: 'b' for i in range(30)}}
        full = bal.balance(data, slack=table, slack_share=1.0)[1]['clothes']
        half = bal.balance(data, slack=table, slack_share=0.5)[1]['clothes']
        spent = lambda row: row['reinvested'] + row['reinvested2']
        self.assertLessEqual(spent(full), 100)
        self.assertLessEqual(spent(half), 50)
        self.assertGreater(spent(half), 0)
        self.assertLess(spent(half), spent(full))

    def test_the_slack_table_loads_and_names_known_buckets(self):
        from tools.package import loot_slack
        table = loot_slack.load()
        self.assertTrue(table['class'])
        self.assertLessEqual(set(table['class'].values()), set(table['bucket']))

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
    GOOD = {'FamilyFactor': 1.5, 'FamilyFloor': 3, 'ShareCap': 0.03, 'StockFactor': 2.0, 'Pass2Share': 0.55, 'SlackShare': 0.5, 'AmmoPerGun': 1.5, 'MagazinePerGun': 1.0}

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

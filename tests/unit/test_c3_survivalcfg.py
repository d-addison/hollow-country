"""Explicit synthetic JSON/native-zero-fill ports; never DayZ runtime evidence."""
import json
import re
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from tests.unit.test_event_runtime import translate
from tests.unit.test_group_server import body, EArray

ROOT = Path(__file__).resolve().parents[2]
WORLD = ROOT / 'mods/HollowCountry/scripts/4_World'
# DTO, owned source, field: (default, lower, upper).
CONFIGS = {
 'HCForageConfig': ('Forage/HCForage.c', {
  'CellCap': (3,1,3), 'TotalCap': (40,1,40), 'RecordCap': (40,1,40), 'LiveCap': (40,1,40),
  'DelaySeconds': (1800,1800,86400), 'FamiliarityReductionSeconds': (180,0,1800),
  'SpotOffsetX': (45,1,199), 'SpotOffsetZ': (155,1,199), 'SpotSpacing': (55,1,99),
  'FloraStartMonth': (6,1,12), 'FloraEndMonth': (11,1,12),
  'BerryStartMonth': (6,1,12), 'BerryEndMonth': (8,1,12),
  'MushroomStartMonth': (9,1,12), 'MushroomEndMonth': (11,1,12), 'FloraRollSides': (10,5,100)}),
 'HCVehicleFlipConfig': ('Vehicles/HCVehicleFlip.c', {
  'ReachMeters': (5.0,1,5), 'Helpers': (3,1,6), 'TorqueMassScale': (0.4,0.01,0.4),
  'LiftMassScale': (0.1,0.01,0.1), 'Pulses': (3,1,3)}),
 'HCWreckSalvageConfig': ('Vehicles/HCWreckSalvage.c', {
  'WheelWeight': (2,0,100), 'SparkPlugWeight': (20,0,100), 'BatteryWeight': (15,0,100),
  'RadiatorWeight': (15,0,100), 'HeadlightWeight': (20,0,100), 'ScrapWeight': (28,1,100),
  'BudgetMinimum': (1,1,3), 'BudgetRollSides': (3,1,3), 'ActionSeconds': (8.0,1,20),
  'ReachMeters': (2.0,0.5,2), 'CompletionGraceMs': (500,0,500)}),
 'HCFuelSiphonConfig': ('Actions/c3FuelSiphonConfig.c', {
  'ReachMeters': (2.0,0.5,2), 'ContactToleranceMeters': (0.5,0.01,0.5),
  'MaxSessions': (96,1,96), 'LeaseMs': (10000,1000,10000),
  'DiagnosticStepSeconds': (1.0,0.1,1), 'RepeatSeconds': (0.5,0.1,1)}),
 'HCSignalConfig': ('Actions/HCActionAskForNews.c', {'CooldownMs': (30000,1000,3600000)}),
 'HCProgressionConfig': ('Progression/HCProgression.c', {'GainPeriodSeconds': (60,1,86400), 'SavePeriodSeconds': (60,60,3600)}),
 'HCRadioDefaults': ('Leads/HCRadioChatter.c', {
  'ReportRangeMetres': (1000.0,1,1000), 'MaxListeners': (32,1,32), 'ChannelCountLimit': (64,1,64),
  'LocalsMHz': (87.8,87.8,102.5), 'VolunteersMHz': (89.5,87.8,102.5),
  'ScavengersMHz': (91.3,87.8,102.5), 'RaidersMHz': (94.6,87.8,102.5),
  'TravellersMHz': (96.6,87.8,102.5), 'BroadcastGapSeconds': (600,60,86400)}),
 'HCEscalationState': ('World/HCEscalationClock.c', {
  'InfectedWeek': (0.25,0,1), 'InfectedFortnight': (0.55,0,1), 'InfectedCap': (1.0,0,1),
  'RaidersWeek': (0.10,0,1), 'RaidersFortnight': (0.35,0,1), 'RaidersCap': (1.0,0,1),
  'ScarcityWeek': (0.15,0,1), 'ScarcityFortnight': (0.40,0,1), 'ScarcityCap': (1.0,0,1),
  'HorizonDays': (30,15,365)})
}


def fixture_config(cls, values=None):
    """Deserialize an explicit synthetic profile, then execute authored fixup."""
    rel, fields = CONFIGS[cls]
    source = (WORLD / rel).read_text()
    match = re.search(r'class ' + cls + r'\s*\{', source)
    if not match:
        raise AssertionError('missing profile DTO ' + cls)
    dto = body(source, match.end())
    defaults = {key: json.loads(value) for key, value in re.findall(r'^    (?:int|float) (\w+) = ([\d.]+);', dto, re.M)}
    defaults = {k:v for k,v in defaults.items() if k in fields}
    payload = json.dumps(values or {})
    # Native JSON zero-fill is explicit, not constructor-default preservation.
    config = N(**{key: (values or {}).get(key, 0) for key in defaults})
    env = dict(HCJsonFields=N(Has=lambda text,key: key in json.loads(text)),
               EArray=EArray, Print=lambda line: None)
    normalize = translate(dto, 'HCNormalize', env, cls, member=True)
    normalize(config, payload)
    return config


def config_ports():
    """Declared-default config ports for existing synthetic engine harnesses."""
    result = {}
    for cls, (_, fields) in CONFIGS.items():
        values = {key: limits[0] for key, limits in fields.items()}
        if cls == 'HCForageConfig':
            values.update(FloraClasses=['Cannabis','AmanitaMushroom','AuriculariaMushroom','CraterellusMushroom','PsilocybeMushroom'],
                          BerryClasses=['SambucusBerry','CaninaBerry'],
                          MushroomClasses=['BoletusMushroom','MacrolepiotaMushroom','CaninaBerry'])
        config = N(**values)
        result[cls] = N(Get=lambda config=config:config)
        if cls == 'HCForageConfig':
            result[cls].MAX_DELAY_SECONDS = 86400  # Explicit persisted-schema bound.
        if cls == 'HCRadioDefaults':
            # Synthetic registry port executes authored canonical-to-config mapping.
            text = (WORLD / CONFIGS[cls][0]).read_text()
            result[cls].Tuned = translate(text, 'Tuned', {'HCRadioDefaults':result[cls]}, cls)
            qualify = translate(text, 'HCQualifyChannels',
                                dict(HCRadioDefaults=result[cls], EArray=EArray, Print=lambda line: None),
                                cls, member=True)
            config.HCQualifyChannels = lambda channels, config=config, fn=qualify: fn(config, channels)
    return result


class SurvivalConfigTests(unittest.TestCase):
    def test_profile_overrides_and_invalid_fallback_for_every_numeric_field(self):
        for cls, (_, fields) in CONFIGS.items():
            with self.subTest(dto=cls):
                self.assertEqual({k:v[0] for k,v in fields.items()}, vars(fixture_config(cls)))
                for key, (default, lower, upper) in fields.items():
                    override = lower if default != lower else upper
                    # Cross-field constraints use a coherent companion override.
                    values = {key: override}
                    if key == 'BudgetMinimum': values['BudgetRollSides'] = 1
                    if key == 'BudgetRollSides': values['BudgetMinimum'] = 1
                    self.assertEqual(override, getattr(fixture_config(cls, values), key), (cls,key))
                    self.assertEqual(default, getattr(fixture_config(cls, {key: upper+1}), key), (cls,key))

    def test_json_override_changes_authored_delay_and_refill(self):
        config = fixture_config('HCForageConfig', {'DelaySeconds':3600, 'CellCap':1})
        env = dict(HCForageConfig=N(Get=lambda:config))
        source = (WORLD / 'Survival/HCSurvivalPolicy.c').read_text()
        policy = N()
        env['HCSurvivalPolicy'] = policy
        for name in ('DecayedFamiliarity','ForageDelay','CanRefill'):
            setattr(policy,name,translate(source,name,env,'HCSurvivalPolicy'))
        self.assertEqual(3420,policy.ForageDelay(100))
        self.assertFalse(policy.CanRefill(False,1,1,5000,0))
        self.assertTrue(policy.CanRefill(False,0,1,5000,0))

    def test_profile_override_changes_escalation_pressure(self):
        config = fixture_config('HCEscalationState', {'InfectedWeek':0.5, 'HorizonDays':60})
        env = dict(HCEscalationClock=N(HCParameters=lambda:config), Math=N(Clamp=lambda v,lo,hi:max(lo,min(hi,v))))
        source = (WORLD/'World/HCEscalationClock.c').read_text()
        curve = translate(source,'Curve',env,'HCEscalationClock')
        env['HCEscalationClock'].Curve = curve
        pressure = translate(source,'PressureAtDay',env,'HCEscalationClock')
        self.assertEqual(0.5, pressure('infected',7))
        self.assertLess(pressure('infected',30),1)
        self.assertEqual(1, pressure('infected',60))

    def test_lowering_forage_delay_retains_existing_durable_reservations(self):
        from tests.unit.test_hc_forage import bind
        config = config_ports()['HCForageConfig']
        spot = N(CellX=1,CellZ=1,NodeSlot=0,ReadyUtc=8500)
        module = N(m_State=N(Version=1,WorldName='chernarusplus',Spots=EArray([spot])))
        env = dict(range=range,RECORD_CAP=40,HCForageConfig=config)
        bind(WORLD/'Forage/HCForage.c','HCForageModule',module,env,['HCValidState'])
        self.assertTrue(module.HCValidState(5000),'lowering tuning must not quarantine a valid saved reservation')

    def test_profile_override_changes_flip_reach(self):
        config = fixture_config('HCVehicleFlipConfig', {'ReachMeters':2.0})
        actor = N(IsAlive=lambda:True,IsUnconscious=lambda:False,IsRestrained=lambda:False,
                  IsInVehicle=lambda:False,GetPosition=lambda:[4,0,0])
        def transform(rows): rows[1] = [0,-1,0]
        vehicle = N(IsPendingDeletion=lambda:False,IsRuined=lambda:False,EngineIsOn=lambda:False,
                    GetPosition=lambda:[0,0,0],GetTransform=transform)
        env = dict(HCVehicleFlipConfig=N(Get=lambda:config),
                   vector=N(DistanceSq=lambda a,b:sum((x-y)**2 for x,y in zip(a,b))),
                   GetVelocity=lambda car:N(LengthSq=lambda:0),
                   dBodyGetAngularVelocity=lambda car:N(LengthSq=lambda:0),
                   SyntheticTransform=lambda:[None]*4)
        source = (WORLD/'Vehicles/HCVehicleFlip.c').read_text().replace('vector transform[4];','vector transform = SyntheticTransform();')
        candidate = translate(source,'HCCandidate',env,'HCVehicleFlipModule')
        self.assertFalse(candidate(actor,vehicle))
        config.ReachMeters = fixture_config('HCVehicleFlipConfig', {'ReachMeters':6.0}).ReachMeters
        self.assertTrue(candidate(actor,vehicle))

    def test_profile_override_changes_signal_cooldown(self):
        config = fixture_config('HCSignalConfig', {'CooldownMs':1000})
        notices = EArray([N(Recipient='synthetic-account', At=1000)])
        player = N(GetIdentity=lambda:N(GetId=lambda:'synthetic-account'))
        env = dict(HCSignalConfig=N(Get=lambda:config), fixture_notices=notices,
                   GetGame=lambda:N(IsServer=lambda:True, GetTime=lambda:2500))
        source = (WORLD/'Actions/HCActionAskForNews.c').read_text()
        source = source.replace('s_Notices','fixture_notices').replace('prune--;','prune = prune - 1;')
        allowed = translate(source,'Allowed',env,'HCSignalCooldown')
        self.assertTrue(allowed(player))
        self.assertEqual([],notices)
        config.CooldownMs = fixture_config('HCSignalConfig', {'CooldownMs':-1}).CooldownMs
        notices.Insert(N(Recipient='synthetic-account',At=1000))
        self.assertFalse(allowed(player))

    def test_profile_override_changes_siphon_lease(self):
        config = fixture_config('HCFuelSiphonConfig', {'LeaseMs':1000})
        env = dict(HCFuelSiphonConfig=N(Get=lambda:config))
        live = translate((WORLD/'Actions/HCActionSiphonFuel.c').read_text(),'LeaseLive',env,'HCSiphonDiagnosticLocks')
        self.assertTrue(live(100,1100))
        self.assertFalse(live(100,1101))
        config.LeaseMs = fixture_config('HCFuelSiphonConfig', {'LeaseMs':10001}).LeaseMs
        self.assertTrue(live(100,1101))

    def test_profile_override_retunes_radio_without_changing_persisted_identity(self):
        config = fixture_config('HCRadioDefaults', {'LocalsMHz':99.9})
        source = (WORLD/'Leads/HCRadioChatter.c').read_text()
        env = dict(HCRadioDefaults=N(Get=lambda:config))
        tuned = translate(source,'Tuned',env,'HCRadioDefaults')
        identity = translate(source,'Frequency',{},'HCRadioChatter')
        self.assertEqual(87.8, identity('locals'))
        self.assertEqual(99.9, tuned(identity('locals')))
        config.LocalsMHz = fixture_config('HCRadioDefaults', {'LocalsMHz':200}).LocalsMHz
        self.assertEqual(87.8, tuned(identity('locals')))

    def test_profile_override_changes_progression_gain_period(self):
        config = fixture_config('HCProgressionConfig', {'GainPeriodSeconds':10})
        row = N(Key='synthetic',CharacterKey='life',LegacyDeferred=False,Dead=False,
                DecayUtc=1000,GainUtc=1000,Forage=2)
        module = N(m_Healthy=True,m_SaveUtc=1000,m_State=N(Players=EArray([row])),
                   HCDecay=lambda *args:None,HCChanged=lambda:None)
        env = dict(HCProgressionConfig=N(Get=lambda:config),
                   HCSurvivalRuntime=N(HCIsServer=lambda:True,HCCharacterKey=lambda p:'life',HCIdentityKey=lambda p:'synthetic'),
                   HCGroupClock=N(Utc=lambda:1010),Print=lambda line:None)
        # Restricted translator type spelling only; no branch or arithmetic changes.
        source = (WORLD/'Progression/HCProgression.c').read_text().replace('HCProgressionRow','HCEventProgressionRow')
        award = translate(source,'HCAwardForage',env,'HCProgressionModule',member=True)
        self.assertEqual(3,award(module,N(IsAlive=lambda:True)))
        row.Forage, row.GainUtc = 2,1000
        config.GainPeriodSeconds = fixture_config('HCProgressionConfig', {'GainPeriodSeconds':0}).GainPeriodSeconds
        self.assertEqual(2,award(module,N(IsAlive=lambda:True)))

    def test_profile_override_changes_authored_wreck_budget(self):
        config = fixture_config('HCWreckSalvageConfig', {'BudgetRollSides':1})
        env = dict(HCWreckSalvageConfig=N(Get=lambda:config), HCWreckSalvage=N(Roll=lambda key,sides:sides-1))
        fn = translate((WORLD/'Vehicles/HCWreckSalvage.c').read_text(),'Budget',env,'HCWreckSalvage')
        self.assertEqual(1,fn('synthetic-wreck-key'))

if __name__ == '__main__': unittest.main()


class SurvivalProfilesShipInFriendBundle(unittest.TestCase):
    """Operator tuning profiles must survive the friend-bundle handoff."""

    def test_every_c3_profile_is_a_bundled_configuration_file(self):
        from tools.setup import friend_bundle
        for name in ('forage-config', 'vehicle-flip', 'wreck-salvage-config', 'fuel-siphon',
                     'signals', 'progression-config', 'radio'):
            self.assertIn('HollowCountry/%s.json' % name, friend_bundle.PROFILE_INCLUDE)

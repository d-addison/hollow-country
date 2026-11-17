

// Hollow Country DISPOSABLE taped-light geometry probe; observation only, no gameplay acceptance.
// Host, light and slot data are inlined literals. Server only; runs once per process.
// Every spawned object is tracked and deleted; output is one bounded JSON plus a sentinel.
// Limits: the per-class timeout is checked after every observation (including the last) and the
// watchdog fires between steps. The watchdog cannot interrupt a synchronous call that never returns;
// a hung engine call hangs the probe and the launcher's wait limit is the only outer bound.
class HCDisposableDiagnosticMission : CustomMission
{
    protected bool m_HCTLStarted = false;
    protected bool m_HCTLDone = false;
    protected bool m_HCTLClassTimedOut = false;
    protected int m_HCTLCursor = 0;
    protected int m_HCTLHardCap = 0;
    protected int m_HCTLPerClassMs = 0;
    protected int m_HCTLBeginMs = 0;
    protected int m_HCTLEndMs = 0;
    protected int m_HCTLSpawned = 0;
    protected int m_HCTLDeleted = 0;
    protected int m_HCTLTimeouts = 0;
    protected int m_HCTLAttachOk = 0;
    protected int m_HCTLResidualProbe = 0;
    protected int m_HCTLResidualOther = 0;
    protected int m_HCTLCensusTotal = 0;
    protected int m_HCTLCensusScanned = 0;
    protected bool m_HCTLCensusTruncated = false;
    protected int m_HCTLLiveAfterRelease = 0;
    protected string m_HCTLQuote = "";
    protected string m_HCTLSlash = "";
    protected string m_HCTLStatus = "running";
    protected vector m_HCTLPos;
    protected ref array<string> m_HCTLClasses = new array<string>;
    protected ref array<string> m_HCTLRoots = new array<string>;
    protected ref array<int> m_HCTLGroups = new array<int>;
    protected ref array<string> m_HCTLLights = new array<string>;
    protected ref array<string> m_HCTLSlots = new array<string>;
    protected ref array<string> m_HCTLPrereqSlots = new array<string>;
    protected ref array<string> m_HCTLPrereqTypes = new array<string>;
    protected ref array<string> m_HCTLPrereqLights = new array<string>;
    protected ref array<Object> m_HCTLLive = new array<Object>;
    protected ref array<Object> m_HCTLReleased = new array<Object>;
    protected ref array<string> m_HCTLRows = new array<string>;
    protected ref array<string> m_HCTLLightRows = new array<string>;
    protected ref array<string> m_HCTLSlotRows = new array<string>;
    protected ref array<int> m_HCTLBoneIndex = new array<int>;
    protected ref array<string> m_HCTLBoneNames = new array<string>;
    protected ref array<int> m_HCTLBoneTried = new array<int>;
    protected string m_HCTLControlRow = "";

    override void OnInit()
    {
        super.OnInit();
        if (!GetGame() || !GetGame().IsServer() || m_HCTLStarted)
            return;
        m_HCTLStarted = true;
        m_HCTLHardCap = 600;
        m_HCTLPerClassMs = 2000;
        int quoteCode = 34;
        m_HCTLQuote = quoteCode.AsciiToString();
        int slashCode = 92;
        m_HCTLSlash = slashCode.AsciiToString();
        HCTLLoadMeta();
        HCTLLoadHosts0();
        HCTLLoadHosts1();
        HCTLLoadHosts2();
        HCTLLoadHosts3();
        HCTLLoadHosts4();
        HCTLLoadHosts5();
        HCTLLoadHosts6();
        HCTLLoadHosts7();
        HCTLLoadHosts8();
        HCTLLoadHosts9();
        HCTLLoadHosts10();
        HCTLLoadHosts11();
        if (m_HCTLClasses.Count() > m_HCTLHardCap)
        {
            Print("[HC Taped Light Probe] FAILED class count exceeds the hard cap");
            return;
        }
        float surfaceY = GetGame().SurfaceY(7680.0, 7680.0);
        m_HCTLPos = Vector(7680.0, surfaceY + 1.0, 7680.0);
        Print("[HC Taped Light Probe] ARMED; observation only; classes=" + m_HCTLClasses.Count().ToString());
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTLStep, 25000, false);
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTLWatchdog, 997250, false);
    }

    void HCTLAddHost(string className, string rootName, int group)
    {
        m_HCTLClasses.Insert(className);
        m_HCTLRoots.Insert(rootName);
        m_HCTLGroups.Insert(group);
    }

    void HCTLAddLight(string lightName)
    {
        m_HCTLLights.Insert(lightName);
    }

    void HCTLAddSlot(string slotName)
    {
        m_HCTLSlots.Insert(slotName);
    }

    void HCTLAddPrereq(string slotName, string handguardType)
    {
        m_HCTLPrereqSlots.Insert(slotName);
        m_HCTLPrereqTypes.Insert(handguardType);
    }

    void HCTLAddPrereqLight(string lightName)
    {
        m_HCTLPrereqLights.Insert(lightName);
    }

    void HCTLLoadMeta()
    {
        HCTLAddLight("Flashlight");
        HCTLAddLight("TLRLight");
        HCTLAddLight("UniversalLight");
        HCTLAddSlot("helmetFlashlight");
        HCTLAddSlot("pistolFlashlight");
        HCTLAddSlot("weaponFlashlight");
        HCTLAddPrereq("weaponHandguardAK", "AK_RailHndgrd");
        HCTLAddPrereq("weaponHandguardM4", "M4_RISHndgrd");
        HCTLAddPrereq("weaponHandguardMP5", "MP5_RailHndgrd");
        HCTLAddPrereqLight("UniversalLight");
    }

    void HCTLLoadHosts0()
    {
        HCTLAddHost("AK101", "CfgWeapons", 1);
        HCTLAddHost("AK101_Black", "CfgWeapons", 1);
        HCTLAddHost("AK101_Green", "CfgWeapons", 1);
        HCTLAddHost("AK74", "CfgWeapons", 1);
        HCTLAddHost("AK74_Black", "CfgWeapons", 1);
        HCTLAddHost("AK74_Green", "CfgWeapons", 1);
        HCTLAddHost("AKM", "CfgWeapons", 1);
        HCTLAddHost("AKM_Gold", "CfgWeapons", 1);
        HCTLAddHost("ASVAL", "CfgWeapons", 1);
        HCTLAddHost("Aug", "CfgWeapons", 1);
        HCTLAddHost("Colt1911", "CfgWeapons", 1);
        HCTLAddHost("CZ75", "CfgWeapons", 1);
        HCTLAddHost("Engraved1911", "CfgWeapons", 1);
        HCTLAddHost("FNX45", "CfgWeapons", 1);
        HCTLAddHost("FNX45_arrow", "CfgWeapons", 1);
        HCTLAddHost("Glock19", "CfgWeapons", 1);
        HCTLAddHost("Glock19_Tan", "CfgWeapons", 1);
        HCTLAddHost("M4A1", "CfgWeapons", 1);
        HCTLAddHost("M4A1_Black", "CfgWeapons", 1);
        HCTLAddHost("M4A1_Green", "CfgWeapons", 1);
        HCTLAddHost("Mich2001Helmet", "CfgVehicles", 1);
        HCTLAddHost("MP5K", "CfgWeapons", 1);
        HCTLAddHost("R12", "CfgWeapons", 1);
        HCTLAddHost("SCARH", "CfgWeapons", 1);
        HCTLAddHost("SCARH_Black", "CfgWeapons", 1);
        HCTLAddHost("SCARL", "CfgWeapons", 1);
        HCTLAddHost("SCARL_Black", "CfgWeapons", 1);
        HCTLAddHost("UMP45", "CfgWeapons", 1);
        HCTLAddHost("AKS74U", "CfgWeapons", 0);
        HCTLAddHost("AKS74U_Black", "CfgWeapons", 0);
        HCTLAddHost("AKS74U_Green", "CfgWeapons", 0);
        HCTLAddHost("AliceBag_Black", "CfgVehicles", 0);
        HCTLAddHost("AliceBag_Camo", "CfgVehicles", 0);
        HCTLAddHost("AliceBag_FarBubble", "CfgVehicles", 0);
        HCTLAddHost("AliceBag_Green", "CfgVehicles", 0);
        HCTLAddHost("AliceBag_NearBubble", "CfgVehicles", 0);
        HCTLAddHost("ArmyPouch_Beige", "CfgVehicles", 0);
        HCTLAddHost("ArmyPouch_Black", "CfgVehicles", 0);
        HCTLAddHost("ArmyPouch_Camo", "CfgVehicles", 0);
        HCTLAddHost("ArmyPouch_Green", "CfgVehicles", 0);
    }

    void HCTLLoadHosts1()
    {
        HCTLAddHost("AssaultBag_Black", "CfgVehicles", 0);
        HCTLAddHost("AssaultBag_Desert", "CfgVehicles", 0);
        HCTLAddHost("AssaultBag_Green", "CfgVehicles", 0);
        HCTLAddHost("AssaultBag_Ttsko", "CfgVehicles", 0);
        HCTLAddHost("AssaultBag_Winter", "CfgVehicles", 0);
        HCTLAddHost("Attack2Bag_Black", "CfgVehicles", 0);
        HCTLAddHost("Attack2Bag_Green", "CfgVehicles", 0);
        HCTLAddHost("Attack2Bag_Ttsko", "CfgVehicles", 0);
        HCTLAddHost("Attack2Bag_Yeger", "CfgVehicles", 0);
        HCTLAddHost("AugShort", "CfgWeapons", 0);
        HCTLAddHost("B95", "CfgWeapons", 0);
        HCTLAddHost("B95_Black", "CfgWeapons", 0);
        HCTLAddHost("B95_Green", "CfgWeapons", 0);
        HCTLAddHost("BallisticHelmet_BDU", "CfgVehicles", 0);
        HCTLAddHost("BallisticHelmet_Black", "CfgVehicles", 0);
        HCTLAddHost("BallisticHelmet_Desert", "CfgVehicles", 0);
        HCTLAddHost("BallisticHelmet_Green", "CfgVehicles", 0);
        HCTLAddHost("BallisticHelmet_Navy", "CfgVehicles", 0);
        HCTLAddHost("BallisticHelmet_UN", "CfgVehicles", 0);
        HCTLAddHost("BallisticHelmet_Winter", "CfgVehicles", 0);
        HCTLAddHost("BallisticHelmet_Woodland", "CfgVehicles", 0);
        HCTLAddHost("Bandana_BlackPattern", "CfgVehicles", 0);
        HCTLAddHost("Bandana_Blue", "CfgVehicles", 0);
        HCTLAddHost("Bandana_CamoPattern", "CfgVehicles", 0);
        HCTLAddHost("Bandana_Greenpattern", "CfgVehicles", 0);
        HCTLAddHost("Bandana_Pink", "CfgVehicles", 0);
        HCTLAddHost("Bandana_PolkaPattern", "CfgVehicles", 0);
        HCTLAddHost("Bandana_RedPattern", "CfgVehicles", 0);
        HCTLAddHost("Bandana_Yellow", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_Beige", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_Black", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_Blue", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_Camo", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_CMMG_Black", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_CMMG_Pink", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_Olive", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_Pink", "CfgVehicles", 0);
        HCTLAddHost("BaseballCap_Red", "CfgVehicles", 0);
        HCTLAddHost("BeanieHat_Beige", "CfgVehicles", 0);
        HCTLAddHost("BeanieHat_Black", "CfgVehicles", 0);
    }

    void HCTLLoadHosts2()
    {
        HCTLAddHost("BeanieHat_Blue", "CfgVehicles", 0);
        HCTLAddHost("BeanieHat_Brown", "CfgVehicles", 0);
        HCTLAddHost("BeanieHat_Green", "CfgVehicles", 0);
        HCTLAddHost("BeanieHat_Grey", "CfgVehicles", 0);
        HCTLAddHost("BeanieHat_Pink", "CfgVehicles", 0);
        HCTLAddHost("BeanieHat_Red", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Black", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Blue", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Desert", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_DPM", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Dubok", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Flecktran", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_NavyBlue", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Olive", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Orange", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Red", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Tan", "CfgVehicles", 0);
        HCTLAddHost("BoonieHat_Winter", "CfgVehicles", 0);
        HCTLAddHost("BudenovkaHat_Gray", "CfgVehicles", 0);
        HCTLAddHost("BurlapSackCover", "CfgVehicles", 0);
        HCTLAddHost("CanvasBag_Medical", "CfgVehicles", 0);
        HCTLAddHost("CanvasBag_Olive", "CfgVehicles", 0);
        HCTLAddHost("Chainmail_Coif", "CfgVehicles", 0);
        HCTLAddHost("ChildBag_Blue", "CfgVehicles", 0);
        HCTLAddHost("ChildBag_Green", "CfgVehicles", 0);
        HCTLAddHost("ChildBag_Red", "CfgVehicles", 0);
        HCTLAddHost("ChristmasHeadband_Antlers", "CfgVehicles", 0);
        HCTLAddHost("ChristmasHeadband_Gingerbread", "CfgVehicles", 0);
        HCTLAddHost("ChristmasHeadband_Lights_Antlers", "CfgVehicles", 0);
        HCTLAddHost("ChristmasHeadband_Lights_Gingerbread", "CfgVehicles", 0);
        HCTLAddHost("ChristmasHeadband_Lights_Trees", "CfgVehicles", 0);
        HCTLAddHost("ChristmasHeadband_Trees", "CfgVehicles", 0);
        HCTLAddHost("ConstructionHelmet_Blue", "CfgVehicles", 0);
        HCTLAddHost("ConstructionHelmet_Lime", "CfgVehicles", 0);
        HCTLAddHost("ConstructionHelmet_Orange", "CfgVehicles", 0);
        HCTLAddHost("ConstructionHelmet_Red", "CfgVehicles", 0);
        HCTLAddHost("ConstructionHelmet_White", "CfgVehicles", 0);
        HCTLAddHost("ConstructionHelmet_Yellow", "CfgVehicles", 0);
        HCTLAddHost("CourierBag", "CfgVehicles", 0);
        HCTLAddHost("CowboyHat_black", "CfgVehicles", 0);
    }

    void HCTLLoadHosts3()
    {
        HCTLAddHost("CowboyHat_Brown", "CfgVehicles", 0);
        HCTLAddHost("CowboyHat_darkBrown", "CfgVehicles", 0);
        HCTLAddHost("CowboyHat_green", "CfgVehicles", 0);
        HCTLAddHost("CoyoteBag_Brown", "CfgVehicles", 0);
        HCTLAddHost("CoyoteBag_Desert", "CfgVehicles", 0);
        HCTLAddHost("CoyoteBag_Green", "CfgVehicles", 0);
        HCTLAddHost("CoyoteBag_Winter", "CfgVehicles", 0);
        HCTLAddHost("Crossbow", "CfgWeapons", 0);
        HCTLAddHost("Crossbow_Autumn", "CfgWeapons", 0);
        HCTLAddHost("Crossbow_Black", "CfgWeapons", 0);
        HCTLAddHost("Crossbow_Summer", "CfgWeapons", 0);
        HCTLAddHost("Crossbow_Wood", "CfgWeapons", 0);
        HCTLAddHost("CZ527", "CfgWeapons", 0);
        HCTLAddHost("CZ527_Black", "CfgWeapons", 0);
        HCTLAddHost("CZ527_Camo", "CfgWeapons", 0);
        HCTLAddHost("CZ527_desert", "CfgWeapons", 0);
        HCTLAddHost("CZ527_Green", "CfgWeapons", 0);
        HCTLAddHost("CZ527_winter", "CfgWeapons", 0);
        HCTLAddHost("CZ527_Woodland", "CfgWeapons", 0);
        HCTLAddHost("CZ550", "CfgWeapons", 0);
        HCTLAddHost("CZ61", "CfgWeapons", 0);
        HCTLAddHost("DarkMotoHelmet_Black", "CfgVehicles", 0);
        HCTLAddHost("DarkMotoHelmet_Blue", "CfgVehicles", 0);
        HCTLAddHost("DarkMotoHelmet_Green", "CfgVehicles", 0);
        HCTLAddHost("DarkMotoHelmet_Grey", "CfgVehicles", 0);
        HCTLAddHost("DarkMotoHelmet_Lime", "CfgVehicles", 0);
        HCTLAddHost("DarkMotoHelmet_Red", "CfgVehicles", 0);
        HCTLAddHost("DarkMotoHelmet_White", "CfgVehicles", 0);
        HCTLAddHost("DarkMotoHelmet_Yellow", "CfgVehicles", 0);
        HCTLAddHost("DarkMotoHelmet_YellowScarred", "CfgVehicles", 0);
        HCTLAddHost("DartGun", "CfgWeapons", 0);
        HCTLAddHost("Deagle", "CfgWeapons", 0);
        HCTLAddHost("Deagle_Gold", "CfgWeapons", 0);
        HCTLAddHost("Derringer_Black", "CfgWeapons", 0);
        HCTLAddHost("Derringer_Grey", "CfgWeapons", 0);
        HCTLAddHost("Derringer_Pink", "CfgWeapons", 0);
        HCTLAddHost("DirtBikeHelmet_Black", "CfgVehicles", 0);
        HCTLAddHost("DirtBikeHelmet_Blue", "CfgVehicles", 0);
        HCTLAddHost("DirtBikeHelmet_Chernarus", "CfgVehicles", 0);
        HCTLAddHost("DirtBikeHelmet_Green", "CfgVehicles", 0);
    }

    void HCTLLoadHosts4()
    {
        HCTLAddHost("DirtBikeHelmet_Khaki", "CfgVehicles", 0);
        HCTLAddHost("DirtBikeHelmet_Police", "CfgVehicles", 0);
        HCTLAddHost("DirtBikeHelmet_Red", "CfgVehicles", 0);
        HCTLAddHost("DryBag_Black", "CfgVehicles", 0);
        HCTLAddHost("DryBag_Blue", "CfgVehicles", 0);
        HCTLAddHost("DryBag_Green", "CfgVehicles", 0);
        HCTLAddHost("DryBag_Orange", "CfgVehicles", 0);
        HCTLAddHost("DryBag_Red", "CfgVehicles", 0);
        HCTLAddHost("DryBag_Yellow", "CfgVehicles", 0);
        HCTLAddHost("DrysackBag_Green", "CfgVehicles", 0);
        HCTLAddHost("DrysackBag_Orange", "CfgVehicles", 0);
        HCTLAddHost("DrysackBag_Yellow", "CfgVehicles", 0);
        HCTLAddHost("DuffelBagSmall_Camo", "CfgVehicles", 0);
        HCTLAddHost("DuffelBagSmall_Green", "CfgVehicles", 0);
        HCTLAddHost("DuffelBagSmall_Medical", "CfgVehicles", 0);
        HCTLAddHost("FAL", "CfgWeapons", 0);
        HCTLAddHost("FAMAS", "CfgWeapons", 0);
        HCTLAddHost("FirefightersHelmet_Red", "CfgVehicles", 0);
        HCTLAddHost("FirefightersHelmet_White", "CfgVehicles", 0);
        HCTLAddHost("FirefightersHelmet_Yellow", "CfgVehicles", 0);
        HCTLAddHost("Flaregun", "CfgWeapons", 0);
        HCTLAddHost("FlatCap_Black", "CfgVehicles", 0);
        HCTLAddHost("FlatCap_BlackCheck", "CfgVehicles", 0);
        HCTLAddHost("FlatCap_Blue", "CfgVehicles", 0);
        HCTLAddHost("FlatCap_Brown", "CfgVehicles", 0);
        HCTLAddHost("FlatCap_BrownCheck", "CfgVehicles", 0);
        HCTLAddHost("FlatCap_Grey", "CfgVehicles", 0);
        HCTLAddHost("FlatCap_GreyCheck", "CfgVehicles", 0);
        HCTLAddHost("FlatCap_Red", "CfgVehicles", 0);
        HCTLAddHost("FurCourierBag", "CfgVehicles", 0);
        HCTLAddHost("FurImprovisedBag", "CfgVehicles", 0);
        HCTLAddHost("GhillieBushrag_Desert", "CfgVehicles", 0);
        HCTLAddHost("GhillieBushrag_Mossy", "CfgVehicles", 0);
        HCTLAddHost("GhillieBushrag_Tan", "CfgVehicles", 0);
        HCTLAddHost("GhillieBushrag_Winter", "CfgVehicles", 0);
        HCTLAddHost("GhillieBushrag_Woodland", "CfgVehicles", 0);
        HCTLAddHost("GhillieHood_Desert", "CfgVehicles", 0);
        HCTLAddHost("GhillieHood_Mossy", "CfgVehicles", 0);
        HCTLAddHost("GhillieHood_Tan", "CfgVehicles", 0);
        HCTLAddHost("GhillieHood_Winter", "CfgVehicles", 0);
    }

    void HCTLLoadHosts5()
    {
        HCTLAddHost("GhillieHood_Woodland", "CfgVehicles", 0);
        HCTLAddHost("GhillieSuit_Desert", "CfgVehicles", 0);
        HCTLAddHost("GhillieSuit_Mossy", "CfgVehicles", 0);
        HCTLAddHost("GhillieSuit_Tan", "CfgVehicles", 0);
        HCTLAddHost("GhillieSuit_Winter", "CfgVehicles", 0);
        HCTLAddHost("GhillieSuit_Woodland", "CfgVehicles", 0);
        HCTLAddHost("GhillieTop_Desert", "CfgVehicles", 0);
        HCTLAddHost("GhillieTop_Mossy", "CfgVehicles", 0);
        HCTLAddHost("GhillieTop_Tan", "CfgVehicles", 0);
        HCTLAddHost("GhillieTop_Winter", "CfgVehicles", 0);
        HCTLAddHost("GhillieTop_Woodland", "CfgVehicles", 0);
        HCTLAddHost("GorkaHelmet", "CfgVehicles", 0);
        HCTLAddHost("GorkaHelmet_Black", "CfgVehicles", 0);
        HCTLAddHost("GorkaHelmet_Green", "CfgVehicles", 0);
        HCTLAddHost("GP25", "CfgWeapons", 0);
        HCTLAddHost("GP25_Standalone", "CfgWeapons", 0);
        HCTLAddHost("GreatHelm", "CfgVehicles", 0);
        HCTLAddHost("Groza", "CfgWeapons", 0);
        HCTLAddHost("HeadCover_Improvised", "CfgVehicles", 0);
        HCTLAddHost("Headdress_Bear", "CfgVehicles", 0);
        HCTLAddHost("Headdress_Fox", "CfgVehicles", 0);
        HCTLAddHost("Headdress_Wolf", "CfgVehicles", 0);
        HCTLAddHost("HockeyHelmet_Black", "CfgVehicles", 0);
        HCTLAddHost("HockeyHelmet_Blue", "CfgVehicles", 0);
        HCTLAddHost("HockeyHelmet_Red", "CfgVehicles", 0);
        HCTLAddHost("HockeyHelmet_White", "CfgVehicles", 0);
        HCTLAddHost("HuntingBag", "CfgVehicles", 0);
        HCTLAddHost("HuntingBag_Hannah", "CfgVehicles", 0);
        HCTLAddHost("ImprovisedBag", "CfgVehicles", 0);
        HCTLAddHost("Izh18", "CfgWeapons", 0);
        HCTLAddHost("Izh18Shotgun", "CfgWeapons", 0);
        HCTLAddHost("Izh43Shotgun", "CfgWeapons", 0);
        HCTLAddHost("Keffiyeh_Black", "CfgVehicles", 0);
        HCTLAddHost("Keffiyeh_Blue", "CfgVehicles", 0);
        HCTLAddHost("Keffiyeh_Brown", "CfgVehicles", 0);
        HCTLAddHost("Keffiyeh_Gray", "CfgVehicles", 0);
        HCTLAddHost("Keffiyeh_LightBlue", "CfgVehicles", 0);
        HCTLAddHost("Keffiyeh_LightBrown", "CfgVehicles", 0);
        HCTLAddHost("Keffiyeh_LightRed", "CfgVehicles", 0);
        HCTLAddHost("Keffiyeh_Red", "CfgVehicles", 0);
    }

    void HCTLLoadHosts6()
    {
        HCTLAddHost("LargeTentBackPack", "CfgVehicles", 0);
        HCTLAddHost("LAW", "CfgWeapons", 0);
        HCTLAddHost("LeafCrown_Autumn", "CfgVehicles", 0);
        HCTLAddHost("LeafCrown_Spring", "CfgVehicles", 0);
        HCTLAddHost("LeafCrown_Summer", "CfgVehicles", 0);
        HCTLAddHost("LeafCrown_Winter", "CfgVehicles", 0);
        HCTLAddHost("LeatherHat_Beige", "CfgVehicles", 0);
        HCTLAddHost("LeatherHat_Black", "CfgVehicles", 0);
        HCTLAddHost("LeatherHat_Brown", "CfgVehicles", 0);
        HCTLAddHost("LeatherHat_Natural", "CfgVehicles", 0);
        HCTLAddHost("LeatherSack_Beige", "CfgVehicles", 0);
        HCTLAddHost("LeatherSack_Black", "CfgVehicles", 0);
        HCTLAddHost("LeatherSack_Brown", "CfgVehicles", 0);
        HCTLAddHost("LeatherSack_Natural", "CfgVehicles", 0);
        HCTLAddHost("LeeEnfield", "CfgWeapons", 0);
        HCTLAddHost("LongHorn", "CfgWeapons", 0);
        HCTLAddHost("Luger", "CfgWeapons", 0);
        HCTLAddHost("M14", "CfgWeapons", 0);
        HCTLAddHost("M16A2", "CfgWeapons", 0);
        HCTLAddHost("M203", "CfgWeapons", 0);
        HCTLAddHost("M203_Standalone", "CfgWeapons", 0);
        HCTLAddHost("M249", "CfgWeapons", 0);
        HCTLAddHost("M79", "CfgWeapons", 0);
        HCTLAddHost("Magnum", "CfgWeapons", 0);
        HCTLAddHost("Magnum_Gold", "CfgWeapons", 0);
        HCTLAddHost("MakarovIJ70", "CfgWeapons", 0);
        HCTLAddHost("MakarovPB", "CfgWeapons", 0);
        HCTLAddHost("MedicalScrubsHat_Blue", "CfgVehicles", 0);
        HCTLAddHost("MedicalScrubsHat_Green", "CfgVehicles", 0);
        HCTLAddHost("MedicalScrubsHat_White", "CfgVehicles", 0);
        HCTLAddHost("MilitaryBeret_CDF", "CfgVehicles", 0);
        HCTLAddHost("MilitaryBeret_ChDKZ", "CfgVehicles", 0);
        HCTLAddHost("MilitaryBeret_NZ", "CfgVehicles", 0);
        HCTLAddHost("MilitaryBeret_Red", "CfgVehicles", 0);
        HCTLAddHost("MilitaryBeret_TK", "CfgVehicles", 0);
        HCTLAddHost("MilitaryBeret_UN", "CfgVehicles", 0);
        HCTLAddHost("MilitaryCap_BDU", "CfgVehicles", 0);
        HCTLAddHost("MilitaryCap_Desert", "CfgVehicles", 0);
        HCTLAddHost("MilitaryCap_Woodland", "CfgVehicles", 0);
        HCTLAddHost("MKII", "CfgWeapons", 0);
    }

    void HCTLLoadHosts7()
    {
        HCTLAddHost("MorozkoHat", "CfgVehicles", 0);
        HCTLAddHost("Mosin9130", "CfgWeapons", 0);
        HCTLAddHost("Mosin9130_Black", "CfgWeapons", 0);
        HCTLAddHost("Mosin9130_Camo", "CfgWeapons", 0);
        HCTLAddHost("Mosin9130_Desert", "CfgWeapons", 0);
        HCTLAddHost("Mosin9130_Green", "CfgWeapons", 0);
        HCTLAddHost("Mosin9130_Winter", "CfgWeapons", 0);
        HCTLAddHost("Mosin9130_Woodland", "CfgWeapons", 0);
        HCTLAddHost("MotoHelmet_Black", "CfgVehicles", 0);
        HCTLAddHost("MotoHelmet_Blue", "CfgVehicles", 0);
        HCTLAddHost("MotoHelmet_Green", "CfgVehicles", 0);
        HCTLAddHost("MotoHelmet_Grey", "CfgVehicles", 0);
        HCTLAddHost("MotoHelmet_Lime", "CfgVehicles", 0);
        HCTLAddHost("MotoHelmet_Red", "CfgVehicles", 0);
        HCTLAddHost("MotoHelmet_White", "CfgVehicles", 0);
        HCTLAddHost("MotoHelmet_Yellow", "CfgVehicles", 0);
        HCTLAddHost("MountainBag_Blue", "CfgVehicles", 0);
        HCTLAddHost("MountainBag_Green", "CfgVehicles", 0);
        HCTLAddHost("MountainBag_Orange", "CfgVehicles", 0);
        HCTLAddHost("MountainBag_Red", "CfgVehicles", 0);
        HCTLAddHost("Mp133Shotgun", "CfgWeapons", 0);
        HCTLAddHost("Mp133Shotgun_PistolGrip", "CfgWeapons", 0);
        HCTLAddHost("MP18", "CfgWeapons", 0);
        HCTLAddHost("NBCHoodGray", "CfgVehicles", 0);
        HCTLAddHost("NBCHoodWhite", "CfgVehicles", 0);
        HCTLAddHost("NBCHoodYellow", "CfgVehicles", 0);
        HCTLAddHost("NorseHelm", "CfgVehicles", 0);
        HCTLAddHost("OBRCap_Beige", "CfgVehicles", 0);
        HCTLAddHost("OBRCap_Olive", "CfgVehicles", 0);
        HCTLAddHost("OfficerHat", "CfgVehicles", 0);
        HCTLAddHost("OKZKCap_Beige", "CfgVehicles", 0);
        HCTLAddHost("OKZKCap_Green", "CfgVehicles", 0);
        HCTLAddHost("P1", "CfgWeapons", 0);
        HCTLAddHost("PakolHat_Beige", "CfgVehicles", 0);
        HCTLAddHost("PakolHat_Black", "CfgVehicles", 0);
        HCTLAddHost("PakolHat_Brown", "CfgVehicles", 0);
        HCTLAddHost("PakolHat_Grey", "CfgVehicles", 0);
        HCTLAddHost("PakolHat_White", "CfgVehicles", 0);
        HCTLAddHost("PetushokHat_Black", "CfgVehicles", 0);
        HCTLAddHost("PetushokHat_Green", "CfgVehicles", 0);
    }

    void HCTLLoadHosts8()
    {
        HCTLAddHost("PetushokHat_Yellow", "CfgVehicles", 0);
        HCTLAddHost("PilotkaCap", "CfgVehicles", 0);
        HCTLAddHost("PM73Rak", "CfgWeapons", 0);
        HCTLAddHost("PoliceCap", "CfgVehicles", 0);
        HCTLAddHost("PP19", "CfgWeapons", 0);
        HCTLAddHost("PrisonerCap", "CfgVehicles", 0);
        HCTLAddHost("PumpkinHelmet", "CfgVehicles", 0);
        HCTLAddHost("PVCBow", "CfgWeapons", 0);
        HCTLAddHost("QuickieBow", "CfgWeapons", 0);
        HCTLAddHost("RadarCap_Black", "CfgVehicles", 0);
        HCTLAddHost("RadarCap_Blue", "CfgVehicles", 0);
        HCTLAddHost("RadarCap_Brown", "CfgVehicles", 0);
        HCTLAddHost("RadarCap_Green", "CfgVehicles", 0);
        HCTLAddHost("RadarCap_Red", "CfgVehicles", 0);
        HCTLAddHost("RecurveBow", "CfgWeapons", 0);
        HCTLAddHost("Red9", "CfgWeapons", 0);
        HCTLAddHost("Repeater", "CfgWeapons", 0);
        HCTLAddHost("RPG7", "CfgWeapons", 0);
        HCTLAddHost("Ruger1022", "CfgWeapons", 0);
        HCTLAddHost("Saiga", "CfgWeapons", 0);
        HCTLAddHost("SantasHat", "CfgVehicles", 0);
        HCTLAddHost("SawedoffB95", "CfgWeapons", 0);
        HCTLAddHost("SawedoffFAMAS", "CfgWeapons", 0);
        HCTLAddHost("SawedoffIzh18", "CfgWeapons", 0);
        HCTLAddHost("SawedoffIzh18Shotgun", "CfgWeapons", 0);
        HCTLAddHost("SawedoffIzh43Shotgun", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMagnum", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMagnum_Gold", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMosin9130", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMosin9130_Black", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMosin9130_Camo", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMosin9130_Desert", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMosin9130_Green", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMosin9130_Winter", "CfgWeapons", 0);
        HCTLAddHost("SawedoffMosin9130_Woodland", "CfgWeapons", 0);
        HCTLAddHost("Scout", "CfgWeapons", 0);
        HCTLAddHost("Scout_Chernarus", "CfgWeapons", 0);
        HCTLAddHost("Scout_Livonia", "CfgWeapons", 0);
        HCTLAddHost("Shemag_Brown", "CfgVehicles", 0);
        HCTLAddHost("Shemag_Green", "CfgVehicles", 0);
    }

    void HCTLLoadHosts9()
    {
        HCTLAddHost("Shemag_Red", "CfgVehicles", 0);
        HCTLAddHost("Shemag_White", "CfgVehicles", 0);
        HCTLAddHost("SherpaHat_Black", "CfgVehicles", 0);
        HCTLAddHost("SherpaHat_Blue", "CfgVehicles", 0);
        HCTLAddHost("SherpaHat_Red", "CfgVehicles", 0);
        HCTLAddHost("Shockpistol", "CfgWeapons", 0);
        HCTLAddHost("Shockpistol_Black", "CfgWeapons", 0);
        HCTLAddHost("SkateHelmet_Black", "CfgVehicles", 0);
        HCTLAddHost("SkateHelmet_Blue", "CfgVehicles", 0);
        HCTLAddHost("SkateHelmet_Gray", "CfgVehicles", 0);
        HCTLAddHost("SkateHelmet_Green", "CfgVehicles", 0);
        HCTLAddHost("SkateHelmet_Red", "CfgVehicles", 0);
        HCTLAddHost("SKS", "CfgWeapons", 0);
        HCTLAddHost("SKS_Black", "CfgWeapons", 0);
        HCTLAddHost("SKS_Desert", "CfgWeapons", 0);
        HCTLAddHost("SKS_Green", "CfgWeapons", 0);
        HCTLAddHost("SKS_Winter", "CfgWeapons", 0);
        HCTLAddHost("SKS_Woodland", "CfgWeapons", 0);
        HCTLAddHost("SlingBag_Black", "CfgVehicles", 0);
        HCTLAddHost("SlingBag_Brown", "CfgVehicles", 0);
        HCTLAddHost("SlingBag_Gray", "CfgVehicles", 0);
        HCTLAddHost("SmershBag", "CfgVehicles", 0);
        HCTLAddHost("SnowstormUshanka_Brown", "CfgVehicles", 0);
        HCTLAddHost("SnowstormUshanka_Navy", "CfgVehicles", 0);
        HCTLAddHost("SnowstormUshanka_Olive", "CfgVehicles", 0);
        HCTLAddHost("SnowstormUshanka_White", "CfgVehicles", 0);
        HCTLAddHost("SSG82", "CfgWeapons", 0);
        HCTLAddHost("Ssh68Helmet", "CfgVehicles", 0);
        HCTLAddHost("SV98", "CfgWeapons", 0);
        HCTLAddHost("SVD", "CfgWeapons", 0);
        HCTLAddHost("SVD_Wooden", "CfgWeapons", 0);
        HCTLAddHost("T56TankerHelmet_Olive", "CfgVehicles", 0);
        HCTLAddHost("T56TankerHelmet_Tan", "CfgVehicles", 0);
        HCTLAddHost("TaloonBag_Blue", "CfgVehicles", 0);
        HCTLAddHost("TaloonBag_Green", "CfgVehicles", 0);
        HCTLAddHost("TaloonBag_Orange", "CfgVehicles", 0);
        HCTLAddHost("TaloonBag_Violet", "CfgVehicles", 0);
        HCTLAddHost("TankerHelmet", "CfgVehicles", 0);
        HCTLAddHost("TortillaBag", "CfgVehicles", 0);
        HCTLAddHost("TortillaBag_Desert", "CfgVehicles", 0);
    }

    void HCTLLoadHosts10()
    {
        HCTLAddHost("TortillaBag_Winter", "CfgVehicles", 0);
        HCTLAddHost("Trumpet", "CfgWeapons", 0);
        HCTLAddHost("TurbanHat_Beige", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_Black", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_Brown", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_Green", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_Grey", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_NavyBlue", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_Pink", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_Purple", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_Red", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_SkyBlue", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_White", "CfgVehicles", 0);
        HCTLAddHost("TurbanHat_Yellow", "CfgVehicles", 0);
        HCTLAddHost("UnderSlugGrenadeM4", "CfgWeapons", 0);
        HCTLAddHost("Ushanka_Black", "CfgVehicles", 0);
        HCTLAddHost("Ushanka_Blue", "CfgVehicles", 0);
        HCTLAddHost("Ushanka_Green", "CfgVehicles", 0);
        HCTLAddHost("Vikhr", "CfgWeapons", 0);
        HCTLAddHost("VSS", "CfgWeapons", 0);
        HCTLAddHost("WeldingMask", "CfgVehicles", 0);
        HCTLAddHost("Winchester70", "CfgWeapons", 0);
        HCTLAddHost("Winchester70_Black", "CfgWeapons", 0);
        HCTLAddHost("Winchester70_Green", "CfgWeapons", 0);
        HCTLAddHost("WinterCoif_Black", "CfgVehicles", 0);
        HCTLAddHost("WinterCoif_Blue", "CfgVehicles", 0);
        HCTLAddHost("WinterCoif_Green", "CfgVehicles", 0);
        HCTLAddHost("WinterCoif_Skull", "CfgVehicles", 0);
        HCTLAddHost("WitchHat", "CfgVehicles", 0);
        HCTLAddHost("WitchHood_Black", "CfgVehicles", 0);
        HCTLAddHost("WitchHood_Brown", "CfgVehicles", 0);
        HCTLAddHost("WitchHood_Red", "CfgVehicles", 0);
        HCTLAddHost("WitchHoodCoif_Black", "CfgVehicles", 0);
        HCTLAddHost("WitchHoodCoif_Brown", "CfgVehicles", 0);
        HCTLAddHost("WitchHoodCoif_Red", "CfgVehicles", 0);
        HCTLAddHost("ZmijovkaCap_Black", "CfgVehicles", 0);
        HCTLAddHost("ZmijovkaCap_Blue", "CfgVehicles", 0);
        HCTLAddHost("ZmijovkaCap_Brown", "CfgVehicles", 0);
        HCTLAddHost("ZmijovkaCap_Green", "CfgVehicles", 0);
        HCTLAddHost("ZmijovkaCap_Red", "CfgVehicles", 0);
    }

    void HCTLLoadHosts11()
    {
        HCTLAddHost("ZSh3PilotHelmet", "CfgVehicles", 0);
        HCTLAddHost("ZSh3PilotHelmet_Black", "CfgVehicles", 0);
        HCTLAddHost("ZSh3PilotHelmet_Green", "CfgVehicles", 0);
    }


    string HCTLKey(string name)
    {
        return m_HCTLQuote + name + m_HCTLQuote + ":";
    }

    string HCTLStr(string value)
    {
        string text = value;
        if (text.Length() > 96)
            text = text.Substring(0, 96);
        text.Replace(m_HCTLQuote, "'");
        text.Replace(m_HCTLSlash, "/");
        return m_HCTLQuote + text + m_HCTLQuote;
    }

    string HCTLBool(bool value)
    {
        if (value)
            return "true";
        return "false";
    }

    string HCTLVector(vector value)
    {
        return "[" + value[0].ToString() + "," + value[1].ToString() + "," + value[2].ToString() + "]";
    }

    // The single creation point of the probe. Round 8: the flags are a parameter so the one control spawn can leave out
    // ECE_IN_INVENTORY and show whether that flag changes what the model reports.
    Object HCTLSpawnFlags(string typeName, int spawnFlags)
    {
        Object created = GetGame().CreateObjectEx(typeName, m_HCTLPos, spawnFlags);
        if (created)
        {
            m_HCTLLive.Insert(created);
            m_HCTLSpawned = m_HCTLSpawned + 1;
        }
        return created;
    }

    Object HCTLSpawn(string typeName)
    {
        int spawnFlags = ECE_IN_INVENTORY | ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME;
        return HCTLSpawnFlags(typeName, spawnFlags);
    }

    void HCTLReleaseAll()
    {
        int releaseIndex = m_HCTLLive.Count() - 1;
        Object releaseItem = null;
        while (releaseIndex >= 0)
        {
            releaseItem = m_HCTLLive.Get(releaseIndex);
            if (releaseItem)
            {
                GetGame().ObjectDelete(releaseItem);
                m_HCTLDeleted = m_HCTLDeleted + 1;
                m_HCTLReleased.Insert(releaseItem);
            }
            releaseIndex = releaseIndex - 1;
        }
        m_HCTLLive.Clear();
    }

    void HCTLMeasureLive()
    {
        int liveIndex = 0;
        Object liveItem = null;
        m_HCTLLiveAfterRelease = m_HCTLLive.Count();
        while (liveIndex < m_HCTLReleased.Count())
        {
            liveItem = m_HCTLReleased.Get(liveIndex);
            if (liveItem)
                m_HCTLLiveAfterRelease = m_HCTLLiveAfterRelease + 1;
            liveIndex = liveIndex + 1;
        }
    }

    void HCTLStep()
    {
        if (m_HCTLDone)
            return;
        if (m_HCTLCursor == 0)
        {
            m_HCTLBeginMs = GetGame().GetTime();
            Print("[HC Taped Light Probe] BEGIN; observation only; classes=" + m_HCTLClasses.Count().ToString());
            HCTLObserveSlots();
            HCTLObserveLights();
            m_HCTLControlRow = HCTLObserveControl();
        }
        if (m_HCTLCursor < m_HCTLClasses.Count())
        {
            m_HCTLRows.Insert(HCTLObserveHost(m_HCTLCursor));
            m_HCTLCursor = m_HCTLCursor + 1;
            GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTLStep, 50, false);
            return;
        }
        HCTLFinish("complete");
    }

    void HCTLWatchdog()
    {
        if (m_HCTLDone)
            return;
        HCTLFinish("partial");
    }

    void HCTLFinish(string status)
    {
        if (m_HCTLDone)
            return;
        m_HCTLDone = true;
        m_HCTLStatus = status;
        m_HCTLEndMs = GetGame().GetTime();
        HCTLReleaseAll();
        GetGame().GetCallQueue(CALL_CATEGORY_SYSTEM).CallLater(HCTLWriteResult, 3000, false);
    }

    void HCTLObserveSlots()
    {
        int slotIndex = 0;
        string slotName = "";
        int slotId = 0;
        bool slotValid = false;
        string selection = "";
        string bone = "";
        bool selectionKnown = false;
        bool boneKnown = false;
        while (slotIndex < m_HCTLSlots.Count())
        {
            slotName = m_HCTLSlots.Get(slotIndex);
            slotIndex = slotIndex + 1;
            slotId = InventorySlots.GetSlotIdFromString(slotName);
            slotValid = InventorySlots.IsSlotIdValid(slotId);
            selection = "";
            bone = "";
            selectionKnown = false;
            boneKnown = false;
            if (slotValid)
            {
                selectionKnown = InventorySlots.GetSelectionForSlotId(slotId, selection);
                boneKnown = InventorySlots.GetBoneNameForSlotId(slotId, bone);
            }
            string slotRowText = "{" + HCTLKey("slot") + HCTLStr(slotName) + "," + HCTLKey("id") + slotId.ToString() + ",";
            slotRowText = slotRowText + HCTLKey("valid") + HCTLBool(slotValid) + "," + HCTLKey("selection") + HCTLStr(selection) + ",";
            slotRowText = slotRowText + HCTLKey("selection_known") + HCTLBool(selectionKnown) + "," + HCTLKey("bone") + HCTLStr(bone) + ",";
            slotRowText = slotRowText + HCTLKey("bone_known") + HCTLBool(boneKnown) + "}";
            m_HCTLSlotRows.Insert(slotRowText);
        }
    }

    bool HCTLRelevantName(string lowered)
    {
        if (lowered.IndexOf("flash") != -1)
            return true;
        if (lowered.IndexOf("light") != -1)
            return true;
        if (lowered.IndexOf("rail") != -1)
            return true;
        if (lowered.IndexOf("beam") != -1)
            return true;
        if (lowered.IndexOf("tape") != -1)
            return true;
        return false;
    }

    string HCTLSelectionFacts(Object subject)
    {
        TStringArray selectionNames = new TStringArray;
        subject.GetSelectionList(selectionNames);
        int total = selectionNames.Count();
        int scanLimit = total;
        if (scanLimit > 512)
            scanLimit = 512;
        int scan = 0;
        string selectionName = "";
        string lowered = "";
        string matches = "";
        int matchCount = 0;
        while (scan < scanLimit)
        {
            selectionName = selectionNames.Get(scan);
            scan = scan + 1;
            lowered = selectionName;
            lowered.ToLower();
            if (matchCount < 16 && HCTLRelevantName(lowered))
            {
                if (matchCount > 0)
                    matches = matches + ",";
                matches = matches + HCTLStr(selectionName);
                matchCount = matchCount + 1;
            }
        }
        return HCTLKey("selection_count") + total.ToString() + "," + HCTLKey("selection_matches") + "[" + matches + "]";
    }

    // Proxy join (probe-003: InventorySlots.GetSelectionForSlotId returned nothing natively, so the model evidence is a
    // proxy selection joined to its CfgNonAIVehicles entry, the pattern 4_World/Systems/Inventory/AttachmentsOutOfReach.c
    // :97-135 reads: inventorySlot at :105, model at :110). Native cache 1.30.164289:
    //   3_Game/Global/Game.c:449 ConfigGetText(path, out value); 3_Game/Global/Game.c:558 ConfigGetTextArray(path,
    //   out values); 3_Game/Global/Game.c:612 ConfigIsExisting(path); 3_Game/constants.c:237 CFG_NONAI_VEHICLES is
    //   "CfgNonAIVehicles"; 5_Mission/GUI/SceneEditorMenu.c:1362 reads inventorySlot as an array and
    //   5_Mission/GUI/SceneEditorMenu.c:1385 falls back to the text form, as does 3_Game/Entities/EntityAI.c:3996;
    //   1_Core/proto/EnString.c:113 Substring, EnString.c:171 ToLower, EnString.c:240 IndexOf, EnString.c:253 LastIndexOf
    //   (measured only by the header self-test, never relied on below) and EnString.c:271 IndexOfFrom(int start, string sample).
    // Fix round 6 (probe-004: cfg_class came out as "Proxy/dz/..." and no config entry was found on 614 rows). The earlier
    // code looked for "/" in the RAW selection name and only afterwards (in HCTLStr) were backslashes turned into "/", so a
    // raw name with backslashes kept its whole path in the class. The separators are therefore normalised FIRST
    // (Replace of the backslash string, the same call HCTLViewKey uses) and the last separator and dot are found by a
    // bounded forward scan with IndexOf/IndexOfFrom, so LastIndexOf is not needed. Whether the raw names hold backslashes
    // is measured per row (sep_slash, sep_backslash) and LastIndexOf itself by the header self-test; neither is assumed.
    int HCTLLastPos(string text, string mark)
    {
        int lastPos = -1;
        int foundPos = text.IndexOf(mark);
        int guard = 0;
        while (foundPos != -1 && guard < 256)
        {
            lastPos = foundPos;
            guard = guard + 1;
            if (foundPos + 1 >= text.Length())
                break;
            foundPos = text.IndexOfFrom(foundPos + 1, mark);
        }
        return lastPos;
    }

    int HCTLCountChar(string text, string mark)
    {
        int markCount = 0;
        int foundPos = text.IndexOf(mark);
        while (foundPos != -1 && markCount < 256)
        {
            markCount = markCount + 1;
            if (foundPos + 1 >= text.Length())
                break;
            foundPos = text.IndexOfFrom(foundPos + 1, mark);
        }
        return markCount;
    }

    string HCTLProxyBase(string selectionName)
    {
        string text = selectionName.Substring(6, selectionName.Length() - 6);
        text.Replace(m_HCTLSlash, "/");
        int cutPos = HCTLLastPos(text, "/");
        if (cutPos != -1)
            text = text.Substring(cutPos + 1, text.Length() - cutPos - 1);
        cutPos = HCTLLastPos(text, ".");
        if (cutPos != -1)
            text = text.Substring(0, cutPos);
        return text;
    }

    // Resolution-LOD join (round 7, replacing the view-LOD join of rounds 4 to 6). taped-light-probe-005 measured that no
    // dedicated-server host has a LOD named "view" (the view LOD 4_World/Systems/Inventory/AttachmentsOutOfReach.c:112-131
    // reads belongs to a client inventory helper, not to the visible model). The LOD names are resolution LODs ("0", "1",
    // "1.000", some repeated), geometry, memory, landContact, geometryView, geometryFire and VIEW_PILOT. The model proxy
    // slot is therefore looked up in the RESOLUTION LODs only: every LOD whose WHOLE name is a non-negative number is
    // scanned and no other LOD (geometry, memory, view*, VIEW_PILOT, any non-numeric name) is ever asked for selections.
    // Each proxy model path is joined to the selection proxy:<path>.<digits> whose whole normalised path (lower case,
    // forward slashes, no leading slash, no .p3d, prefix and instance suffix removed) equals the model path, per numeric
    // LOD; weaponlight_universal_extra or a generic label/... selection never stands in for weaponlight_universal.
    // Native cache 1.30.164289:
    //   3_Game/Entities/Object.c:98 GetLODS(notnull out array<LOD> lods) returning bool, 3_Game/Entities/Object.c:101
    //   GetLODName(LOD lod) and 3_Game/Entities/Object.c:106-122 GetLODByName (script; diagnostics only here);
    //   3_Game/gameplay.c:179 class Selection with gameplay.c:184 GetName(), gameplay.c:185 GetVertexCount(),
    //   gameplay.c:186 GetLODVertexIndex(int) and gameplay.c:188 GetVertexPosition(LOD lod, int index) (script; it calls
    //   Error() when the LOD vertex index is -1, so a vertex is read only after GetVertexCount() > 0 and
    //   GetLODVertexIndex(0) != -1); gameplay.c:203 class LOD with gameplay.c:207 NAME_VIEW "view", gameplay.c:216
    //   GetSelections(notnull out array<Selection> selections) returning bool and gameplay.c:218 GetVertexPosition(int);
    //   1_Core/proto/EnScript.c:380 array Count, EnScript.c:385 Clear, EnScript.c:394 Find, EnScript.c:399 Get and
    //   EnScript.c:407 Insert; 1_Core/proto/EnString.c:240 IndexOf and EnString.c:271 IndexOfFrom (digit and mark tests).
    // Bounds: Object.GetLODS above 128 LODs is reported as not listed (nothing is scanned); at most 16 numeric LODs are
    // scanned (res_lod_count says how many exist) and at most 512 selections of each are kept (selection_count says how
    // many it listed; scan_complete is false above 512). LOD.GetSelections returns bool and does not promise anything about
    // its out array on failure, so the array is cleared before every call and again after a failure, list_ok is emitted per
    // LOD, and false is "unknown", never an empty-but-valid list. The scan runs once per host; each proxy row only looks up
    // its own model path in the kept selection paths. A vertex is emitted as number text.
    // This is source-level evidence of a model proxy slot on the server-side model only: it does not show that a client
    // renders the attachment, the beam, the switch, removal by hand, tape consumption or persistence.
    string HCTLViewKey(string value)
    {
        string text = value;
        text.Replace(m_HCTLSlash, "/");
        text.ToLower();
        return text;
    }

    string HCTLViewTrim(string value)
    {
        string text = HCTLViewKey(value);
        int textLength = text.Length();
        if (textLength > 4 && text.Substring(textLength - 4, 4) == ".p3d")
            text = text.Substring(0, textLength - 4);
        while (text.Length() > 0 && text.Substring(0, 1) == "/")
            text = text.Substring(1, text.Length() - 1);
        return text;
    }

    string HCTLViewPath(string viewKey)
    {
        if (viewKey.IndexOf("proxy:") != 0)
            return "";
        string stem = viewKey.Substring(6, viewKey.Length() - 6);
        int lastDot = HCTLLastPos(stem, ".");
        if (lastDot < 1 || lastDot == stem.Length() - 1)
            return "";
        string digitSet = "0123456789";
        string instanceText = stem.Substring(lastDot + 1, stem.Length() - lastDot - 1);
        int digitIndex = 0;
        while (digitIndex < instanceText.Length())
        {
            if (digitSet.IndexOf(instanceText.Substring(digitIndex, 1)) == -1)
                return "";
            digitIndex = digitIndex + 1;
        }
        return HCTLViewTrim(stem.Substring(0, lastDot));
    }

    // A resolution LOD name is a whole non-negative number: digits with at most one inner dot ("0", "1", "1.000"). Anything
    // else (geometry, memory, view, VIEW_PILOT, landContact, geometryView, geometryFire, "", "-1", "1e3", "1.") is not.
    bool HCTLIsNumericName(string lodName)
    {
        int nameLength = lodName.Length();
        if (nameLength == 0)
            return false;
        string digitSet = "0123456789";
        if (digitSet.IndexOf(lodName.Substring(0, 1)) == -1)
            return false;
        if (digitSet.IndexOf(lodName.Substring(nameLength - 1, 1)) == -1)
            return false;
        int dotCount = 0;
        int charIndex = 0;
        string oneChar = "";
        while (charIndex < nameLength)
        {
            oneChar = lodName.Substring(charIndex, 1);
            charIndex = charIndex + 1;
            if (oneChar == ".")
                dotCount = dotCount + 1;
            if (oneChar != "." && digitSet.IndexOf(oneChar) == -1)
                return false;
        }
        if (dotCount > 1)
            return false;
        return true;
    }

    // The per-host resolution scan. It fills, per scanned numeric LOD, resNames (its name) and six consecutive ints in
    // resFacts (selection list ok 0/1, selections listed, start offset into resKeys/resPaths/resVerts, selections kept,
    // instance ok 0/1, native GetSelectionCount or -1), and returns the number of numeric LODs found (more than are scanned
    // when above 16), or -1 when GetLODS failed or listed more than 128 LODs. Round 8 (probe-006): the script instance of a
    // LOD can be null while GetLODName still answers, so only the selection calls sit behind the instance guard, and the
    // first vertex of every kept proxy selection is read here, in the scope that listed the selections (no LOD or
    // Selection reference is kept after the scan). resKeys holds the normalised selection name, resPaths the proxy model
    // path ("" for a non-proxy selection) and resVerts the vertex text ("" when the selection has no readable vertex).
    int HCTLResolutionScan(Object subject, array<string> resNames, array<int> resFacts, array<string> resKeys, array<string> resPaths, array<string> resVerts)
    {
        array<LOD> lodList = new array<LOD>;
        array<Selection> lodSelections = new array<Selection>;
        lodList.Clear();
        bool lodListed = subject.GetLODS(lodList);
        if (lodListed == false)
            return -1;
        int lodTotal = lodList.Count();
        if (lodTotal > 128)
            return -1;
        int numericCount = 0;
        int lodIndex = 0;
        string lodName = "";
        LOD scanLod = null;
        bool selectionsListed = false;
        int listedFlag = 0;
        int instanceFlag = 0;
        int nativeCount = -1;
        int selectionTotal = 0;
        int selectionKept = 0;
        int selectionIndex = 0;
        Selection scanSelection = null;
        string scanKey = "";
        string scanPath = "";
        string vertexText = "";
        vector vertexPos = "0 0 0";
        while (lodIndex < lodTotal)
        {
            scanLod = lodList.Get(lodIndex);
            lodIndex = lodIndex + 1;
            lodName = subject.GetLODName(scanLod);
            if (HCTLIsNumericName(lodName))
            {
                numericCount = numericCount + 1;
                if (resNames.Count() < 16)
                {
                    lodSelections.Clear();
                    listedFlag = 0;
                    instanceFlag = 0;
                    nativeCount = -1;
                    if (scanLod)
                    {
                        instanceFlag = 1;
                        nativeCount = scanLod.GetSelectionCount();
                        selectionsListed = scanLod.GetSelections(lodSelections);
                        listedFlag = 1;
                        if (selectionsListed == false)
                        {
                            listedFlag = 0;
                            lodSelections.Clear();
                        }
                    }
                    selectionTotal = lodSelections.Count();
                    selectionKept = selectionTotal;
                    if (selectionKept > 512)
                        selectionKept = 512;
                    resNames.Insert(lodName);
                    resFacts.Insert(listedFlag);
                    resFacts.Insert(selectionTotal);
                    resFacts.Insert(resKeys.Count());
                    resFacts.Insert(selectionKept);
                    resFacts.Insert(instanceFlag);
                    resFacts.Insert(nativeCount);
                    selectionIndex = 0;
                    while (selectionIndex < selectionKept)
                    {
                        scanSelection = lodSelections.Get(selectionIndex);
                        selectionIndex = selectionIndex + 1;
                        scanKey = HCTLViewKey(scanSelection.GetName());
                        scanPath = HCTLViewPath(scanKey);
                        vertexText = "";
                        if (scanPath != "" && scanSelection.GetVertexCount() > 0 && scanSelection.GetLODVertexIndex(0) != -1)
                        {
                            vertexPos = scanSelection.GetVertexPosition(scanLod, 0);
                            vertexText = HCTLStr(vertexPos[0].ToString()) + "," + HCTLStr(vertexPos[1].ToString()) + "," + HCTLStr(vertexPos[2].ToString());
                        }
                        resKeys.Insert(scanKey);
                        resPaths.Insert(scanPath);
                        resVerts.Insert(vertexText);
                    }
                    lodSelections.Clear();
                }
            }
        }
        return numericCount;
    }

    // The host facts of the resolution scan: res_enum_ok (GetLODS listed 128 LODs or fewer), res_lod_count (numeric LODs
    // found, 0 when not listed), res_lods_scanned (at most 16), res_scan_complete (every numeric LOD scanned and every
    // selection list ok and within 512) and one res_lods entry per scanned LOD with its instance_ok (the script instance
    // was not null) and native_count (GetSelectionCount, -1 without an instance).
    string HCTLResFacts(int resCount, array<string> resNames, array<int> resFacts)
    {
        bool enumOk = true;
        int countShown = resCount;
        if (resCount < 0)
        {
            enumOk = false;
            countShown = 0;
        }
        bool allComplete = true;
        string lodText = "";
        int lodIndex = 0;
        int factBase = 0;
        int selectionTotal = 0;
        int nativeCount = 0;
        bool lodListed = false;
        bool lodComplete = false;
        bool instanceOk = false;
        while (lodIndex < resNames.Count())
        {
            factBase = lodIndex * 6;
            selectionTotal = resFacts.Get(factBase + 1);
            nativeCount = resFacts.Get(factBase + 5);
            lodListed = false;
            if (resFacts.Get(factBase) == 1)
                lodListed = true;
            instanceOk = false;
            if (resFacts.Get(factBase + 4) == 1)
                instanceOk = true;
            lodComplete = false;
            if (lodListed && selectionTotal <= 512)
                lodComplete = true;
            if (lodComplete == false)
                allComplete = false;
            if (lodIndex > 0)
                lodText = lodText + ",";
            lodText = lodText + "{" + HCTLKey("name") + HCTLStr(resNames.Get(lodIndex)) + "," + HCTLKey("list_ok") + HCTLBool(lodListed) + ",";
            lodText = lodText + HCTLKey("selection_count") + selectionTotal.ToString() + "," + HCTLKey("scan_complete") + HCTLBool(lodComplete) + ",";
            lodText = lodText + HCTLKey("instance_ok") + HCTLBool(instanceOk) + "," + HCTLKey("native_count") + nativeCount.ToString() + "}";
            lodIndex = lodIndex + 1;
        }
        bool scanComplete = false;
        if (enumOk && allComplete && resNames.Count() == countShown)
            scanComplete = true;
        string factText = HCTLKey("res_enum_ok") + HCTLBool(enumOk) + "," + HCTLKey("res_lod_count") + countShown.ToString() + ",";
        int scannedCount = resNames.Count();
        factText = factText + HCTLKey("res_lods_scanned") + scannedCount.ToString() + "," + HCTLKey("res_scan_complete") + HCTLBool(scanComplete) + ",";
        return factText + HCTLKey("res_lods") + "[" + lodText + "],";
    }

    // One proxy row's per-LOD evidence: for each scanned numeric LOD the first kept selection whose normalised whole path
    // equals the row's model path (name, list_ok, the matching selection or "", and its first vertex text when it had one
    // when the scan read it). Only strings are used: the vertex was read by the scan.
    string HCTLResRow(string modelPath, array<string> resNames, array<int> resFacts, array<string> resKeys, array<string> resPaths, array<string> resVerts)
    {
        string needle = "";
        if (modelPath.Length() > 5)
            needle = HCTLViewTrim(modelPath);
        string rowText = "";
        string matchName = "";
        string vertexText = "";
        bool vertexOk = false;
        bool lodListed = false;
        int lodIndex = 0;
        int pathIndex = 0;
        int pathEnd = 0;
        while (lodIndex < resNames.Count())
        {
            matchName = "";
            vertexText = "";
            vertexOk = false;
            lodListed = false;
            if (resFacts.Get(lodIndex * 6) == 1)
                lodListed = true;
            pathIndex = resFacts.Get(lodIndex * 6 + 2);
            pathEnd = pathIndex + resFacts.Get(lodIndex * 6 + 3);
            while (needle != "" && pathIndex < pathEnd)
            {
                if (resPaths.Get(pathIndex) == needle)
                {
                    matchName = resKeys.Get(pathIndex);
                    vertexText = resVerts.Get(pathIndex);
                    break;
                }
                pathIndex = pathIndex + 1;
            }
            if (vertexText != "")
                vertexOk = true;
            if (lodIndex > 0)
                rowText = rowText + ",";
            rowText = rowText + "{" + HCTLKey("name") + HCTLStr(resNames.Get(lodIndex)) + "," + HCTLKey("list_ok") + HCTLBool(lodListed) + ",";
            rowText = rowText + HCTLKey("selection") + HCTLStr(matchName) + "," + HCTLKey("vertex_ok") + HCTLBool(vertexOk) + ",";
            rowText = rowText + HCTLKey("vertex") + "[" + vertexText + "]}";
            lodIndex = lodIndex + 1;
        }
        return HCTLKey("res_lods") + "[" + rowText + "]";
    }

    string HCTLProxyRow(string selectionName, array<string> resNames, array<int> resFacts, array<string> resKeys, array<string> resPaths, array<string> resVerts)
    {
        string cfgBase = HCTLProxyBase(selectionName);
        string cfgClass = "Proxy" + cfgBase;
        string cfgPath = "CfgNonAIVehicles " + cfgClass;
        bool cfgExists = GetGame().ConfigIsExisting(cfgPath);
        bool baseExists = GetGame().ConfigIsExisting("CfgNonAIVehicles " + cfgBase);
        int slashCount = HCTLCountChar(selectionName, "/");
        int backslashCount = HCTLCountChar(selectionName, m_HCTLSlash);
        string modelPath = "";
        string slotText = "";
        TStringArray slotNames = new TStringArray;
        if (cfgExists)
        {
            GetGame().ConfigGetText(cfgPath + " model", modelPath);
            GetGame().ConfigGetTextArray(cfgPath + " inventorySlot", slotNames);
            if (slotNames.Count() == 0)
            {
                GetGame().ConfigGetText(cfgPath + " inventorySlot", slotText);
                if (slotText != "")
                    slotNames.Insert(slotText);
            }
        }
        int slotTotal = slotNames.Count();
        bool slotComplete = true;
        if (slotTotal > 8)
            slotComplete = false;
        string slotList = "";
        int slotIndex = 0;
        while (slotIndex < slotTotal && slotIndex < 8)
        {
            if (slotIndex > 0)
                slotList = slotList + ",";
            slotList = slotList + HCTLStr(slotNames.Get(slotIndex));
            slotIndex = slotIndex + 1;
        }
        string rowText = "{" + HCTLKey("selection") + HCTLStr(selectionName) + "," + HCTLKey("cfg_class") + HCTLStr(cfgClass) + ",";
        rowText = rowText + HCTLKey("cfg_exists") + HCTLBool(cfgExists) + "," + HCTLKey("model") + HCTLStr(modelPath) + ",";
        rowText = rowText + HCTLKey("cfg_tried") + "[" + HCTLStr(cfgClass) + "," + HCTLStr(cfgBase) + "],";
        rowText = rowText + HCTLKey("cfg_tried_exists") + "[" + HCTLBool(cfgExists) + "," + HCTLBool(baseExists) + "],";
        rowText = rowText + HCTLKey("sep_slash") + slashCount.ToString() + "," + HCTLKey("sep_backslash") + backslashCount.ToString() + ",";
        rowText = rowText + HCTLKey("inventory_slots") + "[" + slotList + "]," + HCTLKey("slot_count") + slotTotal.ToString() + ",";
        rowText = rowText + HCTLKey("slot_scan_complete") + HCTLBool(slotComplete) + ",";
        return rowText + HCTLResRow(modelPath, resNames, resFacts, resKeys, resPaths, resVerts) + "}";
    }

    // LOD diagnostics (fix round 6, kept as diagnostics only since round 7). Object.c:106-122 GetLODByName is script: it
    // walks GetLODS (Object.c:98, bool, out array<LOD>) and compares GetLODName (Object.c:101) lower-cased. Every name is
    // reported (at most eight, with the count); a list the engine refused (or one above 128 LODs, which is not scanned) is
    // reported as not listed, never as an empty list. view_by_name is the result of GetLODByName(LOD.NAME_VIEW) and is
    // never evidence: the report does not use a view LOD.
    string HCTLLodFacts(Object subject, bool viewByName)
    {
        array<LOD> lodList = new array<LOD>;
        lodList.Clear();
        bool lodListed = subject.GetLODS(lodList);
        if (lodListed == false)
            lodList.Clear();
        int lodTotal = lodList.Count();
        if (lodTotal > 128)
        {
            lodListed = false;
            lodTotal = 0;
        }
        string nameList = "";
        int nameCount = 0;
        string lodName = "";
        while (nameCount < lodTotal && nameCount < 8)
        {
            lodName = subject.GetLODName(lodList.Get(nameCount));
            if (nameCount > 0)
                nameList = nameList + ",";
            nameList = nameList + HCTLStr(lodName);
            nameCount = nameCount + 1;
        }
        bool namesComplete = false;
        if (nameCount == lodTotal)
            namesComplete = true;
        string lodText = HCTLKey("lod_list_ok") + HCTLBool(lodListed) + "," + HCTLKey("lod_count") + lodTotal.ToString() + ",";
        lodText = lodText + HCTLKey("lod_names") + "[" + nameList + "]," + HCTLKey("lod_names_complete") + HCTLBool(namesComplete) + ",";
        lodText = lodText + HCTLLodCounts(subject, lodList, lodTotal);
        return lodText + HCTLKey("view_by_name") + HCTLBool(viewByName) + ",";
    }

    // Round 8 (probe-006): the native selection count of EVERY listed LOD (memory, geometry, geometryView, geometryFire
    // and the rest included, at most 16), read only through LOD.GetSelectionCount (gameplay.c:215, proto native int), never
    // through GetSelections. A LOD whose script instance is null is reported as instance_ok false and count -1; the
    // instance guard wraps the count call only, not GetLODName. lod_counts_total is the number of LODs listed and
    // lod_counts_complete says every one of them has an entry. A diagnostic: it never decides a verdict.
    string HCTLLodCounts(Object subject, array<LOD> lodList, int lodTotal)
    {
        string countText = "";
        int countIndex = 0;
        int countValue = 0;
        bool instanceOk = false;
        LOD countLod = null;
        while (countIndex < lodTotal && countIndex < 16)
        {
            countLod = lodList.Get(countIndex);
            countValue = -1;
            instanceOk = false;
            if (countLod)
            {
                instanceOk = true;
                countValue = countLod.GetSelectionCount();
            }
            if (countIndex > 0)
                countText = countText + ",";
            countText = countText + "{" + HCTLKey("name") + HCTLStr(subject.GetLODName(countLod)) + "," + HCTLKey("count") + countValue.ToString() + ",";
            countText = countText + HCTLKey("instance_ok") + HCTLBool(instanceOk) + "}";
            countIndex = countIndex + 1;
        }
        bool countsComplete = false;
        if (countIndex == lodTotal)
            countsComplete = true;
        string factText = HCTLKey("lod_counts") + "[" + countText + "]," + HCTLKey("lod_counts_total") + lodTotal.ToString() + ",";
        return factText + HCTLKey("lod_counts_complete") + HCTLBool(countsComplete) + ",";
    }

    string HCTLProxyFacts(Object subject)
    {
        TStringArray selectionNames = new TStringArray;
        subject.GetSelectionList(selectionNames);
        int total = selectionNames.Count();
        int scanLimit = total;
        if (scanLimit > 512)
            scanLimit = 512;
        bool scanComplete = true;
        if (scanLimit < total)
            scanComplete = false;
        array<string> resNames = new array<string>;
        array<int> resFacts = new array<int>;
        array<string> resKeys = new array<string>;
        array<string> resPaths = new array<string>;
        array<string> resVerts = new array<string>;
        int resCount = HCTLResolutionScan(subject, resNames, resFacts, resKeys, resPaths, resVerts);
        LOD byNameLod = subject.GetLODByName(LOD.NAME_VIEW);
        bool viewByName = false;
        if (byNameLod)
            viewByName = true;
        TStringArray seen = new TStringArray;
        string rows = "";
        string selectionName = "";
        string lowered = "";
        int scan = 0;
        while (scan < scanLimit)
        {
            selectionName = selectionNames.Get(scan);
            scan = scan + 1;
            lowered = selectionName;
            lowered.ToLower();
            if (lowered.IndexOf("proxy:") == 0 && seen.Find(selectionName) == -1)
            {
                if (seen.Count() < 24)
                {
                    if (seen.Count() > 0)
                        rows = rows + ",";
                    rows = rows + HCTLProxyRow(selectionName, resNames, resFacts, resKeys, resPaths, resVerts);
                }
                seen.Insert(selectionName);
            }
        }
        int proxyTotal = seen.Count();
        string facts = HCTLKey("proxy_count") + proxyTotal.ToString() + "," + HCTLKey("proxy_scan_complete") + HCTLBool(scanComplete) + ",";
        facts = facts + HCTLResFacts(resCount, resNames, resFacts);
        facts = facts + HCTLLodFacts(subject, viewByName);
        return facts + HCTLKey("proxies") + "[" + rows + "]";
    }

    string HCTLAttachSlotNames(EntityAI subject, int limit)
    {
        GameInventory subjectInventory = subject.GetInventory();
        string names = "";
        if (!subjectInventory)
            return "[]";
        int total = subjectInventory.GetAttachmentSlotsCount();
        int listed = 0;
        int index = 0;
        while (index < total && listed < limit)
        {
            if (listed > 0)
                names = names + ",";
            names = names + HCTLStr(InventorySlots.GetSlotName(subjectInventory.GetAttachmentSlotId(index)));
            listed = listed + 1;
            index = index + 1;
        }
        return "[" + names + "]";
    }

    string HCTLOwnSlotNames(EntityAI subject, int limit)
    {
        GameInventory subjectInventory = subject.GetInventory();
        string names = "";
        if (!subjectInventory)
            return "[]";
        int total = subjectInventory.GetSlotIdCount();
        int listed = 0;
        int index = 0;
        while (index < total && listed < limit)
        {
            if (listed > 0)
                names = names + ",";
            names = names + HCTLStr(InventorySlots.GetSlotName(subjectInventory.GetSlotId(index)));
            listed = listed + 1;
            index = index + 1;
        }
        return "[" + names + "]";
    }

    string HCTLBeamFacts(Object subject)
    {
        bool startExists = subject.MemoryPointExists("beamStart");
        bool endExists = subject.MemoryPointExists("beamEnd");
        vector startPos = "0 0 0";
        vector endPos = "0 0 0";
        if (startExists)
            startPos = subject.GetMemoryPointPos("beamStart");
        if (endExists)
            endPos = subject.GetMemoryPointPos("beamEnd");
        string beamText = HCTLKey("beam_start") + HCTLBool(startExists) + "," + HCTLKey("beam_start_pos") + HCTLVector(startPos) + ",";
        beamText = beamText + HCTLKey("beam_end") + HCTLBool(endExists) + "," + HCTLKey("beam_end_pos") + HCTLVector(endPos);
        return beamText;
    }

    void HCTLObserveLights()
    {
        int lightIndex = 0;
        string lightName = "";
        EntityAI lightItem = null;
        string row = "";
        int slotIndex = 0;
        string fits = "";
        int slotId = 0;
        while (lightIndex < m_HCTLLights.Count())
        {
            lightName = m_HCTLLights.Get(lightIndex);
            lightIndex = lightIndex + 1;
            lightItem = EntityAI.Cast(HCTLSpawn(lightName));
            row = "{" + HCTLKey("light") + HCTLStr(lightName) + ",";
            if (!lightItem)
            {
                m_HCTLLightRows.Insert(row + HCTLKey("spawned") + "false}");
                continue;
            }
            fits = "";
            slotIndex = 0;
            while (slotIndex < m_HCTLSlots.Count())
            {
                slotId = InventorySlots.GetSlotIdFromString(m_HCTLSlots.Get(slotIndex));
                if (slotIndex > 0)
                    fits = fits + ",";
                fits = fits + "{" + HCTLKey("slot") + HCTLStr(m_HCTLSlots.Get(slotIndex)) + "," + HCTLKey("fits") + HCTLBool(lightItem.GetInventory().HasInventorySlot(slotId)) + "}";
                slotIndex = slotIndex + 1;
            }
            row = row + HCTLKey("spawned") + "true," + HCTLKey("type") + HCTLStr(lightItem.GetType()) + ",";
            row = row + HCTLKey("own_slots") + HCTLOwnSlotNames(lightItem, 16) + "," + HCTLKey("fits_native_slots") + "[" + fits + "],";
            row = row + HCTLKey("attach_slots") + HCTLAttachSlotNames(lightItem, 8) + "," + HCTLBeamFacts(lightItem) + "," + HCTLSelectionFacts(lightItem) + "}";
            m_HCTLLightRows.Insert(row);
            HCTLReleaseAll();
        }
    }

    // Round 8 (probe-006): InventorySlots.GetSelectionForSlotId and GetBoneNameForSlotId answer "" for every light slot, so
    // the only host-side name a light slot can have is the proxy selection the model lists (Object.c:382 GetSelectionList)
    // whose CfgNonAIVehicles Proxy<base> entry names that slot in its inventorySlot. For every probed slot this reads
    // Entity.GetBoneIndex (Entity.c:35, proto native int) with each spelling of each such proxy name (as listed, without the
    // proxy: prefix, lower case, and both): at most four distinct proxy names, so at most sixteen queries per slot. The best
    // index, the spelling that gave it (the first spelling tried when none did) and the number of queries go into
    // m_HCTLBoneIndex/m_HCTLBoneNames/m_HCTLBoneTried, one entry per probed slot. A diagnostic and optional stronger
    // evidence only: a negative index is never read as a negative finding.
    bool HCTLProxyHoldsSlot(string proxyName, string slotName)
    {
        string cfgPath = "CfgNonAIVehicles Proxy" + HCTLProxyBase(proxyName);
        if (!GetGame().ConfigIsExisting(cfgPath))
            return false;
        TStringArray holdSlots = new TStringArray;
        string holdText = "";
        GetGame().ConfigGetTextArray(cfgPath + " inventorySlot", holdSlots);
        if (holdSlots.Count() == 0)
        {
            GetGame().ConfigGetText(cfgPath + " inventorySlot", holdText);
            if (holdText != "")
                holdSlots.Insert(holdText);
        }
        return holdSlots.Find(slotName) != -1;
    }

    string HCTLBoneSpelling(string proxyName, int spelling)
    {
        string spelled = proxyName;
        if (spelling == 1 || spelling == 3)
            spelled = proxyName.Substring(6, proxyName.Length() - 6);
        if (spelling == 2 || spelling == 3)
            spelled.ToLower();
        return spelled;
    }

    void HCTLSlotBones(EntityAI hostItem)
    {
        m_HCTLBoneIndex.Clear();
        m_HCTLBoneNames.Clear();
        m_HCTLBoneTried.Clear();
        TStringArray listedNames = new TStringArray;
        TStringArray triedProxies = new TStringArray;
        hostItem.GetSelectionList(listedNames);
        int listedTotal = listedNames.Count();
        if (listedTotal > 512)
            listedTotal = 512;
        int slotIndex = 0;
        int nameIndex = 0;
        int spelling = 0;
        int bestIndex = -1;
        int triedCount = 0;
        int spelledIndex = 0;
        string bestName = "";
        string listedName = "";
        string loweredName = "";
        string spelled = "";
        while (slotIndex < m_HCTLSlots.Count())
        {
            triedProxies.Clear();
            nameIndex = 0;
            bestIndex = -1;
            bestName = "";
            triedCount = 0;
            while (nameIndex < listedTotal && triedProxies.Count() < 4)
            {
                listedName = listedNames.Get(nameIndex);
                nameIndex = nameIndex + 1;
                loweredName = listedName;
                loweredName.ToLower();
                if (loweredName.IndexOf("proxy:") == 0 && triedProxies.Find(listedName) == -1 && HCTLProxyHoldsSlot(listedName, m_HCTLSlots.Get(slotIndex)))
                {
                    triedProxies.Insert(listedName);
                    spelling = 0;
                    while (spelling < 4)
                    {
                        spelled = HCTLBoneSpelling(listedName, spelling);
                        spelledIndex = hostItem.GetBoneIndex(spelled);
                        triedCount = triedCount + 1;
                        if (bestName == "")
                            bestName = spelled;
                        if (spelledIndex > bestIndex)
                        {
                            bestIndex = spelledIndex;
                            bestName = spelled;
                        }
                        spelling = spelling + 1;
                    }
                }
            }
            m_HCTLBoneIndex.Insert(bestIndex);
            m_HCTLBoneNames.Insert(bestName);
            m_HCTLBoneTried.Insert(triedCount);
            slotIndex = slotIndex + 1;
        }
    }

    string HCTLHostSlots(EntityAI hostItem)
    {
        GameInventory hostInventory = hostItem.GetInventory();
        string result = "";
        int slotIndex = 0;
        string slotName = "";
        int slotId = 0;
        bool slotValid = false;
        bool hostHasSlot = false;
        string selection = "";
        bool selectionKnown = false;
        bool onModel = false;
        bool memoryPoint = false;
        int boneIndex = -1;
        Object boneObject = null;
        string boneType = "";
        int proxyBone = -1;
        int proxyTried = 0;
        HCTLSlotBones(hostItem);
        while (slotIndex < m_HCTLSlots.Count())
        {
            slotName = m_HCTLSlots.Get(slotIndex);
            slotId = InventorySlots.GetSlotIdFromString(slotName);
            slotValid = InventorySlots.IsSlotIdValid(slotId);
            hostHasSlot = false;
            selection = "";
            selectionKnown = false;
            onModel = false;
            memoryPoint = false;
            boneIndex = -1;
            boneObject = null;
            boneType = "";
            if (slotValid && hostInventory)
            {
                hostHasSlot = hostInventory.HasAttachmentSlot(slotId);
                selectionKnown = InventorySlots.GetSelectionForSlotId(slotId, selection);
            }
            if (selectionKnown && selection != "")
            {
                onModel = hostItem.HasSelection(selection);
                memoryPoint = hostItem.MemoryPointExists(selection);
                boneIndex = hostItem.GetBoneIndex(selection);
                if (boneIndex >= 0)
                {
                    boneObject = hostItem.GetBoneObject(boneIndex);
                    if (boneObject)
                        boneType = boneObject.GetType();
                }
            }
            if (slotIndex > 0)
                result = result + ",";
            result = result + "{" + HCTLKey("slot") + HCTLStr(slotName) + "," + HCTLKey("host_has_slot") + HCTLBool(hostHasSlot) + ",";
            result = result + HCTLKey("selection") + HCTLStr(selection) + ",";
            result = result + HCTLKey("selection_on_model") + HCTLBool(onModel) + "," + HCTLKey("memory_point") + HCTLBool(memoryPoint) + ",";
            result = result + HCTLKey("bone_index") + boneIndex.ToString() + "," + HCTLKey("bone_object") + HCTLStr(boneType) + ",";
            proxyBone = m_HCTLBoneIndex.Get(slotIndex);
            proxyTried = m_HCTLBoneTried.Get(slotIndex);
            result = result + HCTLKey("proxy_bone_index") + proxyBone.ToString() + "," + HCTLKey("proxy_bone_name") + HCTLStr(m_HCTLBoneNames.Get(slotIndex)) + ",";
            result = result + HCTLKey("proxy_bone_tried") + proxyTried.ToString() + "}";
            slotIndex = slotIndex + 1;
        }
        return result;
    }

    string HCTLObserveLight(EntityAI hostItem, string lightName)
    {
        GameInventory hostInventory = hostItem.GetInventory();
        EntityAI lightItem = EntityAI.Cast(HCTLSpawn(lightName));
        string result = "{" + HCTLKey("light") + HCTLStr(lightName) + ",";
        if (!lightItem || !hostInventory)
            return result + HCTLKey("spawned") + "false}";
        bool canAddAny = hostInventory.CanAddAttachment(lightItem);
        result = result + HCTLKey("spawned") + "true," + HCTLKey("can_add_any") + HCTLBool(canAddAny) + "," + HCTLKey("per_slot") + "[";
        int slotIndex = 0;
        int slotId = 0;
        bool slotValid = false;
        bool canAddSlot = false;
        bool attachOk = false;
        bool boneChecked = false;
        bool boneMatches = false;
        int boneIndex = -1;
        Object boneObject = null;
        string boneType = "";
        EntityAI attached = null;
        EntityAI found = null;
        string foundType = "";
        string beamFacts = "";
        while (slotIndex < m_HCTLSlots.Count())
        {
            slotId = InventorySlots.GetSlotIdFromString(m_HCTLSlots.Get(slotIndex));
            slotValid = InventorySlots.IsSlotIdValid(slotId);
            canAddSlot = false;
            attachOk = false;
            boneChecked = false;
            boneMatches = false;
            boneIndex = -1;
            boneObject = null;
            boneType = "";
            attached = null;
            found = null;
            foundType = "";
            beamFacts = "";
            if (slotValid)
                canAddSlot = hostInventory.CanAddAttachmentEx(lightItem, slotId);
            if (canAddSlot)
            {
                attached = hostInventory.CreateAttachmentEx(lightName, slotId);
                if (attached)
                {
                    m_HCTLLive.Insert(attached);
                    m_HCTLSpawned = m_HCTLSpawned + 1;
                    m_HCTLAttachOk = m_HCTLAttachOk + 1;
                    attachOk = true;
                    found = hostInventory.FindAttachment(slotId);
                    if (found)
                        foundType = found.GetType();
                    beamFacts = HCTLBeamFacts(attached);
                    // Round 8: after the attach, the proxy bone the host reported for this slot (HCTLSlotBones) is asked
                    // for its object, and that object is compared with the attached light by reference.
                    boneIndex = m_HCTLBoneIndex.Get(slotIndex);
                    if (boneIndex >= 0)
                    {
                        boneObject = hostItem.GetBoneObject(boneIndex);
                        boneChecked = true;
                    }
                    if (boneObject)
                    {
                        boneType = boneObject.GetType();
                        if (boneObject == attached)
                            boneMatches = true;
                    }
                }
            }
            if (slotIndex > 0)
                result = result + ",";
            result = result + "{" + HCTLKey("slot") + HCTLStr(m_HCTLSlots.Get(slotIndex)) + "," + HCTLKey("light_fits") + HCTLBool(lightItem.GetInventory().HasInventorySlot(slotId)) + ",";
            result = result + HCTLKey("can_add") + HCTLBool(canAddSlot) + "," + HCTLKey("attach_ok") + HCTLBool(attachOk) + ",";
            result = result + HCTLKey("found_type") + HCTLStr(foundType) + "," + HCTLKey("proxy_after_attach") + HCTLStr(boneType) + ",";
            result = result + HCTLKey("bone_object_checked") + HCTLBool(boneChecked) + "," + HCTLKey("bone_object_matches") + HCTLBool(boneMatches);
            if (beamFacts != "")
                result = result + "," + beamFacts;
            result = result + "}";
            slotIndex = slotIndex + 1;
        }
        return result + "]}";
    }

    // Round 8: one firearm control, the first slot host, spawned WITHOUT ECE_IN_INVENTORY (the other spawns all carry it) and
    // released at once. Its model selection list is counted so a reader can see whether the flag changes what the model
    // reports. It is observation only and never a verdict input.
    string HCTLObserveControl()
    {
        string controlClass = "";
        int controlIndex = 0;
        while (controlIndex < m_HCTLClasses.Count() && controlClass == "")
        {
            if (m_HCTLGroups.Get(controlIndex) == 1)
                controlClass = m_HCTLClasses.Get(controlIndex);
            controlIndex = controlIndex + 1;
        }
        int controlFlags = ECE_NOPERSISTENCY_WORLD | ECE_NOLIFETIME;
        string controlText = "{" + HCTLKey("class") + HCTLStr(controlClass) + "," + HCTLKey("spawn_flags") + HCTLStr("NOPERSISTENCY_WORLD|NOLIFETIME") + ",";
        if (controlClass == "")
            return controlText + HCTLKey("spawned") + "false}";
        Object controlItem = HCTLSpawnFlags(controlClass, controlFlags);
        if (!controlItem)
            return controlText + HCTLKey("spawned") + "false}";
        TStringArray controlNames = new TStringArray;
        controlItem.GetSelectionList(controlNames);
        int controlTotal = controlNames.Count();
        int controlScan = controlTotal;
        if (controlScan > 512)
            controlScan = 512;
        int proxyTotal = 0;
        int nameIndex = 0;
        string loweredName = "";
        while (nameIndex < controlScan)
        {
            loweredName = controlNames.Get(nameIndex);
            loweredName.ToLower();
            if (loweredName.IndexOf("proxy:") == 0)
                proxyTotal = proxyTotal + 1;
            nameIndex = nameIndex + 1;
        }
        bool listOk = false;
        if (controlTotal > 0)
            listOk = true;
        controlText = controlText + HCTLKey("spawned") + "true," + HCTLKey("proxy_count") + proxyTotal.ToString() + ",";
        controlText = controlText + HCTLKey("selection_list_ok") + HCTLBool(listOk) + "}";
        HCTLReleaseAll();
        return controlText;
    }

    bool HCTLRail(Object subject)
    {
        // Same test as UniversalLight.CanPutAsAttachment applies to the occupant of a handguard slot.
        if (!subject)
            return false;
        if (!subject.ConfigIsExisting("hasRailFunctionality"))
            return false;
        return subject.ConfigGetBool("hasRailFunctionality");
    }

    string HCTLHostPrereq(EntityAI hostItem)
    {
        GameInventory hostInventory = hostItem.GetInventory();
        string result = "";
        int prereqIndex = 0;
        int slotId = 0;
        bool owns = false;
        string occupantType = "";
        bool railFunctional = false;
        EntityAI occupant = null;
        while (prereqIndex < m_HCTLPrereqSlots.Count())
        {
            slotId = InventorySlots.GetSlotIdFromString(m_HCTLPrereqSlots.Get(prereqIndex));
            owns = false;
            occupantType = "";
            railFunctional = false;
            occupant = null;
            if (hostInventory && InventorySlots.IsSlotIdValid(slotId))
            {
                owns = hostInventory.HasAttachmentSlot(slotId);
                if (owns)
                    occupant = hostInventory.FindAttachment(slotId);
            }
            if (occupant)
            {
                occupantType = occupant.GetType();
                railFunctional = HCTLRail(occupant);
            }
            if (prereqIndex > 0)
                result = result + ",";
            result = result + "{" + HCTLKey("slot") + HCTLStr(m_HCTLPrereqSlots.Get(prereqIndex)) + "," + HCTLKey("host_has_slot") + HCTLBool(owns) + ",";
            result = result + HCTLKey("rail_functional") + HCTLBool(railFunctional) + "," + HCTLKey("attached_type") + HCTLStr(occupantType) + "}";
            prereqIndex = prereqIndex + 1;
        }
        return result;
    }

    int HCTLFirstOpenPrereq(EntityAI hostItem)
    {
        // Index of the first prerequisite slot the host owns, or -1 when it owns none or a rail is already attached.
        GameInventory hostInventory = hostItem.GetInventory();
        int firstOpen = -1;
        int prereqIndex = 0;
        int slotId = 0;
        EntityAI occupant = null;
        if (!hostInventory)
            return -1;
        while (prereqIndex < m_HCTLPrereqSlots.Count())
        {
            slotId = InventorySlots.GetSlotIdFromString(m_HCTLPrereqSlots.Get(prereqIndex));
            if (InventorySlots.IsSlotIdValid(slotId) && hostInventory.HasAttachmentSlot(slotId))
            {
                occupant = hostInventory.FindAttachment(slotId);
                if (HCTLRail(occupant))
                    return -1;
                if (firstOpen < 0)
                    firstOpen = prereqIndex;
            }
            prereqIndex = prereqIndex + 1;
        }
        return firstOpen;
    }

    string HCTLHostLightRows(EntityAI hostItem, array<string> lightNames, int beginMs)
    {
        // The class budget is checked after every observation, the last one included.
        string rows = "";
        int lightIndex = 0;
        while (lightIndex < lightNames.Count())
        {
            if (lightIndex > 0)
                rows = rows + ",";
            rows = rows + HCTLObserveLight(hostItem, lightNames.Get(lightIndex));
            lightIndex = lightIndex + 1;
            if (GetGame().GetTime() - beginMs > m_HCTLPerClassMs)
            {
                m_HCTLClassTimedOut = true;
                break;
            }
        }
        return rows;
    }

    string HCTLPrereqVariant(EntityAI baseItem, string className, int beginMs)
    {
        // A fresh copy of the host with the matching rail handguard created natively in its handguard slot.
        string result = "{" + HCTLKey("performed") + "false}";
        if (m_HCTLPrereqLights.Count() == 0 || m_HCTLClassTimedOut)
            return result;
        int prereqIndex = HCTLFirstOpenPrereq(baseItem);
        if (prereqIndex < 0)
            return result;
        string slotName = m_HCTLPrereqSlots.Get(prereqIndex);
        string handguardName = m_HCTLPrereqTypes.Get(prereqIndex);
        int slotId = InventorySlots.GetSlotIdFromString(slotName);
        EntityAI variantHost = EntityAI.Cast(HCTLSpawn(className));
        EntityAI handguard = null;
        EntityAI readBack = null;
        bool attached = false;
        bool occupied = false;
        bool railFunctional = false;
        string foundType = "";
        string lightRows = "";
        if (variantHost && variantHost.GetInventory())
        {
            handguard = variantHost.GetInventory().CreateAttachmentEx(handguardName, slotId);
            // What the slot really holds afterwards, read back natively; the requested label is not evidence.
            readBack = variantHost.GetInventory().FindAttachment(slotId);
            if (readBack)
            {
                occupied = true;
                foundType = readBack.GetType();
                railFunctional = HCTLRail(readBack);
            }
            if (handguard)
            {
                m_HCTLLive.Insert(handguard);
                m_HCTLSpawned = m_HCTLSpawned + 1;
                attached = true;
                HCTLSlotBones(variantHost);
                lightRows = HCTLHostLightRows(variantHost, m_HCTLPrereqLights, beginMs);
            }
        }
        result = "{" + HCTLKey("performed") + "true," + HCTLKey("slot") + HCTLStr(slotName) + "," + HCTLKey("handguard") + HCTLStr(handguardName) + ",";
        result = result + HCTLKey("handguard_attached") + HCTLBool(attached) + "," + HCTLKey("handguard_found_type") + HCTLStr(foundType) + ",";
        result = result + HCTLKey("handguard_slot_occupied") + HCTLBool(occupied) + "," + HCTLKey("handguard_rail_functional") + HCTLBool(railFunctional) + ",";
        return result + HCTLKey("lights") + "[" + lightRows + "]}";
    }

    string HCTLObserveHost(int index)
    {
        string className = m_HCTLClasses.Get(index);
        string groupName = "no_slot_host";
        if (m_HCTLGroups.Get(index) == 1)
            groupName = "slot_host";
        int beginMs = GetGame().GetTime();
        m_HCTLClassTimedOut = false;
        string row = "{" + HCTLKey("i") + index.ToString() + "," + HCTLKey("class") + HCTLStr(className) + ",";
        row = row + HCTLKey("root") + HCTLStr(m_HCTLRoots.Get(index)) + "," + HCTLKey("group") + HCTLStr(groupName) + ",";
        EntityAI hostItem = EntityAI.Cast(HCTLSpawn(className));
        if (!hostItem)
            return row + HCTLKey("spawned") + "false," + HCTLKey("timed_out") + "false}";
        row = row + HCTLKey("spawned") + "true," + HCTLKey("type") + HCTLStr(hostItem.GetType()) + ",";
        row = row + HCTLKey("own_slots") + HCTLOwnSlotNames(hostItem, 16) + "," + HCTLKey("attach_slots") + HCTLAttachSlotNames(hostItem, 24) + "," + HCTLSelectionFacts(hostItem) + ",";
        row = row + HCTLProxyFacts(hostItem) + ",";
        row = row + HCTLKey("slots") + "[" + HCTLHostSlots(hostItem) + "]," + HCTLKey("prereq") + "[" + HCTLHostPrereq(hostItem) + "],";
        row = row + HCTLKey("lights") + "[" + HCTLHostLightRows(hostItem, m_HCTLLights, beginMs) + "],";
        row = row + HCTLKey("prereq_variant") + HCTLPrereqVariant(hostItem, className, beginMs) + ",";
        int elapsedMs = GetGame().GetTime() - beginMs;
        if (m_HCTLClassTimedOut)
            m_HCTLTimeouts = m_HCTLTimeouts + 1;
        row = row + HCTLKey("timed_out") + HCTLBool(m_HCTLClassTimedOut) + "," + HCTLKey("ms") + elapsedMs.ToString() + "}";
        HCTLReleaseAll();
        return row;
    }

    void HCTLCensusResidual()
    {
        array<Object> nearObjects = new array<Object>;
        array<CargoBase> nearCargos = new array<CargoBase>;
        GetGame().GetObjectsAtPosition3D(m_HCTLPos, 8.0, nearObjects, nearCargos);
        m_HCTLCensusTotal = nearObjects.Count();
        int scanLimit = m_HCTLCensusTotal;
        if (scanLimit > 2048)
            scanLimit = 2048;
        m_HCTLCensusTruncated = m_HCTLCensusTotal > scanLimit;
        int scan = 0;
        Object nearObject = null;
        string nearType = "";
        m_HCTLResidualProbe = 0;
        m_HCTLResidualOther = 0;
        while (scan < scanLimit)
        {
            nearObject = nearObjects.Get(scan);
            scan = scan + 1;
            if (!nearObject)
                continue;
            nearType = nearObject.GetType();
            if (m_HCTLClasses.Find(nearType) != -1)
                m_HCTLResidualProbe = m_HCTLResidualProbe + 1;
            else if (m_HCTLLights.Find(nearType) != -1)
                m_HCTLResidualProbe = m_HCTLResidualProbe + 1;
            else
                m_HCTLResidualOther = m_HCTLResidualOther + 1;
        }
        m_HCTLCensusScanned = scan;
    }

    void HCTLWriteRows(FileHandle handle, string name, array<string> rows, bool last)
    {
        string tail = ",";
        if (last)
            tail = "";
        FPrintln(handle, HCTLKey(name) + "[");
        int rowIndex = 0;
        while (rowIndex < rows.Count())
        {
            if (rowIndex < rows.Count() - 1)
                FPrintln(handle, rows.Get(rowIndex) + ",");
            else
                FPrintln(handle, rows.Get(rowIndex));
            rowIndex = rowIndex + 1;
        }
        FPrintln(handle, "]" + tail);
    }

    // Header diagnostics (fix round 6): measurements, never evidence. The string self-test runs the engine's own IndexOf,
    // LastIndexOf and IndexOfFrom (EnString.c:240, :253, :271) on a fixed sample and on its backslash form, next to the
    // forward-scan helpers the hook actually uses, so a native LastIndexOf that disagrees with them is visible instead of
    // assumed. The scan lists CfgNonAIVehicles children (Game.c:611 ConfigGetChildrenCount, Game.c:594 ConfigGetChildName,
    // constants.c:237 CFG_NONAI_VEHICLES), at most 4096, with the weaponlight ones and their model, so the real proxy
    // class naming is read from the server's own config rather than assumed from convention.
    string HCTLIntField(string name, int value)
    {
        return HCTLKey(name) + value.ToString() + ",";
    }

    string HCTLSelfTest()
    {
        string sampleText = "proxy:/dz/a/b.001";
        string backText = sampleText;
        backText.Replace("/", m_HCTLSlash);
        int firstSlash = sampleText.IndexOf("/");
        int lastSlash = sampleText.LastIndexOf("/");
        int firstDot = sampleText.IndexOf(".");
        int lastDot = sampleText.LastIndexOf(".");
        int fromSeven = sampleText.IndexOfFrom(7, "/");
        int fromTen = sampleText.IndexOfFrom(10, "/");
        int fromTwelve = sampleText.IndexOfFrom(12, "/");
        int fromDot = sampleText.IndexOfFrom(0, ".");
        string testText = "{" + HCTLKey("sample") + HCTLStr(sampleText) + ",";
        testText = testText + HCTLIntField("first_slash", firstSlash) + HCTLIntField("last_slash", lastSlash);
        testText = testText + HCTLIntField("first_dot", firstDot) + HCTLIntField("last_dot", lastDot);
        testText = testText + HCTLIntField("from_slash_7", fromSeven) + HCTLIntField("from_slash_10", fromTen);
        testText = testText + HCTLIntField("from_slash_12", fromTwelve) + HCTLIntField("from_dot_0", fromDot);
        int loopSlash = HCTLLastPos(sampleText, "/");
        int loopDot = HCTLLastPos(sampleText, ".");
        int backLength = backText.Length();
        int backFirst = backText.IndexOf(m_HCTLSlash);
        int backLast = backText.LastIndexOf(m_HCTLSlash);
        int backLoop = HCTLLastPos(backText, m_HCTLSlash);
        int backCount = HCTLCountChar(backText, m_HCTLSlash);
        testText = testText + HCTLIntField("loop_last_slash", loopSlash) + HCTLIntField("loop_last_dot", loopDot);
        testText = testText + HCTLIntField("bs_length", backLength) + HCTLIntField("bs_first", backFirst);
        testText = testText + HCTLIntField("bs_last", backLast) + HCTLIntField("bs_loop_last", backLoop);
        testText = testText + HCTLIntField("bs_count", backCount);
        int codeLength = m_HCTLSlash.Length();
        return testText + HCTLKey("slash_code_length") + codeLength.ToString() + "}";
    }

    string HCTLCfgScan()
    {
        string rootPath = "CfgNonAIVehicles";
        int childTotal = GetGame().ConfigGetChildrenCount(rootPath);
        int scanLimit = childTotal;
        if (scanLimit > 4096)
            scanLimit = 4096;
        string childName = "";
        string loweredName = "";
        string childModel = "";
        string childList = "";
        int childListed = 0;
        int proxyNamed = 0;
        int scanIndex = 0;
        while (scanIndex < scanLimit)
        {
            GetGame().ConfigGetChildName(rootPath, scanIndex, childName);
            scanIndex = scanIndex + 1;
            loweredName = childName;
            loweredName.ToLower();
            if (loweredName.IndexOf("proxy") == 0)
                proxyNamed = proxyNamed + 1;
            if (childListed < 8 && loweredName.IndexOf("weaponlight") != -1)
            {
                childModel = "";
                GetGame().ConfigGetText(rootPath + " " + childName + " model", childModel);
                if (childListed > 0)
                    childList = childList + ",";
                childList = childList + "{" + HCTLKey("name") + HCTLStr(childName) + "," + HCTLKey("model") + HCTLStr(childModel) + "}";
                childListed = childListed + 1;
            }
        }
        bool scanComplete = false;
        if (scanLimit == childTotal)
            scanComplete = true;
        string scanText = "{" + HCTLIntField("child_count", childTotal) + HCTLIntField("scanned", scanLimit);
        scanText = scanText + HCTLKey("complete") + HCTLBool(scanComplete) + "," + HCTLIntField("proxy_named", proxyNamed);
        return scanText + HCTLKey("weaponlight_children") + "[" + childList + "]}";
    }

    void HCTLWriteResult()
    {
        HCTLMeasureLive();
        HCTLCensusResidual();
        string directory = "$profile:HCTapedLightProbe";
        string outputPath = directory + "/observations.json";
        string sentinelPath = directory + "/complete.txt";
        if (!FileExist(directory) && !MakeDirectory(directory))
        {
            Print("[HC Taped Light Probe] FAILED cannot create output directory");
            return;
        }
        if (FileExist(outputPath) || FileExist(sentinelPath))
        {
            Print("[HC Taped Light Probe] FAILED earlier probe output exists; not overwriting");
            return;
        }
        string world;
        string version;
        GetGame().GetWorldName(world);
        GetGame().GetVersion(version);
        FileHandle handle = OpenFile(outputPath, FileMode.WRITE);
        if (!handle)
        {
            Print("[HC Taped Light Probe] FAILED cannot open observations file");
            return;
        }
        FPrintln(handle, "{");
        FPrintln(handle, HCTLKey("schema") + "1," + HCTLKey("kind") + HCTLStr("taped-light-probe-observations") + "," + HCTLKey("status") + HCTLStr(m_HCTLStatus) + ",");
        FPrintln(handle, HCTLKey("world") + HCTLStr(world) + "," + HCTLKey("version") + HCTLStr(version) + ",");
        string outLine = HCTLKey("begin_ms") + m_HCTLBeginMs.ToString() + "," + HCTLKey("end_ms") + m_HCTLEndMs.ToString() + ",";
        outLine = outLine + HCTLKey("hard_cap") + m_HCTLHardCap.ToString() + "," + HCTLKey("per_class_ms") + m_HCTLPerClassMs.ToString() + ",";
        FPrintln(handle, outLine);
        outLine = HCTLKey("classes") + m_HCTLClasses.Count().ToString() + "," + HCTLKey("observed") + m_HCTLRows.Count().ToString() + ",";
        outLine = outLine + HCTLKey("position") + HCTLVector(m_HCTLPos) + ",";
        FPrintln(handle, outLine);
        outLine = HCTLKey("counters") + "{" + HCTLKey("spawned") + m_HCTLSpawned.ToString() + "," + HCTLKey("deleted") + m_HCTLDeleted.ToString() + ",";
        outLine = outLine + HCTLKey("timeouts") + m_HCTLTimeouts.ToString() + "," + HCTLKey("attach_ok") + m_HCTLAttachOk.ToString() + ",";
        outLine = outLine + HCTLKey("live_after_release") + m_HCTLLiveAfterRelease.ToString() + ",";
        outLine = outLine + HCTLKey("residual_probe_types") + m_HCTLResidualProbe.ToString() + "," + HCTLKey("residual_other") + m_HCTLResidualOther.ToString() + ",";
        FPrintln(handle, outLine);
        bool censusComplete = !m_HCTLCensusTruncated && m_HCTLCensusScanned == m_HCTLCensusTotal;
        outLine = HCTLKey("census_total") + m_HCTLCensusTotal.ToString() + "," + HCTLKey("census_scanned") + m_HCTLCensusScanned.ToString() + ",";
        outLine = outLine + HCTLKey("census_truncated") + HCTLBool(m_HCTLCensusTruncated) + "," + HCTLKey("census_complete") + HCTLBool(censusComplete) + "},";
        FPrintln(handle, outLine);
        outLine = HCTLKey("diagnostics") + "{" + HCTLKey("string_self_test") + HCTLSelfTest() + "," + HCTLKey("cfg_nonai_scan") + HCTLCfgScan() + "},";
        FPrintln(handle, outLine);
        string controlRow = m_HCTLControlRow;
        if (controlRow == "")
            controlRow = "{" + HCTLKey("class") + HCTLStr("") + "," + HCTLKey("spawn_flags") + HCTLStr("") + "," + HCTLKey("spawned") + "false}";
        FPrintln(handle, HCTLKey("spawn_control") + controlRow + ",");
        HCTLWriteRows(handle, "slots", m_HCTLSlotRows, false);
        HCTLWriteRows(handle, "lights", m_HCTLLightRows, false);
        HCTLWriteRows(handle, "hosts", m_HCTLRows, true);
        FPrintln(handle, "}");
        CloseFile(handle);
        if (!FileExist(outputPath))
        {
            Print("[HC Taped Light Probe] FAILED observations file missing after write");
            return;
        }
        FileHandle sentinel = OpenFile(sentinelPath, FileMode.WRITE);
        if (!sentinel)
        {
            Print("[HC Taped Light Probe] FAILED cannot open sentinel file");
            return;
        }
        string sentinelText = "status=" + m_HCTLStatus + " observed=" + m_HCTLRows.Count().ToString();
        sentinelText = sentinelText + " spawned=" + m_HCTLSpawned.ToString() + " deleted=" + m_HCTLDeleted.ToString();
        FPrintln(sentinel, sentinelText);
        CloseFile(sentinel);
        string summaryText = "[HC Taped Light Probe] observed=" + m_HCTLRows.Count().ToString() + " spawned=" + m_HCTLSpawned.ToString();
        summaryText = summaryText + " deleted=" + m_HCTLDeleted.ToString() + " residual=" + m_HCTLResidualProbe.ToString();
        Print(summaryText);
        Print("[HC Taped Light Probe] COMPLETE");
    }
}

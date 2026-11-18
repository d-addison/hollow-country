"""W5 #124: install-time types only; no runtime module, tick, native API or PBO edits.

Local installed meta.cpp files identify Navigation=2792984722,
RaG_Core=3556131153 and RaG_Immersive_Vehicles=3105330157. RaG's input is
types/rag_immersive_vehicles.xml. The installed Navigation objects_gear_gps.pbo
config.bin declares public CfgVehicles/ExpansionGPS : Inventory_Base.
Only authored GPS policy ships; vendor XML stays in memory until external mission
installation. optional_overlays owns source hashes, duplicate checks and rollback.
"""
import xml.etree.ElementTree as ET

NAVIGATION_ID = '2792984722'
RAG_CORE_ID = '3556131153'
RAG_VEHICLES_ID = '3105330157'
OVERLAY_PACKS = (('Navigation', NAVIGATION_ID), ('RaGVehicles', RAG_VEHICLES_ID))


def append_types(packs, workshop, loaded, types, source, overlays):
    if 'RaGVehicles' in packs:
        core = overlays.safe(workshop / RAG_CORE_ID)
        if not core.is_dir() or core not in loaded:
            raise ValueError('RaG Immersive Vehicles requires loaded RaG_Core')
        path = overlays.find_file(packs['RaGVehicles'], 'types/rag_immersive_vehicles.xml')
        shipped = overlays.xml(source(path), 'types')
        if not 0 < len(shipped) <= 1024:
            raise ValueError('RaG shipped types missing or over budget')
        for entry in shipped:
            if entry.tag != 'type':
                raise ValueError('invalid RaG shipped type')
            overlays.unique_append(types, entry)
    if 'Navigation' in packs:
        # Own policy: four map-wide, counting stored/carried GPS against CE refill.
        gps = ET.Element('type', {'name': 'ExpansionGPS'})
        for key, value in (('nominal', '4'), ('lifetime', '7200'), ('restock', '1800'),
                           ('min', '1'), ('quantmin', '-1'), ('quantmax', '-1'), ('cost', '100')):
            ET.SubElement(gps, key).text = value
        ET.SubElement(gps, 'flags', dict(count_in_cargo='1', count_in_hoarder='1',
                                       count_in_map='1', count_in_player='1', crafted='0', deloot='0'))
        ET.SubElement(gps, 'category', {'name': 'tools'})
        for usage in ('Military', 'Police'):
            ET.SubElement(gps, 'usage', {'name': usage})
        overlays.unique_append(types, gps)

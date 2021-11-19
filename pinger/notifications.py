import yaml
import json
import datetime

from corptools import models as ctm

from django.utils.html import strip_tags


def filetime_to_dt(ft):
    us = (ft - 116444736000000000) // 10
    return datetime.datetime(1970, 1, 1) + datetime.timedelta(microseconds=us)


def convert_timedelta(duration):
    days, seconds = duration.days, duration.seconds
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = (seconds % 60)
    return hours, minutes, seconds


def format_timedelta(td):
    hours, minutes, seconds = convert_timedelta(td)
    return ("%d Days, %d Hours, %d Min" % (td.days, round(hours), round(minutes)))


def get_available_types():
    classes = NotificationPing.__subclasses__()
    
    output = {}

    for c in classes:
        output[c.__name__] = c
    
    return output


class NotificationPing:
    # Settings
    force_at_ping = False
    category = "None"

    # Data
    _notification = None
    _data = {}
    _ping = ""

    _corp = None
    _alli = None
    _region = None

    def __init__(self, notification):
        self._notification = notification
        self._data = self.parse_notification()
        self.build_ping()

    def parse_notification(self):
        return yaml.load(self._notification.notification_text, Loader=yaml.UnsafeLoader)

    def build_ping(self):
        raise NotImplementedError("Create the Notifcaton Map class to process this ping!")

    def package_ping(self, title, body, timestamp, fields=None, footer=None, img_url=None, colour=16756480):
        custom_data = {'color': colour,
                       'title': title,
                       'description': body,
                       'timestamp': timestamp.replace(tzinfo=None).isoformat(),
                       }

        if fields:
            custom_data['fields'] = fields

        if img_url:
            custom_data['image'] = {'url': img_url}

        if footer:
            custom_data['footer'] = footer

        self._ping = json.dumps(custom_data)

    def get_filters(self):
        return (self._corp, self._alli, self._region)

class AllAnchoringMsg(NotificationPing):
    category = "secure-alert"  # SOV ADMIN ALERTS

    """
        AllAnchoringMsg Example 

        allianceID: 499005583
        corpID: 1542255499
        moonID: 40290328
        solarSystemID: 30004594
        typeID: 27591
        corpsPresent:
        - allianceID: 1900696668
            corpID: 446274610
            towers:
            - moonID: 40290316
            typeID: 20060
        - allianceID: 1900696668
            corpID: 98549506
            towers:
            - moonID: 40290314
            typeID: 20063

    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarSystemID'])

        system_name = system_db.name
        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['typeID'])
        moon_name, _ = ctm.MapSystemMoon.objects.get_or_create_from_esi(self._data['moonID'])

        owner, _ = ctm.EveName.objects.get_or_create_from_esi(self._data['corpID'])

        alliance = "-" if owner.alliance is None else owner.alliance

        title = "Tower Anchoring!"

        body = (f"{structure_type.name}\n**{moon_name.name}**\n\n[{owner.name}]" 
                f"(https://zkillboard.com/search/{owner.name.replace(' ', '%20')}/),"
                f" **[{alliance}](https://zkillboard.com/search/{alliance.replace(' ', '%20')}/)**")
        
        footer = {"icon_url": owner.get_image_url(),
                  "text": f"{owner.name}"}

        fields = []

        for m in self._data['corpsPresent']:
            moons = []
            for moon in m["towers"]:
                _moon_name, _ = ctm.MapSystemMoon.objects.get_or_create_from_esi(moon['moonID'])
                moons.append(_moon_name.name)

            _owner, _ = ctm.EveName.objects.get_or_create_from_esi(m['corpID'])

            fields.append({'name': _owner.name, 'value': "\n".join(moons)})

        self.package_ping(title, 
                          body, 
                          self._notification.timestamp, 
                          fields=fields, 
                          footer=footer)

        self._alli = None if owner.alliance is None else owner.alliance.name
        self._region = system_db.constellation.region.name

class MoonminingExtractionFinished(NotificationPing):
    category = "moons-completed"  # Moon pings

    """
        MoonminingExtractionFinished Example 

        autoTime: 132052212600000000
        moonID: 40291390
        oreVolumeByType:
            45490: 1588072.4935986102
            46677: 2029652.6969759
            46679: 3063178.818627033
            46682: 2839990.2933705184
        solarSystemID: 30004612
        structureID: 1029754067191
        structureLink: <a href="showinfo:35835//1029754067191">NY6-FH - ISF Three</a>
        structureName: NY6-FH - ISF Three
        structureTypeID: 35835

    """
    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarSystemID'])

        system_name = system_db.name
        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        structure_name = self._data['structureName']
        if len(structure_name)<1:
            structure_name = "Unknown"

        moon, _ = ctm.MapSystemMoon.objects.get_or_create_from_esi(self._data['moonID'])

        title = "Moon Extraction Complete!"
        body = "Ready to Fracture!"

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker

        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        auto_time = filetime_to_dt(self._data['autoTime'])
        ores = {}       
        totalm3 = 0
        for t,q in self._data['oreVolumeByType'].items():
            ore, _ = ctm.EveItemType.objects.get_or_create_from_esi(t)
            ores[t] = ore.name
            totalm3 += q
        ore_string = []
        for t,q in self._data['oreVolumeByType'].items():
            ore_string.append(
                "**{}**: {:2.1f}%".format(
                    ores[t],
                    q/totalm3*100
                )
            )
        fields = [{'name': 'Structure', 'value': structure_name, 'inline': True},
                  {'name': 'System', 'value': system_name, 'inline': True},
                  {'name': 'Moon', 'value': moon.name, 'inline': True},
                  {'name': 'Type', 'value': structure_type.name, 'inline': True},
                  {'name': 'Auto Fire', 'value': auto_time.strftime("%Y-%m-%d %H:%M"), 'inline': False},
                  {'name': 'Ore', 'value': "\n".join(ore_string)},
                ]

        self.package_ping(title, 
                          body, 
                          self._notification.timestamp, 
                          fields=fields, 
                          footer=footer,
                          colour=6881024)

        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class MoonminingAutomaticFracture(NotificationPing):
    category = "moons-completed"  # Moon Pings

    """
        MoonminingAutomaticFracture Example 

        moonID: 40291417
        oreVolumeByType:
            45492: 1524501.871099406
            46677: 2656351.8252801565
            46678: 1902385.1244004236
            46681: 2110988.956997792
        solarSystemID: 30004612
        structureID: 1030287515076
        structureLink: <a href="showinfo:35835//1030287515076">NY6-FH - ISF-5</a>
        structureName: NY6-FH - ISF-5
        structureTypeID: 35835

    """
    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarSystemID'])

        system_name = system_db.name
        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        structure_name = self._data['structureName']
        if len(structure_name)<1:
            structure_name = "Unknown"

        moon, _ = ctm.MapSystemMoon.objects.get_or_create_from_esi(self._data['moonID'])

        title = "Moon Auto-Fractured!"
        body = "Ready to Mine!"

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker

        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        ores = {}       
        totalm3 = 0
        for t,q in self._data['oreVolumeByType'].items():
            ore, _ = ctm.EveItemType.objects.get_or_create_from_esi(t)
            ores[t] = ore.name
            totalm3 += q
        ore_string = []
        for t,q in self._data['oreVolumeByType'].items():
            ore_string.append(
                "**{}**: {:2.1f}%".format(
                    ores[t],
                    q/totalm3*100
                )
            )
        fields = [{'name': 'Structure', 'value': structure_name, 'inline': True},
                  {'name': 'System', 'value': system_name, 'inline': True},
                  {'name': 'Moon', 'value': moon.name, 'inline': True},
                  {'name': 'Type', 'value': structure_type.name, 'inline': True},
                  {'name': 'Ore', 'value': "\n".join(ore_string)},
                ]

        self.package_ping(title, 
                          body, 
                          self._notification.timestamp, 
                          fields=fields, 
                          footer=footer,
                          colour=6881024)

        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class MoonminingLaserFired(NotificationPing):
    category = "moons-completed"  # Moons pings

    """
        MoonminingLaserFired Example 

        firedBy: 824787891
        firedByLink: <a href="showinfo:1380//824787891">PoseDamen</a>
        moonID: 40291428
        oreVolumeByType:
            45493: 1983681.4476127427
            46679: 2845769.539271295
            46681: 2046606.19987059
            46688: 2115548.2348155645
        solarSystemID: 30004612
        structureID: 1029754054149
        structureLink: <a href="showinfo:35835//1029754054149">NY6-FH - ISF Two</a>
        structureName: NY6-FH - ISF Two
        structureTypeID: 35835

    """
    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarSystemID'])

        system_name = system_db.name
        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        structure_name = self._data['structureName']
        if len(structure_name)<1:
            structure_name = "Unknown"

        moon, _ = ctm.MapSystemMoon.objects.get_or_create_from_esi(self._data['moonID'])

        title = "Moon Laser Fired!"
        body = "Fired By [{0}](https://zkillboard.com/search/{1}/)".format(
            strip_tags(self._data['firedByLink']), 
            strip_tags(self._data['firedByLink']).replace(" ", "%20"))

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker

        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        ores = {}
        totalm3 = 0
        for t,q in self._data['oreVolumeByType'].items():
            ore, _ = ctm.EveItemType.objects.get_or_create_from_esi(t)
            ores[t] = ore.name
            totalm3 += q
        ore_string = []
        for t,q in self._data['oreVolumeByType'].items():
            ore_string.append(
                "**{}**: {:2.1f}%".format(
                    ores[t],
                    q/totalm3*100
                )
            )
        fields = [{'name': 'Structure', 'value': structure_name, 'inline': True},
                  {'name': 'System', 'value': system_name, 'inline': True},
                  {'name': 'Moon', 'value': moon.name, 'inline': True},
                  {'name': 'Type', 'value': structure_type.name, 'inline': True},
                  {'name': 'Ore', 'value': "\n".join(ore_string)},
                ]

        self.package_ping(title, 
                          body, 
                          self._notification.timestamp, 
                          fields=fields, 
                          footer=footer,
                          colour=16756480)

        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class MoonminingExtractionStarted(NotificationPing):
    category = "moons-started"  # Moons pings

    """
        MoonminingExtractionStarted Example 

        autoTime: 132071260201940545
        moonID: 40291428
        oreVolumeByType:
            45493: 2742775.374017656
            46679: 3934758.0841854215
            46681: 2829779.495126257
            46688: 2925103.528079887
        readyTime: 132071130601940545
        solarSystemID: 30004612
        startedBy: 824787891
        startedByLink: <a href="showinfo:1380//824787891">PoseDamen</a>
        structureID: 1029754054149
        structureLink: <a href="showinfo:35835//1029754054149">NY6-FH - ISF Two</a>
        structureName: NY6-FH - ISF Two
        structureTypeID: 35835

    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarSystemID'])

        system_name = system_db.name
        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        structure_name = self._data['structureName']
        if len(structure_name)<1:
            structure_name = "Unknown"

        moon, _ = ctm.MapSystemMoon.objects.get_or_create_from_esi(self._data['moonID'])

        title = "Moon Extraction Started!"
        body = "Fired By [{0}](https://zkillboard.com/search/{1}/)".format(
            strip_tags(self._data['startedByLink']), 
            strip_tags(self._data['startedByLink']).replace(" ", "%20"))

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker

        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}
        
        auto_time = filetime_to_dt(self._data['autoTime'])
        ready_time = filetime_to_dt(self._data['readyTime'])

        ores = {}
        totalm3 = 0
        for t,q in self._data['oreVolumeByType'].items():
            ore, _ = ctm.EveItemType.objects.get_or_create_from_esi(t)
            ores[t] = ore.name
            totalm3 += q
        ore_string = []
        for t,q in self._data['oreVolumeByType'].items():
            ore_string.append(
                "**{}**: {:2.1f}%".format(
                    ores[t],
                    q/totalm3*100
                )
            )
        fields = [{'name': 'Structure', 'value': structure_name, 'inline': True},
                  {'name': 'System', 'value': system_name, 'inline': True},
                  {'name': 'Moon', 'value': moon.name, 'inline': True},
                  {'name': 'Type', 'value': structure_type.name, 'inline': True},
                  {'name': 'Ready Time', 'value': ready_time.strftime("%Y-%m-%d %H:%M"), 'inline': False},
                  {'name': 'Auto Fire', 'value': auto_time.strftime("%Y-%m-%d %H:%M"), 'inline': False},
                  {'name': 'Ore', 'value': "\n".join(ore_string)},
                ]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=16756480)
        
        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class StructureLostShields(NotificationPing):
    category = "sturucture-attack"  # Structure Alerts

    """
        StructureLostShields Example 

        solarsystemID: 30004608
        structureID: &id001 1036096310753
        structureShowInfoData:
        - showinfo
        - 35835
        - *id001
        structureTypeID: 35835
        timeLeft: 958011150532
        timestamp: 132792333490000000
        vulnerableTime: 9000000000
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarsystemID'])

        system_name = system_db.name
        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        try:
            structure_name = ctm.EveLocation.objects.get(location_id=self._data['structureID']).location_name
        except ctm.EveLocation.DoesNotExist:
            # TODO find the name via esi and create the model
            structure_name = "Unknown"

        _secondsRemaining = self._data['timeLeft'] / 10000000  # seconds
        _refTimeDelta = datetime.timedelta(seconds=_secondsRemaining)
        tile_till = format_timedelta(_refTimeDelta)
        ref_date_time = self._notification.timestamp + _refTimeDelta

        title = structure_name
        body = "Structure has lost its Shields"

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        corp_name = "[%s](https://zkillboard.com/search/%s/)" % \
                                    (self._notification.character.character.corporation_name,
                                     self._notification.character.character.corporation_name.replace(" ", "%20"))
        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        fields = [{'name': 'System', 'value': system_name, 'inline': True},
                    {'name': 'Type', 'value': structure_type.name, 'inline': True},
                    {'name': 'Owner', 'value': corp_name, 'inline': False},
                    {'name': 'Time Till Out', 'value': tile_till, 'inline': False},
                    {'name': 'Date Out', 'value': ref_date_time.strftime("%Y-%m-%d %H:%M"), 'inline': False}]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=16756480)
        
        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class StructureLostArmor(NotificationPing):
    category = "sturucture-attack"  # Structure Alerts

    """
        StructureLostArmor Example 

        solarsystemID: 30004287
        structureID: &id001 1037256891589
        structureShowInfoData:
        - showinfo
        - 35835
        - *id001
        structureTypeID: 35835
        timeLeft: 2575911755713
        timestamp: 132776652750000000
        vulnerableTime: 18000000000
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarsystemID'])

        system_name = system_db.name
        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        try:
            structure_name = ctm.EveLocation.objects.get(location_id=self._data['structureID']).location_name
        except ctm.EveLocation.DoesNotExist:
            # TODO find the name via esi and create the model
            structure_name = "Unknown"

        _secondsRemaining = self._data['timeLeft'] / 10000000  # seconds
        _refTimeDelta = datetime.timedelta(seconds=_secondsRemaining)
        tile_till = format_timedelta(_refTimeDelta)
        ref_date_time = self._notification.timestamp + _refTimeDelta

        title = structure_name
        body = "Structure has lost its Armor"

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        corp_name = "[%s](https://zkillboard.com/search/%s/)" % \
                                    (self._notification.character.character.corporation_name,
                                     self._notification.character.character.corporation_name.replace(" ", "%20"))
        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        fields = [{'name': 'System', 'value': system_name, 'inline': True},
                    {'name': 'Type', 'value': structure_type, 'inline': True},
                    {'name': 'Owner', 'value': corp_name, 'inline': False},
                    {'name': 'Time Till Out', 'value': tile_till, 'inline': False},
                    {'name': 'Date Out', 'value': ref_date_time.strftime("%Y-%m-%d %H:%M"), 'inline': False}]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=16756480)
        
        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class StructureUnderAttack(NotificationPing):
    category = "sturucture-attack"  # Structure Alerts

    """
        StructureUnderAttack Example 

        allianceID: 500010
        allianceLinkData:
        - showinfo
        - 30
        - 500010
        allianceName: Guristas Pirates
        armorPercentage: 100.0
        charID: 1000127
        corpLinkData:
        - showinfo
        - 2
        - 1000127
        corpName: Guristas
        hullPercentage: 100.0
        shieldPercentage: 94.88716147275748
        solarsystemID: 30004608
        structureID: &id001 1036096310753
        structureShowInfoData:
        - showinfo
        - 35835
        - *id001
        structureTypeID: 35835
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarsystemID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name

        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        try:
            structure_name = ctm.EveLocation.objects.get(location_id=self._data['structureID']).location_name
        except ctm.EveLocation.DoesNotExist:
            # TODO find the name via esi and create the model
            structure_name = "Unknown"

        title = structure_name
        shld = float(self._data['shieldPercentage'])
        armr = float(self._data['armorPercentage'])
        hull = float(self._data['hullPercentage'])
        body = "Structure under Attack!\n[ S: {0:.2f}% A: {1:.2f}% H: {2:.2f}% ]".format(shld, armr, hull)

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker
        corp_name = "[%s](https://zkillboard.com/search/%s/)" % \
                                    (self._notification.character.character.corporation_name,
                                     self._notification.character.character.corporation_name.replace(" ", "%20"))
        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        attacking_char, _ = ctm.EveName.objects.get_or_create_from_esi(self._data['charID'])

        attackerStr = "*[%s](https://zkillboard.com/search/%s/)*, [%s](https://zkillboard.com/search/%s/), **[%s](https://zkillboard.com/search/%s/)**" % \
                                                    (attacking_char.name,
                                                    attacking_char.name.replace(" ", "%20"),
                                                    self._data.get('corpName', ""),
                                                    self._data.get('corpName', "").replace(" ", "%20"),
                                                    self._data.get('allianceName', "*-*"),
                                                    self._data.get('allianceName', "").replace(" ", "%20"))


        fields = [{'name': 'System', 'value': system_name, 'inline': True},
                    {'name': 'Region', 'value': region_name, 'inline': True},
                    {'name': 'Type', 'value': structure_type.name, 'inline': True},
                    {'name': 'Attacker', 'value': attackerStr, 'inline': False}]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=16756480)
        
        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class SovStructureReinforced(NotificationPing):
    category = "sov-attack"  # Structure Alerts

    """
        SovStructureReinforced Example

        campaignEventType: 2
        decloakTime: 132790589950971525
        solarSystemID: 30004639
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarSystemID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name

        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        title = "Entosis notification"
        body = "Sov Struct Reinforced in %s" % system_name

        if self._data['campaignEventType'] == 1:
            body = "TCU Reinforced in %s" % system_name
            sov_type = "TCU"
        elif self._data['campaignEventType'] == 2:
            body = "IHub Reinforced in %s" % system_name
            sov_type = "I-HUB"

        ref_time_delta = filetime_to_dt(self._data['decloakTime'])

        tile_till = format_timedelta(
            ref_time_delta.replace(tzinfo=datetime.timezone.utc) - datetime.datetime.now(datetime.timezone.utc))
        alli_id = self._notification.character.character.alliance_id
        alli_ticker = self._notification.character.character.alliance_ticker
        
        footer = {"icon_url": "https://images.evetech.net/alliances/%s/logo" % (str(alli_id)),
                    "text": "%s (%s)" % (self._notification.character.character.alliance_name, alli_ticker)}

        fields = [{'name': 'System', 'value': system_name, 'inline': True},
                    {'name': 'Region', 'value': region_name, 'inline': True},
                    {'name': 'Time Till Decloaks', 'value': tile_till, 'inline': False},
                    {'name': 'Date Out', 'value': ref_time_delta.strftime("%Y-%m-%d %H:%M"), 'inline': False}]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=16756480)
        
        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class EntosisCaptureStarted(NotificationPing):
    category = "sov-attack"  # Structure Alerts

    """
        EntosisCaptureStarted Example

        solarSystemID: 30004046
        structureTypeID: 32458
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarSystemID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name

        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        title = "Entosis Notification"

        body = "Entosis has started in %s on %s" % (system_name, structure_type.name)

        timestamp = self._notification.timestamp
        alli_id = self._notification.character.character.alliance_id
        alli_ticker = self._notification.character.character.alliance_ticker
        
        footer = {"icon_url": "https://images.evetech.net/alliances/%s/logo" % (str(alli_id)),
                    "text": "%s (%s)" % (self._notification.character.character.alliance_name, alli_ticker)}

        fields = [{'name': 'System', 'value': system_name, 'inline': True},
                    {'name': 'Region', 'value': region_name, 'inline': True}]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=16756480)
        
        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name


class OwnershipTransferred(NotificationPing):
    category = "alliance-admin"  # Structure Alerts

    """
        OwnershipTransferred Example

        charID: 972559932
        newOwnerCorpID: 98514543
        oldOwnerCorpID: 98465001
        solarSystemID: 30004626
        structureID: 1029829977992
        structureName: D4KU-5 - ducktales
        structureTypeID: 35835
    """

    def build_ping(self):
        system_db = ctm.MapSystem.objects.get(system_id=self._data['solarSystemID'])

        system_name = system_db.name
        region_name = system_db.constellation.region.name

        system_name = f"[{system_name}](http://evemaps.dotlan.net/system/{system_name.replace(' ', '_')})"
        region_name = f"[{region_name}](http://evemaps.dotlan.net/region/{region_name.replace(' ', '_')})"

        structure_type, _ = ctm.EveItemType.objects.get_or_create_from_esi(self._data['structureTypeID'])

        structure_name = self._data['structureName']

        title = "Structure Transfered"

        originator, _ = ctm.EveName.objects.get_or_create_from_esi(self._data['charID'])
        new_owner, _ = ctm.EveName.objects.get_or_create_from_esi(self._data['newOwnerCorpID'])
        old_owner, _ = ctm.EveName.objects.get_or_create_from_esi(self._data['oldOwnerCorpID'])

        body = "Structure Transfered from %s to %s" % (old_owner.name, new_owner.name)

        corp_id = self._notification.character.character.corporation_id
        corp_ticker = self._notification.character.character.corporation_ticker

        footer = {"icon_url": "https://imageserver.eveonline.com/Corporation/%s_64.png" % (str(corp_id)),
                  "text": "%s (%s)" % (self._notification.character.character.corporation_name, corp_ticker)}

        fields = [{'name': 'Structure', 'value': structure_name, 'inline': True},
                    {'name': 'System', 'value': system_name, 'inline': True},
                    {'name': 'Region', 'value': region_name, 'inline': True},
                    {'name': 'Type', 'value': structure_type.name, 'inline': True},
                    {'name': 'Originator', 'value': originator.name, 'inline': True}
                    ]

        self.package_ping(title,
                          body,
                          self._notification.timestamp,
                          fields=fields,
                          footer=footer,
                          colour=16756480)
        
        self._corp = self._notification.character.character.corporation_id
        self._region = system_db.constellation.region.name

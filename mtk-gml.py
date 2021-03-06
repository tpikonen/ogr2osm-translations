# coding=utf-8

# Translation of feature class numbers from National Land Survey of Finlands
# Maastotietokanta to Openstreetmap tag sets.
#
# Translation tables originally from Openstreetmap wiki,
# http://wiki.openstreetmap.org/wiki/Fi:Maastotietokanta/Luokat
#
# Copyright (c) 2013 Teemu Ikonen <tpikonen@gmail.com>
# License: MIT License http://opensource.org/licenses/mit-license.php

import geom
from osgeo import ogr
import re
import logging as l


def filterLayer(layer):
    skiplayers = [
        "AidanSymboli",
        "HarvaLouhikko",
        "Kaislikko",
        "Kalliohalkeama",
        "KallioSymboli",
        "Karttasymboli",
        "Korkeuskayra",
        "KorkeuskayranKorkeusarvo",
        "KunnanHallintokeskus",
        "Maasto2kuvionReuna",
        "MaastokuvionReuna",
        "MerkittavaLuontokohde",
        "MetsamaanKasvillisuus",
        "MetsamaanMuokkaus",
        "MetsanRaja",
        "Pelastuskoodipiste",
        "PutkijohdonSymboli",
        "RajavyohykkeenTakaraja",
        "Rakennusreunaviiva",
        "RautatienSymboli",
        "SahkolinjanSymboli",
        "SavupiipunKorkeus",
        "Selite",
        "SisaistenAluevesienUlkoraja",
        "SuojaAlueenReunaviiva",
        "SuojametsanReunaviiva",
        "Suojanne",
        "SuojelualueenReunaviiva",
        "Syvyyskayra",
        "SyvyyskayranSyvyysarvo",
        "TaajaanRakennettuAlue",
        "TaajaanRakennetunAlueenReuna",
        "Taytemaa",
        "Tiesymboli",
        "TunnelinAukko",
        "Uittoranni",
        "UlkoJaSisasaaristonRaja",
        "Varastoalue",
        "VesikulkuvaylanKulkusuunta",
        "VesikulkuvaylanTeksti",
        "Viettoviiva",
        "Virtausnuoli",
    ]
    if layer.GetName() in skiplayers:
        l.debug("Skipping layer '%s'" % layer.GetName())
        return None
    else:
        l.debug("Processing layer '%s'" % layer.GetName())
        return layer


def filterFeaturePost(feature, ogrfeature, ogrgeometry):
    if feature is None and ogrfeature is None and ogrgeometry is None:
        return
    kohdeluokka = ogrfeature['kohdeluokka']
    if kohdeluokka in mtk_roadfeatures:
        feature.tags = mtk_roadfeatures[kohdeluokka](ogrfeature, feature)
    else:
        feature.tags = mtk_features.get(kohdeluokka, mtk_default)(ogrfeature)
    feature.tags['source'] = 'MTK_2013' # FIXME: Read year from input XML


def ustr(x):
    return unicode(str(x), 'utf_8') # MTK XML is encoded in UTF-8


def fget(ogrfeature, key, default=None):
    """Get a value from ogrfeature['key'], return default if does not exist."""
    try:
        val = ogrfeature[key]
    except ValueError:
        val = default
    if val is None:
        val = default
    return val


def mtk_default(f):
    l.warn("Kohdeluokka %s not known to this script" % f['kohdeluokka'])
    return {}


def mtk_getnimi(f):
    """Return a name string from various nimi_* features."""
    # nimi_* features in Osoitepiste and Tieviiva layers giving the name in
    # various languages. Roughly in order of how common they are.
    nimi_feats = [ "nimi_suomi", "nimi_ruotsi", "nimi_inarinsaame",
    "nimi_koltansaame", "nimi_pohjoissaame" ]
    nimi = None
    for lang in nimi_feats:
        nimi = fget(f, lang)
        if nimi:
            nimi = ustr(nimi)
            break
    return nimi


def mtk_highway(o, f):
    tags = { "highway" : "road" }
    taso = int(fget(o, 'tasosijainti', 0))
    if taso == -11:
        tags["tunnel"] = "yes"
    elif taso != 0:
        tags["layer"] = ustr(taso)
    # FIXME: f['valmiusaste'] ?
    paallyste = int(fget(o, 'paallyste', 0))
    if paallyste > 0:
        tags["surface"] = "paved" if paallyste == 2 else "unpaved"
    yksisuun = int(fget(o, 'yksisuuntaisuus', 0))
    if yksisuun > 0:
        tags["oneway"] = "yes" if yksisuun == 1 else "-1"
    nimi = mtk_getnimi(o)
    if nimi:
        tags["name"] = nimi
    # Add address interpolation to (high)ways, when sensible
    # address numbers for beginning and end of the road segment exist.
    minleftnum = int(fget(o, 'minOsoitenumeroVasen', -1))
    minrightnum = int(fget(o, 'minOsoitenumeroOikea', -1))
    if minleftnum < 1:
        minaddress = minrightnum
    elif minrightnum < 1:
        minaddress = minleftnum
    else:
        minaddress = min(minrightnum, minleftnum)
    maxleftnum = int(fget(o, 'maxOsoitenumeroVasen', -1))
    maxrightnum = int(fget(o, 'maxOsoitenumeroOikea', -1))
    if maxleftnum < 1:
        maxaddress = maxrightnum
    elif maxrightnum < 1:
        maxaddress = maxleftnum
    else:
        maxaddress = max(maxrightnum, maxleftnum)
    if minaddress > 0 and maxaddress > 0:
        # Feature constructor appends the created objects to
        # a class variable Feature.features
        fmin = geom.Feature()
        fmin.geometry = f.geometry.points[0]
        fmin.tags = { "addr:housenumber" : ustr(minaddress) }
        fmax = geom.Feature()
        fmax.geometry = f.geometry.points[-1]
        fmax.tags = { "addr:housenumber" : ustr(maxaddress) }
        tags["addr:interpolation"] = "all"
    return tags


def mtk_12112(o, f):
    tags = mtk_highway(o, f)
    tags["highway"] = "trunk"
    nimi = mtk_getnimi(o)
    if nimi:
        if nimi == 'Valtatie':
            nro = ustr(fget(o, 'tienumero', ''))
            nimi = nimi + " " + nro
            nimi= nimi.strip()
        tags["name"] = nimi
    return tags


def mtk_12141(o, f):
    tags = mtk_highway(o, f)
    tags["highway"] = "track"
    if "surface" in tags and tags["surface"] == "paved":
        tags["tracktype"] = "grade1"
    else:
        tags["tracktype"] = "grade2"
    return tags


def mtk_surveypoint(f):
    tags = { "man_made" : "survey_point" }
    height = fget(f, 'korkeusarvo')
    if height:
        tags["ele:n60"] = ustr(float(height) / 1000.0)
    return tags


def mtk_railway(f):
    tags = {}
    state = int(fget(f, "valmiusaste", 0))
    if state == 0:
        tags["railway"] = "rail" # In use
    elif state == 1:
        tags["railway"] = "construction" # Under construction
    elif state == 2:
        tags["railway"] = "disused"
    elif state == 4:
        return tags # Being planned, do not add
    taso = int(fget(f, 'tasosijainti', 0))
    if taso == -11:
        tags["tunnel"] = "yes"
    elif taso != 0:
        tags["layer"] = ustr(taso)
    electrified = int(fget(f, 'sahkoisyys', 0))
    if electrified == 0:
        pass # unknown
    elif electrified == 1:
        tags["electrified"] = "yes"
    elif electrified == 2:
        tags["electrified"] = "no"
    return tags


mtk_roadfeatures = {
# Autotie Ia
12111 : lambda o,f: dict(mtk_highway(o,f).items() + {"highway":"motorway"}.items()),
# Autotie Ib
12112 : mtk_12112, # trunk
# Autotie IIa
12121 : lambda o,f: dict(mtk_highway(o,f).items() + {"highway":"primary"}.items()),
# Autotie IIb
12122 : lambda o,f: dict(mtk_highway(o,f).items()+{"highway":"secondary"}.items()),
# Autotie IIIa
12131 : lambda o,f: dict(mtk_highway(o,f).items() + {"highway":"residential"}.items()),
# Autotie IIIb
12132 : lambda o,f: dict(mtk_highway(o,f).items() + {"highway":"service"}.items()),
# Ajotie
12141 : mtk_12141, # track, grade 1 or 2
# Lautta
12151 : lambda o,f: { "route" : "ferry", },
# Lossi
12152 : lambda o,f: { "route" : "ferry", "type" : "cable", },
# Talvitie
12312 : lambda o,f: dict(mtk_highway(o,f).items() + {"winter_road":"yes"}.items()),
# Polku
12313 : lambda o,f: dict(mtk_highway(o,f).items() + {"highway":"path"}.items()),
# Kävely- ja pyörätie
12314 : lambda o,f: dict(mtk_highway(o,f).items() + \
            { "highway" : "cycleway", "foot" : "designated" }.items()),
# Ajopolku
12316 : lambda o,f: dict(mtk_highway(o,f).items() + { "highway":"track", "tracktype" : "grade3" }.items()),
}


mtk_features = {
# featureclass (kohdeluokka) : function from ogrfeature to OSM tag dict
# Work in progress.
# Suoja-alue
62200 : lambda _: { "seamark:type" : "restricted_area", },
# Ampuma-alueen reunaviiva
62100 : lambda _: { "landuse" : "military", "military" : "range", },
# Suoja-alueen reunaviiva
#62200 : lambda _: {}, # Same class as Suoja-alue (!)
# Kunta
84200 : lambda f: { "type" : "boundary", "boundary" : "administrative", "admin_level" : "8", "ref" : ustr(fget(f, 'kuntatunnus', 'FIXME')), "name" : "FIXME", "place" : "FIXME", },
# Valtakunnan rajapyykki
82500 : lambda _: { "man_made" : "cairn", },
# Muu kaupunki
84302 : lambda _: {},
# Muu kunta
84303 : lambda _: {},
# Aluemeren ulkoraja
82100 : lambda _: { "boundary" : "administrative", "admin_level" : "2", },
# Valtakunnan raja
84111 : lambda _: { "boundary" : "administrative", "admin_level" : "2", },
# Aluehallintoviraston toimialueen raja
84112 : lambda _: { "boundary" : "administrative", "admin_level" : "4", },
# Kunnan raja
84113 : lambda _: { "boundary" : "administrative", "admin_level" : "8", },
# Käymätön raja
84114 : lambda _: { "boundary" : "administrative", "admin_level" : "8", },
# Maakunnan raja
84115 : lambda _: { "boundary" : "administrative", "admin_level" : "6", },
# Rajavyöhykkeen takaraja
82200 : lambda _: {},
# Sisäisten aluevesien ulkoraja
82300 : lambda _: {},
# Ulko- ja sisäsaariston raja
82400 : lambda _: {},
# Muuntaja
22100 : lambda _: { "power" : "transformer", },
# Putkijohdon symboli, luokittelematon
26190 : lambda _: {},
# Putkijohdon symboli, kaasu
26191 : lambda _: {},
# Putkijohdon symboli, kiinteä aine
26192 : lambda _: {},
# Putkijohdon symboli, lämpö
26193 : lambda _: {},
# Putkijohdon symboli, vesi
26194 : lambda _: {},
# Putkijohdon symboli, vesihöyry
26195 : lambda _: {},
# Putkijohdon symboli, viemäri
26196 : lambda _: {},
# Putkijohdon symboli, öljy
26197 : lambda _: {},
# Suurjännitelinjan pylväs
22392 : lambda _: { "power" : "tower", },
# Sähkölinjan symboli (tallennettu alaluokkiin)
22391 : lambda _: {},
# Suurjännitelinjan symboli
22394 : lambda _: {},
# Jakelujännitelinjan symboli
22395 : lambda _: {},
# Vedenottamo
26200 : lambda _: { "man_made" : "water_works", },
# Vesitorni
45800 : lambda _: { "man_made" : "water_tower", },
# Muuntoasema
22200 : lambda _: { "power" : "station", },
# Putkijohto, luokittelematon
26111 : lambda _: { "man_made" : "pipeline", },
# Putkijohto, kaasu
26111 : lambda _: { "man_made" : "pipeline", "type" : "gas", },
# Putkijohto, kiinteä aine
26112 : lambda _: { "man_made" : "pipeline", "type" : "solid", },
# Putkijohto, lämpö
26113 : lambda _: { "man_made" : "pipeline", "type" : "heat", },
# Putkijohto, vesi
26114 : lambda _: { "man_made" : "pipeline", "type" : "water", },
# Putkijohto, vesihöyry
26115 : lambda _: { "man_made" : "pipeline", "type" : "steam", },
# Putkijohto, viemäri
26116 : lambda _: { "man_made" : "pipeline", "type" : "sewage", },
# Putkijohto, öljy
26117 : lambda _: { "man_made" : "pipeline", "type" : "oil", },
# Sähkölinja (tallennettu alaluokkiin)
22300 : lambda _: { "power" : "line", },
# Sähkölinja, suurjännite
22311 : lambda _: { "power" : "line", },
# Sähkölinja, jakelujännite
22312 : lambda _: { "power" : "minor_line", },
# Eloperäinen ainessymboli
32191 : lambda _: {},
# Hieno kivennäisainessymboli
32192 : lambda _: {},
# Hautausmaan symboli
32291 : lambda _: {},
# Louhoksen symboli
32591 : lambda _: {},
# Niityn symboli
32891 : lambda _: {},
# Täytemaan symboli
33091 : lambda _: {},
# Varastoalueen symboli
38991 : lambda _: {},
# Tunnelin aukko
16800 : lambda _: {},
# Kolmiopiste, luokittelematon
95100 : mtk_surveypoint,
# Kolmiopiste, I luokka
95111 : mtk_surveypoint,
# Kolmiopiste, II luokka
95112 : mtk_surveypoint,
# Kolmiopiste, III luokka
95113 : mtk_surveypoint,
# Korkeuskiintopiste, luokittelematon
95200 : mtk_surveypoint,
# Korkeuskiintopiste, I luokka
95211 : mtk_surveypoint,
# Korkeuskiintopiste, II luokka
95212 : mtk_surveypoint,
# Korkeuskiintopiste, III luokka
95213 : mtk_surveypoint,
# Korkeuskiintopiste, IV luokka
95214 : mtk_surveypoint,
# Vesiasteikko
95300 : lambda _: { "man_made" : "monitoring_station", "monitoring:river_level" : "yes", },
# Korkeuskäyrän viettoviiva
52192 : lambda _: {},
# Apukäyrän viettoviiva
52193 : lambda _: {},
# Syvyyskäyrän viettoviiva
54192 : lambda _: {},
# Korkeuskäyrän korkeusarvo
52191 : lambda _: {},
# Korkeuspiste
52210 : lambda f: { "ele:n60" : ustr(f['teksti']), },
# Syvyyskäyrän syvyysarvo
54191 : lambda _: {},
# Syvyyspiste
54210 : lambda f: { "depth" : ustr(f['teksti']), },
# Korkeuskäyrä
52100 : lambda _: {},
# Syvyyskäyrä
54100 : lambda _: {},
# Autoliikennealue
32421 : lambda _: { "amenity" : "parking", },
# Hautausmaa
32200 : lambda _: { "landuse" : "cemetery", },
# Hietikko
34300 : lambda _: { "natural" : "sand", },
# Kaatopaikka
32300 : lambda _: { "landuse" : "landfill", },
# Kallio - alue
34100 : lambda _: { "natural" : "bare_rock", "area" : "yes" },
# Kivikko
34700 : lambda _: { "natural" : "scree", },
# Lentokenttäalue, tuntematon
32400 : lambda _: { "aeroway" : "aerodrome", },
# Lentokentän kiitotie, päällystetty
32411 : lambda _: { "aeroway" : "runway", "surface" : "paved", },
# Lentokentän kiitotie, päällystämätön
32412 : lambda _: { "aeroway" : "runway", "surface" : "unpaved", },
# Muu lentokenttäalue
32413 : lambda _: { "aeroway" : "aerodrome", },
# Muu lentokenttäalue, päällystetty
32415 : lambda _: { "aeroway" : "aerodrome", },
# Muu lentokenttäalue, päällystämätön
32416 : lambda _: { "aeroway" : "aerodrome", },
# Muu lentoliikennealue
32414 : lambda _: { "aeroway" : "aerodrome", },
# Muu lentoliikennealue, päällystetty
32417 : lambda _: { "aeroway" : "aerodrome", },
# Muu lentoliikennealue, päällystämätön
32418 : lambda _: { "aeroway" : "aerodrome", },
# Louhos
32500 : lambda _: { "landuse" : "quarry", },
# Maa-aineksenottoalue, luokittelematon
32100 : lambda _: { "landuse" : "quarry", "resource" : "aggregate", },
# Maa-aineksenottoalue, karkea kivennäisaines
32111 : lambda _: { "landuse" : "quarry", "resource" : "aggregate", },
# Maa-aineksenottoalue, hieno kivennäisaines
32112 : lambda _: { "landuse" : "quarry", "resource" : "clay", },
# Maa-aineksenottoalue, eloperäinen aines
32113 : lambda _: { "landuse" : "quarry", "resource" : "organic", },
# Pelto
32611 : lambda _: { "landuse" : "farm", },
# Puutarha
32612 : lambda _: { "landuse" : "orchard", },
# Niitty
32800 : lambda _: { "landuse" : "meadow", },
# Puisto
32900 : lambda _: { "leisure" : "park", },
# Soistuma
35300 : lambda _: { "natural" : "wetland", "wetland" : "swamp", },
# Suo (tallennettu alaluokkiin)
35400 : lambda _: { "natural" : "wetland", },
# Suo, helppokulkuinen puuton
35411 : lambda _: { "natural" : "wetland", },
# Suo, helppokulkuinen metsää kasvava
35412 : lambda _: { "natural" : "wetland", },
# Suo, vaikeakulkuinen puuton
35421 : lambda _: { "natural" : "wetland", "wetland" : "marsh", },
# Suo, vaikeakulkuinen metsää kasvava
35422 : lambda _: { "natural" : "wetland", "wetland" : "swamp", },
# Täytemaa
33000 : lambda _: {},
# Urheilu- ja virkistysalue
33100 : lambda _: { "landuse" : "recreation_ground" },
# Järvivesi
36200 : lambda _: { "natural" : "water", },
# Merivesi
36211 : lambda _: { "natural" : "coastline", },
# Virtavesialue
36313 : lambda _: { "waterway" : "riverbank", },
# Harva louhikko
34200 : lambda _: {},
# Kallio - symboli
#34100 : lambda _: {}, # Same class as Kallio - alue (!)
# Kivi
34600 : lambda _: { "natural" : "stone", },
# Lähde
36100 : lambda _: { "natural" : "spring", },
# Merkittävä luontokohde
34900 : lambda _: {},
# Havumetsä
32710 : lambda _: {},
# Lehtimetsä
32713 : lambda _: {},
# Sekametsä
32714 : lambda _: {},
# Varvikko
32715 : lambda _: {},
# Pensaikko
32719 : lambda _: {},
# Metsämaan ojitus
32721 : lambda _: {},
# Puu
35100 : lambda _: { "natural" : "tree", },
# Vesikuoppa
# FIXME: 36400 is a point, is it rendered as natural=water?
36400 : lambda _: { "natural" : "water", "water" : "pond" },
# Virtaveden juoksusuunta (tallennettu alaluokkiin)
36391 : lambda _: {},
# Kapean virtaveden juoksusuunta
36392 : lambda _: {},
# Leveän virtaveden juoksusuunta
36393 : lambda _: {},
# Vedenpinnan korkeusluku
36291 : lambda f: { "ele:n60" : ustr(f['teksti']), },
# Jyrkänne
34400 : lambda _: { "natural" : "cliff", },
# Kalliohalkeama
34500 : lambda _: {},
# Luiska
34800 : lambda _: {  "embankment" : "yes", },
# Yksikäsitteinen reunaviiva
30211 : lambda _: {},
# Epämääräinen reunaviiva
30212 : lambda _: {},
# Keinotekoinen rantaviiva
30100 : lambda _: {},
# Vesialueiden välinen reuna
30900 : lambda _: {},
# Pato
30300 : lambda _: { "waterway" : "dam", },
# Puurivi
35200 : lambda _: { "natural" : "tree_row", },
# Sulkuportti
30400 : lambda _: { "waterway" : "lock_gate", },
# Suojänne
35500 : lambda _: {},
# Maasto/1 tekninen viiva
30999 : lambda _: {},
# Virtavesi - kapea
36300 : lambda _: { "waterway" : "stream", },
# Virtavesi, alle 2m
36311 : lambda _: { "waterway" : "stream", },
# Virtavesi, 2-5m
36312 : lambda _: { "waterway" : "river", },
# Maatuva vesialue
38300 : lambda _: { "natural" : "wetland", "wetland" : "reedbed", },
# Matalikko
38700 : lambda _: { "seamark:type" : "sea_area", "seamark:sea_area:category" : "shoal", },
# Muu avoin alue, luokittelematon
39100 : lambda _: {},
# Avoin metsämaa
39110 : lambda _: {},
# Varvikko
39120 : lambda _: { "natural" : "scrub", },
# Avoin vesijättö
39130 : lambda _: { "natural" : "wetland", "wetland" : "wet_meadow", },
# Tulva-alue
38400 : lambda _: { "natural" : "wetland", "wetland" : "tidalflat", },
# Varastoalue
38900 : lambda _: {},
# Vesikivikko
38600 : lambda _: { "seamark:type" : "seabed_area", "seamark:seabed_area:surface" : "stone", },
# Kaislikko
38100 : lambda _: {},
# Uittolaite
38800 : lambda _: { "seamark:mooring:category" : "dolphin", "seamark:type" : "mooring", },
# Vesikivi, vedenalainen
38511 : lambda _: { "seamark:type" : "rock", "seamark:rock:water_level" : "submerged", },
# Vesikivi, pinnassa
38512 : lambda _: { "seamark:type" : "rock", "seamark:rock:water_level" : "awash", },
# Vesikivi, vedenpäällinen
38513 : lambda _: { "seamark:type" : "rock", "seamark:rock:water_level" : "always_dry", },
# Koski
38200 : lambda _: { "whitewater:rapid_grade" : "unknown", },
# Maasto/2 kuvion reuna, luokittelematon
30200 : lambda _: {},
# Maasto/2 yksikäsitteinen reunaviiva
30211 : lambda _: {},
# Maasto/2 epämääräinen reunaviiva
30212 : lambda _: {},
# Metsän raja
39500 : lambda _: {},
# Uittoränni
39000 : lambda _: {},
# Maasto/2 tekninen viiva
30999 : lambda _: {},
# Huomaute
3001 : lambda _: {},
# Lähiosoite
96001 : lambda f: { "addr:full" : unicode.strip(mtk_getnimi(f) + " " + ustr(fget(f, "numero", ""))) } if mtk_getnimi(f) is not None else {},
# Kulkupaikka
96002 : lambda _: {},
# Pelastuskoodipiste
96010 : lambda _: {},
# Autotien nimi
12101 : lambda _: {},
# Kulkuväylän nimi
12301 : lambda _: {},
# Rautatieliikennepaikan nimi
14201 : lambda f: { "railway" : "station", "name" : ustr(f['teksti']), },
# Turvalaitteen nimi
16101 : lambda _: {},
# Maa-aineksenottoalueen nimi
32101 : lambda f: { "landuse" : "quarry", "name" : ustr(f['teksti']), },
# Hautausmaan nimi
32201 : lambda f: { "landuse" : "cemetery", "name" : ustr(f['teksti']), },
# Kaatopaikan nimi
32301 : lambda f: { "landuse" : "landfill", "name" : ustr(f['teksti']), },
# Liikennealueen nimi
32401 : lambda _: {},
# Louhoksen nimi
32501 : lambda f: { "landuse" : "quarry", "name" : ustr(f['teksti']), },
# Puiston nimi
32901 : lambda f: { "leisure" : "park", "name" : ustr(f['teksti']), },
# Täytemaan nimi
33001 : lambda _: {},
# Urheilu- ja virkistysalueen nimi
33101 : lambda f: { "leisure" : "sports_centre", "name" : ustr(f['teksti']), },
# Kiven nimi
34601 : lambda f: { "natural" : "stone", "name" : ustr(f['teksti']), },
# Merkittävän luontokohteen nimi
34901 : lambda f: { "natural" : "feature", "name" : ustr(f['teksti']), },
# Pellon tai niityn nimi
35010 : lambda f: { "place" : "locality", "name" : ustr(f['teksti']), },
# Metsäalueen nimi
35020 : lambda f: { "place" : "locality", "name" : ustr(f['teksti']), },
# Suon nimi
35030 : lambda f: { "place" : "locality", "name" : ustr(f['teksti']), },
# Kohouman nimi
35040 : lambda f: { "place" : "locality", "name" : ustr(f['teksti']), },
# Painanteen nimi
35050 : lambda f: { "place" : "locality", "name" : ustr(f['teksti']), },
# Niemen nimi
35060 : lambda f: { "place" : "locality", "name" : ustr(f['teksti']), },
# Saaren nimi
35070 : lambda f: { "place" : "islet", "name" : ustr(f['teksti']), },
# Matalikon nimi
35080 : lambda f: { "natural" : "shoal", "name" : ustr(f['teksti']), },
# Muu maastonimi
35090 : lambda f: { "place" : "locality", "name" : ustr(f['teksti']), },
# Puun nimi
35101 : lambda f: { "natural" : "tree", "name" : ustr(f['teksti']), },
# Lähteen nimi
36101 : lambda f: { "natural" : "spring", "name" : ustr(f['teksti']), },
# Vakaveden nimi
36201 : lambda f: { "natural" : "water", "water" : "lake", "name" : ustr(f['teksti']), },
# Virtaveden nimi
36301 : lambda f: { "natural" : "water", "water" : "river", "name" : ustr(f['teksti']), },
# Vakaveden osan nimi
36410 : lambda f: { "natural" : "bay", "name" : ustr(f['teksti']), },
# Virtaveden osan nimi
36420 : lambda f: { "natural" : "bay", "name" : ustr(f['teksti']), },
# Muu vesistökohteen nimi
36490 : lambda f: { "natural" : "bay", "name" : ustr(f['teksti']), },
# Kosken nimi
38201 : lambda f: { "waterway" : "rapids", "name" : ustr(f['teksti']), },
# Vesikiven nimi
38501 : lambda f: { "natural" : "rock", "name" : ustr(f['teksti']), },
# Varastoalueen nimi
38901 : lambda _: {},
# Rakennuksen nimi
42101 : lambda f: { "place" : "isolated_dwelling", "name" : ustr(f['teksti']),},
# Rakennusryhmän nimi
42201 : lambda f: { "place" : "hamlet", "name" : ustr(f['teksti']), },
# Altaan nimi
44301 : lambda f: { "natural" : "water", "water" : "pond", "name" : ustr(f['teksti']), },
# Muistomerkin nimi
44901 : lambda f: { "historic" : "memorial", "name" : ustr(f['teksti']), },
# Kaupungin nimi
48111 : lambda f: { "place" : "town", "name" : ustr(f['teksti']), },
# Muun kunnan nimi
48112 : lambda f: { "place" : "village", "name" : ustr(f['teksti']), },
# Kylän, kaupunginosan tai kulmakunnan nimi
48120 : lambda f: { "place" : "suburb", "name" : ustr(f['teksti']), },
# Talon nimi
48130 : lambda f: { "place" : "isolated_dwelling", "name" : ustr(f['teksti']),},
# Muu asutusnimi
48190 : lambda f: { "place" : "isolated_dwelling", "name" : ustr(f['teksti']),},
# Luonnonsuojelualueen nimi
#72201 : lambda _: {}, # Same class as Luonnonpuisto (!)
# Luonnonmuistomerkin nimi
72303 : lambda _: {},
# Muinaisjäännöksen nimi
72403 : lambda f: { "historic" : "archaeological_site", "name" : ustr(f['teksti']), },
# Luonnonpuiston nimi
72502 : lambda f: { "leisure" : "nature_reserve", "name" : ustr(f['teksti']), },
# Kansallispuiston nimi
72601 : lambda f: { "leisure" : "nature_reserve", "name" : ustr(f['teksti']), },
# Erämaa-alueen nimi
72701 : lambda f: { "boundary" : "protected_area", "protect_class" : "1a", "name" : ustr(f['teksti']), },
# Retkeilyalueen nimi
72801 : lambda f: { "tourism" : "camp_site", "name" : ustr(f['teksti']), },
# Valtakunnan rajapyykin nimi
82501 : lambda _: {},
# Rajapyykin nimi
92401 : lambda _: {},
# Allas - alue
44300 : lambda _: { "landuse" : "reservoir", },
# Ilmaradan kannatinpylväs
44591 : lambda _: { "aerialway" : "pylon", },
# Kellotapuli
44600 : lambda _: { "man_made" : "tower", "tower:type" : "bell_tower", },
# Lähestymisvalo
44700 : lambda _: { "man_made" : "beacon", },
# Masto
44800 : lambda _: { "man_made" : "mast", "mast:type" : "communication", },
# Muistomerkki
44900 : lambda _: { "historic" : "memorial", },
# Näkötorni
45000 : lambda _: { "man_made" : "tower", "tower:type" : "observation", },
# Portti
45200 : lambda _: { "barrier" : "gate", },
# Savupiippu
45300 : lambda _: { "man_made" : "chimney", },
# Tervahauta
45400 : lambda _: { "man_made" : "tar_kiln", },
# Tulentekopaikka
45710 : lambda _: { "tourism" : "picnic_site", "fireplace" : "yes", },
# Tuulimoottori
45500 : lambda _: { "power" : "generator", "power_source" : "wind", },
# Maston korkeus
44803 : lambda f: { "man_made" : "tower", "height" : ustr(float(fget(f, 'korkeusarvo', 0.0))/1000.0), },
# Savupiipun korkeus
45303 : lambda _: { },
# Aallonmurtaja
44100 : lambda _: { "man_made" : "breakwater", },
# Aita,tekoaines
44211 : lambda _: { "barrier" : "fence", "fixme" : "wall?", },
# Aita, istutettu
44213 : lambda _: { "barrier" : "hedge", },
# Allas - viiva
#44300 : lambda _: {}, # Same class as Allas - alue (!)
# Ilmarata
44500 : lambda _: { "aerialway": "unknown", },
# Pistolaituri, alle 5 m
45111 : lambda _: { "man_made" : "pier", },
# Pistolaituri, vähintään 5 m
45112 : lambda _: { "man_made" : "pier", "area" : "yes", },
# Rakennelma
45700 : lambda _: { "man_made" : "yes", },
## Building border lines are not imported
# Rakennusalueen reunaviiva, luokittelematon
42200 : lambda _: {},
# Asuinrakennus, ? krs
42110 : lambda _: {},
# Asuinrakennus, 1-2 krs
42111 : lambda _: {},
# Asuinrakennus, 3-n krs
42112 : lambda _: {},
# Liike- tai julkinen rakennus, ? krs
42120 : lambda _: {},
# Liike- tai julkinen rakennus, 1-2 krs
42121 : lambda _: {},
# Liike- tai julkinen rakennus, 3-n krs
42122 : lambda _: {},
# Lomarakennus, ? krs
42130 : lambda _: {},
# Lomarakennus, 1-2 krs
42131 : lambda _: {},
# Lomarakennus, 3-n krs
42132 : lambda _: {},
# Teollinen rakennus, ? krs
42140 : lambda _: {},
# Teollinen rakennus, 1-2 krs
42141 : lambda _: {},
# Teollinen rakennus, 3-n krs
42142 : lambda _: {},
# Kirkko
42170 : lambda _: {},
# Kirkollinen rakennus, ? krs
42150 : lambda _: {},
# Kirkollinen rakennus, 1-2 krs
42151 : lambda _: {},
# Kirkollinen rakennus, 3-n krs
42152 : lambda _: {},
# Muu rakennus, ? krs
42160 : lambda _: {},
# Muu rakennus, 1-2 krs
42161 : lambda _: {},
# Muu rakennus, 3-n krs
42162 : lambda _: {},
## Building border lines end
# Rakennus, luokittelematon
42200 : lambda _: { "building" : "yes", },
# Asuinrakennus, ? krs
42210 : lambda _: { "building" : "residential", },
# Asuinrakennus, 1-2 krs
42211 : lambda _: { "building" : "residential", },
# Asuinrakennus, 3-n krs
42212 : lambda _: { "building" : "residential", },
# Liike- tai julkinen rakennus, ? krs
42220 : lambda _: { "building" : "public", },
# Liike- tai julkinen rakennus, 1-2 krs
42221 : lambda _: { "building" : "public", },
# Liike- tai julkinen rakennus, 3-n krs
42222 : lambda _: { "building" : "public", },
# Lomarakennus, ? krs
42230 : lambda _: { "building" : "yes", },
# Lomarakennus, 1-2 krs
42231 : lambda _: { "building" : "yes", },
# Lomarakennus, 3-n krs
42232 : lambda _: { "building" : "yes", },
# Teollinen rakennus, ? krs
42240 : lambda _: { "building" : "industrial", },
# Teollinen rakennus, 1-2 krs
42241 : lambda _: { "building" : "industrial", },
# Teollinen rakennus, 3-n krs
42242 : lambda _: { "building" : "industrial", },
# Kirkko
42270 : lambda _: { "building" : "church", "amenity" : "place_of_worship", "religion" : "christian", },
# Kirkollinen rakennus, ? krs
42250 : lambda _: { "building" : "public", },
# Kirkollinen rakennus, 1-2 krs
42251 : lambda _: { "building" : "public", },
# Kirkollinen rakennus, 3-n krs
42252 : lambda _: { "building" : "public", },
# Muu rakennus, ? krs
42260 : lambda _: { "building" : "yes", },
# Muu rakennus, 1-2 krs
42261 : lambda _: { "building" : "yes", },
# Muu rakennus, 3-n krs
42262 : lambda _: { "building" : "yes", },
# Rautatieliikennepaikka
14200 : lambda _: { "railway" : "station" },
# Rautatie, sähköistyssymboli
14191 : lambda _: {},
# Rautatie, käytöstä poistetun symboli
14192 : lambda _: {},
# Rautatie (tallennettu alaluokkiin)
14110 : mtk_railway,
# Rautatie, sähköistetty
14111 : mtk_railway,
# Rautatie, sähköistämätön
14112 : mtk_railway,
# Kapearaiteinen rautatie
14121 : lambda f: dict(mtk_railway(f).items() + {"railway" : "narrow_gauge"}.items()),
# Metro
14131 : lambda f: dict(mtk_railway(f).items() + {"railway" : "subway"}.items()),
## 'Selite' points are not imported
# Kulkuväylän selite
12302 : lambda _: {},
# Turvalaitteen selite
16102 : lambda _: {},
# Vedenottamon selite
26202 : lambda _: {},
# Maa-aineksenottoalueen selite
32102 : lambda _: {},
# Hautausmaan selite
32202 : lambda _: {},
# Kaatopaikan selite
32302 : lambda _: {},
# Liikennealueen selite
32402 : lambda f: { "aeroway" : "helipad", } if re.match('Helikopter.*', ustr(f['teksti'])) else {},
# Louhoksen selite
32502 : lambda _: {},
# Maatalousmaan selite
32602 : lambda _: {},
# Puiston selite
32902 : lambda _: {},
# Täytemaan selite
33002 : lambda _: {},
# Urheilu- ja virkistysalueen selite
33102 : lambda _: {},
# Merkittävän luontokohteen selite
34902 : lambda _: {},
# Puun selite
35102 : lambda _: {},
# Muun maastokohteen selite
36500 : lambda _: {},
# Varastoalueen selite
38902 : lambda _: {},
# Metsän rajan selite
39502 : lambda _: {},
# Rakennuksen selite
42102 : lambda f: { "tourism" : "hotel", } if re.match('Hot.*', ustr(f['teksti'])) else {},
# Rakennusryhmän selite
42202 : lambda _: {},
# Aidan selite
44202 : lambda _: {},
# Altaan selite
44302 : lambda _: {},
# Ilmaradan selite
44402 : lambda _: {},
# Muistomerkin selite
44902 : lambda _: {},
# Näkötornin selite
45002 : lambda _: {},
# Tervahaudan selite
45402 : lambda _: {},
# Tuulimoottorin selite
45502 : lambda _: {},
# Rakennelman selite
45702 : lambda _: {},
# Vesitornin selite
45802 : lambda _: {},
# Sotilasalueen selite
62102 : lambda _: {},
# Suoja-alueen selite
62202 : lambda _: {},
# Luonnonsuojelualueen selite
#72202 : lambda _: {}, # Same class as Kansallispuisto (!)
# Luonnonmuistomerkin selite
72304 : lambda _: {},
# Muinaisjäännöksen selite
72404 : lambda _: {},
# Suojametsän selite
72501 : lambda _: {},
# Kansallispuiston selite
72603 : lambda _: {},
# Luonnonpuiston selite
72604 : lambda _: {},
# Erämaa-alueen selite
72702 : lambda _: {},
# Retkeilyalueen selite
72802 : lambda _: {},
# Aluemeren ulkorajan selite
82102 : lambda _: {},
# Rajavyöhykkeen takarajan selite
82202 : lambda _: {},
# Sisäisten aluevesien ulkorajan selite
82302 : lambda _: {},
# Ulko- ja sisäsaariston rajan selite
82402 : lambda _: {},
# Kunnan hallintorajan selite
85100 : lambda _: {},
# Vesiasteikon selite
95302 : lambda _: {},
## 'Selite' points end
# Luonnonsuojelualue
72200 : lambda _: { "boundary" : "protected_area", "protection_title" : "luonnonsuojelualue", "protect_class" : "4", },
# Luonnonpuisto
72201 : lambda _: { "boundary" : "protected_area", "protection_title" : "luonnonpuisto", "related_law" : "Luonnonsuojelulaki", "protect_class" : "1", },
# Kansallispuisto
72202 : lambda _: { "boundary" : "national_park", },
# Retkeilyalue
72800 : lambda _: { "boundary" : "protected_area", "protection_title" : "retkeilyalue", "related_law" : "Ulkoilulaki", "protect_class" : "6" },
# Suojametsä
72500 : lambda _: { "boundary" : "protected_area", "protection_title" : "suojametsä", "related_law" : "Kuntalaki", "protect_class" : "15" },
# Rauhoitettu kivi
72310 : lambda _: { "natural" : "stone", },
# Rauhoitettu puu
72320 : lambda _: { "natural" : "tree", },
# Muu rauhoitettu kohde
72340 : lambda _: {},
# Muinaisjäännös
72330 : lambda _: { "historic" : "archaeological_site", "fixme" : "castle/fort/memorial/ruins?", },
## Features Below are lines and do not map well to OSM data types
# Erämaa-alue
72700 : lambda _: {}, # "boundary" : "protected_area", "protect_class" : "1b" },
# Rauhoitettu kivi
72410 : lambda _: {},
# Rauhoitettu puu
72420 : lambda _: {},
# Muu rauhoitettu kohde
72440 : lambda _: {},
# Muinaisjäännös
74330 : lambda _: {}, # "historic" : "archaeological_site", "area" : "yes", "fixme" : "castle/fort/memorial/ruins?", },
# Suojelualueen reunaviiva
72000 : lambda _: {},
# Suojelukohteet tekninen viiva
30999 : lambda _: {},
# Taajaan rakennettu alue
40200 : lambda _: {},
# Taajaan rakennetun alueen reunaviiva
40100 : lambda _: {},
## Lines end
# Lauttasymboli
12192 : lambda _: {},
# Lossisymboli
12193 : lambda _: {},
# Esterakennelma
12200 : lambda _: {},
# Kevytväylän alikulkusymboli
12391 : lambda _: {},
# Kulkukorkeusrajoitteen korkeus
10111 : lambda f: { "maxheight" : ustr(f['teksti']), },
# Autotien siltanumero
12105 : lambda _: {},
# Autotien lauttanumero
12106 : lambda _: {},
# Paikallistien numero
12181 : lambda _: {},
# Maantien numero
12182 : lambda _: {},
# E- valta- tai kantatien numero
12183 : lambda _: {},
# Ankkuripaikka
16600 : lambda _: { "seamark:type" : "anchorage", },
# Hylky, luokittelematon
16700 : lambda _: { "historic" : "wreck", "seamark:type" : "wreck", },
# Hylky, pinnalla
16712 : lambda _: { "historic" : "wreck", "seamark:type" : "wreck", "seamark:category" : "hull_visible", },
# Hylky, syvyys tuntematon
16721 : lambda _: { "historic" : "wreck", "seamark:type" : "wreck", },
# Hylky, syvyys tunnettu
16722 : lambda _: { "historic" : "wreck", "seamark:type" : "wreck", },
# Linjamerkki
#16120 : lambda _: { "seamark:type" : "navigation_line", "seamark:navigation_line:category" : "leading_line" ??? }
# Kummeli
16121 : lambda _: { "seamark:type" : "beacon_special_purpose", "seamark:beacon_special_purpose:shape" : "cairn", },
# Tunnusmajakka
16122 : lambda _: { "man_made" : "lighthouse", },
# Loisto
16124 : lambda _: { "seamark:type" : "light_minor" },
# Linjaloisto
16125 : lambda _: { "seamark:type" : "light_minor" },
# Merimajakka
16126 : lambda _: { "man_made" : "lighthouse", "seamark:type" : "landmark", "seamark:category" : "tower", },
# Merimerkki, vasen
16141 : lambda _: { "seamark:type" : "buoy_lateral", "seamark:buoy_lateral:colour" : "red", },
# Merimerkki, oikea
16142 : lambda _: { "seamark:type" : "buoy_lateral", "seamark:buoy_lateral:colour" : "green", },
# Merimerkki, pohjoinen
16143 : lambda _: { "seamark:type" : "buoy_cardinal", "seamark:buoy_cardinal:colour" : "black;yellow" },
# Merimerkki, etelä
16144 : lambda _: { "seamark:type" : "buoy_cardinal", "seamark:buoy_cardinal:colour" : "yellow;black" },
# Merimerkki, itä
16145 : lambda _: { "seamark:type" : "buoy_cardinal", "seamark:buoy_cardinal:colour" : "black;yellow;black" },
# Merimerkki, länsi
16146 : lambda _: { "seamark:type" : "buoy_cardinal", "seamark:buoy_cardinal:colour" : "yellow;black;yellow" },
# Merimerkki, kari
16147 : lambda _: { "seamark:type" : "buoy_isolated_danger", "seamark:buoy_isolated_danger:colour" : "black;red;black" },
# Merimerkki, turvavesi
16148 : lambda _: { "seamark:type" : "buoy_safe_water", "seamark:buoy_safe_water:colour_pattern" : "vertical", "seamark:buoy_safe_water:colour" : "red;white" },
# Merimerkki, erikoismerkki
16149 : lambda _: { "seamark:type" : "buoy_special_purpose" },
# Viittapoiju, vasen
16151 : lambda _: { "seamark:type" : "buoy_lateral", "seamark:buoy_lateral:colour" : "red", },
# Viittapoiju, oikea
16152 : lambda _: { "seamark:type" : "buoy_lateral", "seamark:buoy_lateral:colour" : "green", },
# Viittapoiju, pohjoinen
16153 : lambda _: { "seamark:type" : "buoy_cardinal", "seamark:buoy_cardinal:colour" : "black;yellow" },
# Viittapoiju, etelä
16154 : lambda _: { "seamark:type" : "buoy_cardinal", "seamark:buoy_cardinal:colour" : "yellow;black" },
# Viittapoiju, itä
16155 : lambda _: { "seamark:type" : "buoy_cardinal", "seamark:buoy_cardinal:colour" : "black;yellow;black" },
# Viittapoiju, länsi
16156 : lambda _: { "seamark:type" : "buoy_cardinal", "seamark:buoy_cardinal:colour" : "yellow;black;yellow" },
# Viittapoiju, kari
16157 : lambda _: { "seamark:type" : "buoy_isolated_danger", "seamark:buoy_isolated_danger:colour" : "black;red;black" },
# Viittapoiju, turvavesi
16158 : lambda _: { "seamark:type" : "buoy_safe_water", "seamark:buoy_safe_water:colour_pattern" : "vertical", "seamark:buoy_safe_water:colour" : "red;white" },
# Viittapoiju, erikoismerkki
16159 : lambda _: { "seamark:type" : "buoy_special_purpose" },
# Hylyn syvyys
16703 : lambda f: { "depth" : ustr(f['teksti']), },
# Kulkusyvyys (2.2mm teksti) # FIXME: depth=x ?
16503 : lambda _: {},
# Kulkusyvyys (1.8mm teksti)
16504 : lambda _: {},
# Alikulkukorkeus
16508 : lambda _: {},
# Laivaväylä
16511 : lambda _: { "seamark:type" : "recommended_track", },
# Venereitti
16512 : lambda _: { "seamark:type" : "recommended_track", },
}

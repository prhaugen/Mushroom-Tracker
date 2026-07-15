"""
One-shot script: adds grow_guide_url column to species_db,
populates it with out-grow.com How-to-Grow links for all matched species,
and inserts gap species that out-grow.com covers but the DB doesn't.
"""

import sqlite3

BASE = "https://out-grow.com"

# Map common_name → how-to-grow URL path (applied to ALL rows sharing that name)
COMMON_NAME_URLS = {
    "Abalone":                    "/pages/how-to-grow-abalone-mushroom-pleurotus-cystidiosus",
    "Agarikon":                   "/pages/how-to-grow-agarikon-fomitopsis-officinalis",
    "Almond Mushroom":            "/pages/how-to-grow-almond-agaricus-agaricus-subrufescens",
    "Amber Jelly Fungus":         "/pages/how-to-grow-amber-jelly-roll-exidia-crenata",
    "Amber Nam":                  "/pages/how-to-grow-nameko-mushrooms-pholiota-nameko",
    "Antler Reishi":              "/pages/how-to-grow-antler-reishi-ganoderma-multipileum",
    "Artist's Conk":              "/pages/how-to-grow-artists-conk-ganoderma-applanatum",
    "Aspen Oyster":               "/pages/how-to-grow-aspen-oyster-mushrooms-pleurotus-populinus",
    "Australian Black Morel":     "/pages/how-to-grow-morchella-australiana",
    "Bear's Head":                "/pages/how-to-grow-bears-head-tooth-mushroom-hericium-americanum",
    "Beech Wild Strain":          "/pages/how-to-grow-shimeji-mushroom-hypsizygus-tessellatus",
    "Beef Steak":                 "/pages/how-to-grow-beefsteak-fungus-fistulina-hepatica",
    "Berkeley's Polypore":        "/pages/how-to-grow-berkeleys-polypore-bondarzewia-berkeleyi",
    "Big White Beech Wild Strain":"/pages/how-to-grow-white-beech-mushroom-hypsizygus-tessellatus",
    "Birch Polypore":             "/pages/how-to-grow-birch-polypore-fomitopsis-betulina",
    "Bitter Oyster":              "/pages/how-to-grow-panellus-stipticus",
    "Black Fungus":               "/pages/how-to-grow-black-fungus-annulohypoxylon-archeri",
    "Black Hoof Mushroom":        "/pages/how-to-grow-phellinus-linteus-phellinus-linteus",
    "Black Morel":                "/pages/how-to-grow-black-morel-mushrooms-morchella-angusticeps",
    "Black Pearl King Oyster":    "/pages/how-to-grow-king-oyster-mushrooms-pleurotus-eryngii",
    "Black Poplar":               "/pages/how-to-grow-pioppino-mushrooms-agrocybe-aegerita",
    "Black Reishi":               "/pages/how-to-grow-black-reishi-ganoderma-sinense",
    "Black Staining Polypore":    "/pages/how-to-grow-black-staining-polypore-meripilus-sumstinei",
    "Blistered Morel":            "/pages/how-to-grow-morchella-steppicola",
    "Blue Brat Oyster":           "/pages/how-to-grow-brat-oyster-mushrooms-pleurotus-ostreatus",
    "Blue Chanterelle":           "/pages/blue-chanterelle-polyozellus-multiplex",
    "Blue Oyster":                "/pages/how-to-grow-blue-oyster-mushrooms-pleurotus-columbinus",
    "Blushing Bracket":           "/pages/how-to-grow-blushing-bracket-daedaleopsis-confragosa",
    "Blushing Morel":             "/pages/how-to-grow-california-landscaping-morel-morchella-rufobrunnea",
    "Bolles Bear's Head":         "/pages/how-to-grow-bears-head-mushroom-hericium-abietis",
    "Branched Oyster":            "/pages/how-to-grow-branched-oyster-mushroom-pleurotus-cornucopiae",
    "Brick Cap":                  "/pages/how-to-grow-cinnamon-cap-mushroom-hypholoma-sublateritium",
    "Brown Beech Shimeji":        "/pages/how-to-grow-shimeji-mushroom-hypsizygus-tessellatus",
    "Bulbous Honey Mushroom":     "/pages/how-to-grow-bulbous-honey-mushroom-armillaria-gallica",
    "Burnt Morel":                "/pages/how-to-grow-morchella-eximia",
    "Cauliflower Mushroom":       "/pages/how-to-grow-cauliflower-mushroom-sparassis-crispa",
    "Chaga":                      "/pages/how-to-grow-chaga-mushroom-inonotus-obliquus",
    "Champignon":                 "/pages/how-to-grow-button-mushrooms-agaricus-bisporus",
    "Chestnut Mushroom":          "/pages/how-to-grow-chestnut-mushrooms-pholiota-adiposa",
    "Chicken Of The Woods":       "/pages/how-to-grow-chicken-of-the-woods-laetiporus-sulphureus",
    "Chicken Of The Woods White Pored": "/pages/how-to-grow-chicken-of-the-woods-laetiporus-cincinnatus",
    "Common Stinkhorn":           "/pages/how-to-grow-common-stinkhorn-phallus-impudicus",
    "Conifer Tuft":               "/pages/how-to-grow-conifer-tuft-mushroom-hypholoma-capnoides",
    "Coral Tooth":                "/pages/how-to-grow-coral-tooth-mushroom-hericium-coralloides",
    "Cordyceps Militaris":        "/pages/how-to-grow-cordyceps-militaris-cordyceps-militaris",
    "Corn Smut":                  "/pages/how-to-grow-huitlacoche-ustilago-maydis",
    "Dancing Hens":               "/pages/how-to-grow-maitake-mushrooms-grifola-frondosa",
    "Deer Mushroom":              "/pages/how-to-grow-deer-mushroom-pluteus-cervinus",
    "Enoki Golden":               "/pages/how-to-grow-gold-enoki-mushrooms-flammulina-velutipes",
    "Enoki White":                "/pages/how-to-grow-white-enoki-mushrooms-flammulina-velutipes",
    "Enoki Wild Strain":          "/pages/how-to-grow-enoki-mushrooms-flammulina-velutipes",
    "Fire Morel":                 "/pages/how-to-grow-morchella-exuberans",
    "Florida Oyster":             "/pages/how-to-grow-florida-oyster-mushroom-pleurotus-ostreatus-var-florida",
    "Fluted Bird's Nest":         "/pages/how-to-grow-fluted-birds-nest-cyathus-striatus",
    "Garlic Scented Mushroom":    "/pages/how-to-grow-garlic-scented-mushroom-mycetinis-scorodonius",
    "Ghost Fungus":               "/pages/how-to-grow-ghost-fungus-omphalotus-nidiformis",
    "Giant Puffball":             "/pages/how-to-grow-giant-puffball-mushrooms-calvatia-gigantea",
    "Golden Oyster":              "/pages/how-to-grow-golden-oyster-mushroom-pleurotus-citrinopileatus",
    "Golden Oyster Wild Strain":  "/pages/how-to-grow-golden-oyster-mushroom-pleurotus-citrinopileatus",
    "Green Elfcup Fungus":        "/pages/how-to-grow-green-elfcup-chlorociboria-aeruginascens",
    "Grey Dove Oyster":           "/pages/how-to-grow-grey-oyster-mushrooms-pleurotus-ostreatus",
    "Grey Oyster":                "/pages/how-to-grow-grey-oyster-mushrooms-pleurotus-ostreatus",
    "Half Free Morel":            "/pages/how-to-grow-half-free-morel-morchella-punctipes",
    "Hed Khon Khao White Shiitake": "/pages/how-to-grow-lentinus-squarrosulus-lentinus-squarrosulus",
    "Hemlock Reishi":             "/pages/how-to-grow-hemlock-reishi-ganoderma-tsugae",
    "Honey Mushroom":             "/pages/how-to-grow-honey-mushrooms-armillaria-mellea",
    "Horse Mushroom":             "/pages/how-to-grow-horse-mushroom-agaricus-arvensis",
    "Indian Oyster":              "/pages/how-to-grow-pleurotus-sajor-caju",
    "Italian Oyster":             "/pages/how-to-grow-phoenix-oyster-mushroom-pleurotus-pulmonarius",
    "Ivory Shimeji":              "/pages/how-to-grow-shimeji-mushroom-hypsizygus-tessellatus",
    "Jack O Lantern Mushroom":    "/pages/how-to-grow-jack-o-lantern-mushroom-omphalotus-olearius",
    "King Blue Oysters":          "/pages/how-to-grow-blue-oyster-mushrooms-pleurotus-columbinus",
    "King Oyster":                "/pages/how-to-grow-king-oyster-mushrooms-pleurotus-eryngii",
    "King Trumpet Oyster":        "/pages/how-to-grow-king-oyster-mushrooms-pleurotus-eryngii",
    "King Tuber Oyster":          "/pages/how-to-grow-pleurotus-tuber-regium",
    "Late Oyster":                "/pages/how-to-grow-olive-oysterling-panellus-serotinus",
    "Lingzhi Reishi":             "/pages/how-to-grow-reishi-mushrooms-ganoderma-lucidum",
    "Lion's Mane":                "/pages/how-to-grow-lions-mane-mushrooms-hericium-erinaceus",
    "Lion's Mane Heat Tolerant":  "/pages/how-to-grow-lions-mane-warm-weather-hericium-erinaceus",
    "Macrocybe titans":           "/pages/how-to-grow-macrocybe-titans-macrocybe-titans",
    "Maine Oyster 2019":          "/pages/how-to-grow-pearl-oyster-mushroom-pleurotus-ostreatus",
    "Maine Wild Oyster":          "/pages/how-to-grow-grey-oyster-mushrooms-pleurotus-ostreatus",
    "Maitake":                    "/pages/how-to-grow-maitake-mushrooms-grifola-frondosa",
    "Milky Mushroom":             "/pages/how-to-grow-milky-mushroom-calocybe-indica",
    "Nameko":                     "/pages/how-to-grow-nameko-mushrooms-pholiota-nameko",
    "Natural Morel":              "/pages/how-to-grow-morchella-snyderi",
    "New Zealand's Bush Shiitake":"/pages/how-to-grow-new-zealand-shiitake-lentinula-novae-zelandiae",
    "North American Morel":       "/pages/how-to-grow-morchella-sceptriformis",
    "Paddy Straw":                "/pages/how-to-grow-paddy-straw-mushroom-volvariella-volvacea",
    "Pear Shaped Puffball":       "/pages/how-to-grow-pear-shaped-puffball-apioperdon-pyriforme",
    "Pearl Oyster":               "/pages/how-to-grow-pearl-oyster-mushroom-pleurotus-ostreatus",
    "Pheasant Back":              "/pages/how-to-grow-pheasant-back-mushrooms-polyporus-squamosus",
    "Phoenix Oyster":             "/pages/how-to-grow-phoenix-oyster-mushroom-pleurotus-pulmonarius",
    "Pink Oyster":                "/pages/how-to-grow-pink-oyster-mushrooms-pleurotus-djamor",
    "Portobello":                 "/pages/how-to-grow-portobello-mushrooms-agaricus-bisporus",
    "Purple Morel":               "/pages/how-to-grow-purple-morel-morchella-purpurascens",
    "Red Reishi":                 "/pages/how-to-grow-red-reishi-mushroom-ganoderma-resinaceum",
    "Reishi":                     "/pages/how-to-grow-reishi-mushrooms-ganoderma-lucidum",
    "Sajor Caju Oyster":          "/pages/how-to-grow-pleurotus-sajor-caju",
    "Shaggy Mane":                "/pages/how-to-grow-shaggy-mane-mushrooms-coprinus-comatus",
    "Shiitake":                   "/pages/how-to-grow-shiitake-bag-cultivation-lentinula-edodes",
    "Shiitake 0557":              "/pages/how-to-grow-shiitake-bag-cultivation-lentinula-edodes",
    "Shiitake 5000":              "/pages/how-to-grow-shiitake-wr-55-85f-lentinula-edodes",
    "Shiitake 7869":              "/pages/how-to-grow-shiitake-wr-50-75f-mushrooms-lentinula-edodes",
    "Shimeji":                    "/pages/how-to-grow-shimeji-mushroom-hypsizygus-tessellatus",
    "Sky Blue Oyster":            "/pages/how-to-grow-blue-oyster-mushrooms-pleurotus-columbinus",
    "Snow Fungus":                "/pages/how-to-grow-snow-fungus-tremella-fuciformis",
    "Sordid Blewit Bleu Foot":    "/pages/how-to-grow-blue-foot-mushroom-clitocybe-sordida",
    "Split Gill":                 "/pages/how-to-grow-split-gill-mushroom-schizophyllum-commune",
    "Straw Shiitake":             "/pages/how-to-grow-shiitake-bag-cultivation-lentinula-edodes",
    "Sweet Knot Polypore":        "/pages/how-to-grow-sweet-knot-mushroom-globifomes-graveolens",
    "Tarragon Oyster":            "/pages/how-to-grow-tarragon-oyster-mushroom-pleurotus-eunosmus",
    "Termite Mushroom":           "/pages/how-to-grow-termite-mushroom-termitomyces-albuminosus",
    "The Gilled Polypore":        "/pages/how-to-grow-gilled-polypore-lenzites-betulina",
    "The Prince":                 "/pages/how-to-grow-the-prince-agaricus-augustus",
    "Tiger Milk Mushroom":        "/pages/how-to-grow-tiger-milk-mushroom-lignosus-rhinocerus",
    "Tiger Sawgill":              "/pages/how-to-grow-tiger-sawgill-lentinus-tigrinus",
    "Train Wrecker":              "/pages/how-to-grow-train-wrecker-mushroom-neolentinus-lepideus",
    "Tree Oyster":                "/pages/how-to-grow-pearl-oyster-mushroom-pleurotus-ostreatus",
    "True Morel":                 "/pages/how-to-grow-morchella-laurentiana",
    "Turkey Tail":                "/pages/how-to-grow-turkey-tail-mushrooms-trametes-versicolor",
    "Turkey Tail Wild Strain":    "/pages/how-to-grow-turkey-tail-mushrooms-trametes-versicolor",
    "Umbrella Polypore":          "/pages/how-to-grow-polyporus-umbellatus",
    "Veiled Oyster":              "/pages/how-to-grow-veiled-oyster-mushroom-pleurotus-dryinus",
    "Velvet Pioppino":            "/pages/how-to-grow-pioppino-mushrooms-agrocybe-aegerita",
    "White Beech Shimeji":        "/pages/how-to-grow-white-beech-mushroom-hypsizygus-tessellatus",
    "White Button":               "/pages/how-to-grow-button-mushrooms-agaricus-bisporus",
    "White Elm Mushroom":         "/pages/how-to-grow-elm-oyster-mushrooms-hypsizygus-ulmarius",
    "White Elm Oyster Hypsizygus":"/pages/how-to-grow-elm-oyster-mushrooms-hypsizygus-ulmarius",
    "White Ferula":               "/pages/how-to-grow-ferulae-mushroom-pleurotus-ferulae",
    "White Morel":                "/pages/how-to-grow-white-morel-mushrooms-morchella-deliciosa",
    "Wine Cap":                   "/pages/how-to-grow-wine-cap-mushrooms-stropharia-rugosoannulata",
    "Wine Cap Golden":            "/pages/how-to-grow-golden-wine-cap-mushroom-stropharia-rugosoannulata-var-lutea",
    "Wood Blewit":                "/pages/how-to-grow-blewit-mushrooms-lepista-nuda",
    "Woodear":                    "/pages/how-to-grow-wood-ear-mushrooms-auricularia-auricula-judae",
    "Woodtuft":                   "/pages/how-to-grow-sheathed-woodtuft-kuehneromyces-mutabilis",
    "Yellow Morel":               "/pages/how-to-grow-yellow-morel-mushrooms-morchella-esculenta",
    "Yellow Reishi":              "/pages/how-to-grow-yellow-reishi-ganoderma-curtisii",
}

# Per-id overrides for rows where scientific name determines a more specific URL
ID_OVERRIDES = {
    # Black Morel rows by scientific name
    23: "/pages/how-to-grow-morel-mushrooms-morchella-brunnea",          # Morchella brunnea
    25: "/pages/how-to-grow-morel-mushrooms-morchella-importuna",        # Morchella importuna
    26: "/pages/how-to-grow-morchella-mel-8",                            # Morchella mel
    # Yellow Morel — row 204 is M. esculenta (correct), row 203 is M. diminutiva (no guide)
    # Half Free Morel — punctipes URL is already in common-name map above
}

# Gap species to INSERT (not already in species_db)
GAP_SPECIES = [
    ("Saffron Milk Cap",         "Lactarius deliciosus",      "/pages/how-to-grow-saffron-milk-cap-lactarius-deliciosus"),
    ("Ringless Honey Mushroom",  "Desarmillaria caespitosa",  "/pages/how-to-grow-ringless-honey-mushrooms-desarmillaria-caespitosa"),
    ("Fried Chicken Mushroom",   "Lyophyllum decastes",       "/pages/how-to-grow-fried-chicken-mushroom-lyophyllum-decastes"),
    ("Brain Puffball",           "Calvatia craniiformis",     "/pages/how-to-grow-brain-puffball-mushroom-calvatia-craniiformis"),
    ("Gem Studded Puffball",     "Lycoperdon perlatum",       "/pages/how-to-grow-gem-studded-puffball-lycoperdon-perlatum"),
    ("Australian Shiitake",      "Lentinula lateritia",       "/pages/how-to-grow-australian-shiitake-lentinula-lateritia"),
    ("Field Blewit",             "Lepista personata",         "/pages/how-to-grow-field-blewit-mushroom-lepista-personata"),
    ("Spring Fieldcap",          "Agrocybe praecox",          "/pages/how-to-grow-agrocybe-praecox-spring-fieldcap"),
    ("Red Belted Polypore",      "Fomitopsis pinicola",       "/pages/how-to-grow-red-belted-polypore-fomitopsis-pinicola"),
    ("Sidewalk Mushroom",        "Agaricus bitorquis",        "/pages/how-to-grow-sidewalk-mushroom-agaricus-bitorquis"),
    ("Snowy Wood Mushroom",      "Agaricus excellens",        "/pages/how-to-grow-snowy-wood-mushroom-agaricus-excellens"),
    ("Salt Loving Mushroom",     "Agaricus bernardii",        "/pages/how-to-grow-salt-loving-mushroom-agaricus-bernardii"),
    ("Light Filament",           "Panellus luxfilamentus",    "/pages/how-to-grow-light-filament-panellus-luxfilamentus"),
    ("Neonothopanus nambi",      "Neonothopanus nambi",       "/pages/how-to-grow-neonothopanus-nambi"),
    ("Lentinula boryana",        "Lentinula boryana",         "/pages/how-to-grow-lentinula-boryana"),
    ("Lentinula aciculospora",   "Lentinula aciculospora",    "/pages/how-to-grow-lentinula-aciculospora"),
    ("Fu Ling",                  "Poria cocos",               "/pages/how-to-grow-fu-ling-poria-cocos"),
    ("Black Truffle",            "Tuber melanosporum",        "/pages/how-to-grow-black-truffle-tuber-melanosporum"),
    ("Orange Peel Fungus",       "Aleuria aurantia",          "/pages/how-to-grow-orange-peel-fungus-aleuria-aurantia"),
    ("Poplar Oyster",            "Pleurotus calyptratus",     "/pages/how-to-grow-poplar-oyster-mushroom-pleurotus-calyptratus"),
    ("Giant Sawgill",            "Neolentinus ponderosus",    "/pages/how-to-grow-giant-sawgill-mushroom-neolentinus-ponderosus"),
    ("Orange Mock Oyster",       "Phyllotopsis nidulans",     "/pages/how-to-grow-orange-mock-oyster-phyllotopsis-nidulans"),
]


def run():
    conn = sqlite3.connect("mushroom_data.db")
    conn.row_factory = sqlite3.Row

    # 1. Add column if missing
    cols = [c["name"] for c in conn.execute("PRAGMA table_info(species_db)")]
    if "grow_guide_url" not in cols:
        conn.execute("ALTER TABLE species_db ADD COLUMN grow_guide_url TEXT")
        print("Added grow_guide_url column.")

    # 2. Update by common_name
    updated_names = 0
    for common_name, path in COMMON_NAME_URLS.items():
        url = BASE + path
        cur = conn.execute(
            "UPDATE species_db SET grow_guide_url = ? WHERE common_name = ?",
            (url, common_name)
        )
        updated_names += cur.rowcount
    print(f"Updated {updated_names} rows via common_name map.")

    # 3. Per-id overrides
    for row_id, path in ID_OVERRIDES.items():
        url = BASE + path
        conn.execute("UPDATE species_db SET grow_guide_url = ? WHERE id = ?", (url, row_id))
    print(f"Applied {len(ID_OVERRIDES)} per-id overrides.")

    # 4. Insert gap species (skip if common_name + scientific_name already exists)
    inserted = 0
    for common_name, sci_name, path in GAP_SPECIES:
        exists = conn.execute(
            "SELECT 1 FROM species_db WHERE common_name = ? AND scientific_name = ?",
            (common_name, sci_name)
        ).fetchone()
        if not exists:
            url = BASE + path
            conn.execute(
                "INSERT INTO species_db (common_name, scientific_name, grow_guide_url) VALUES (?, ?, ?)",
                (common_name, sci_name, url)
            )
            inserted += 1
    print(f"Inserted {inserted} new gap species.")

    conn.commit()

    # 5. Report
    total       = conn.execute("SELECT COUNT(*) FROM species_db").fetchone()[0]
    matched     = conn.execute("SELECT COUNT(*) FROM species_db WHERE grow_guide_url IS NOT NULL").fetchone()[0]
    unmatched   = conn.execute("SELECT COUNT(*) FROM species_db WHERE grow_guide_url IS NULL").fetchone()[0]
    print(f"\nSummary: {total} total rows | {matched} with URL | {unmatched} without URL")

    if unmatched:
        print("\nRows without a grow guide URL:")
        rows = conn.execute(
            "SELECT common_name, scientific_name FROM species_db WHERE grow_guide_url IS NULL ORDER BY common_name"
        ).fetchall()
        for r in rows:
            print(f"  {r['common_name']} ({r['scientific_name']})")

    conn.close()


if __name__ == "__main__":
    run()

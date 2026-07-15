"""
One-shot script: add species present on out-grow.com that are absent from species_db.
Run once, keep for reference.
"""
import sqlite3

DB = "mushroom_data.db"
BASE = "https://out-grow.com"

NEW_SPECIES = [
    # (common_name, scientific_name, url_path)
    ("Aniseed Toadstool",       "Clitocybe odora",           "/pages/how-to-grow-aniseed-toadstool-clitocybe-odora"),
    ("Apricot Jelly Mushroom",  "Guepinia helvelloides",     "/pages/how-to-grow-apricot-jelly-mushroom-guepinia-helvelloides"),
    ("Bleach Cup",              "Disciotis venosa",           "/pages/how-to-grow-bleach-cup-disciotis-venosa"),
    ("Bleeding Bonnet",         "Mycena sanguinolenta",       "/pages/how-to-grow-bleeding-bonnet-mycena-sanguinolenta"),
    ("Bovista Puffball",        "Bovista plumbea",            "/pages/how-to-grow-bovista-plumbea"),
    ("Brazen Bracket",          "Ganoderma chalceum",         "/pages/how-to-grow-brazen-bracket-ganoderma-chalceum"),
    ("Cinnabar Polypore",       "Trametes sanguineus",        "/pages/how-to-grow-cinnabar-polypore-trametes-sanguineus"),
    ("Common Funnel",           "Clitocybe gibba",            "/pages/how-to-grow-common-funnel-clitocybe-gibba"),
    ("Cookeina",                "Cookeina sulcipes",          "/pages/how-to-grow-cookeina-sulcipes"),
    ("Desert Shaggy Mane",      "Podaxis pistillaris",        "/pages/how-to-grow-desert-shaggy-mane-podaxis-pistillaris"),
    ("Earliella",               "Earliella scabrosa",         "/pages/how-to-grow-earliella-scabrosa"),
    ("Elegant Bracket",         "Trametes elegans",           "/pages/how-to-grow-elegant-bracket-trametes-elegans"),
    ("Fan-Shaped Jelly Fungus", "Dacryopinax spathularia",   "/pages/how-to-grow-fan-shaped-jelly-fungus-dacryopinax-spathularia"),
    ("Fee's Polypore",          "Fomitopsis feei",            "/pages/how-to-grow-fees-polypore-fomitopsis-feei"),
    ("Ganoderma megaloma",      "Ganoderma megaloma",         "/pages/how-to-grow-ganoderma-megaloma"),
    ("Ganoderma tropicum",      "Ganoderma tropicum",         "/pages/how-to-grow-ganoderma-tropicum"),
    ("Macrocybe crassa",        "Macrocybe crassa",           "/pages/how-to-grow-macrocybe-crassa"),
    ("Mycena chlorophos",       "Mycena chlorophos",          "/pages/how-to-grow-mycena-chlorophos"),
    ("Mycena coralliformis",    "Mycena coralliformis",       "/pages/how-to-grow-mycena-coralliformis"),
    ("Mycena deeptha",          "Mycena deeptha",             "/pages/how-to-grow-mycena-deeptha"),
    ("Mycena noctilucens",      "Mycena noctilucens",         "/pages/how-to-grow-mycena-noctilucens"),
    ("Ornament Polypore",       "Amauroderma rugosum",        "/pages/how-to-grow-ornament-polypore-amauroderma-rugosum"),
    ("Parasol Mushroom",        "Macrolepiota procera",       "/pages/how-to-grow-parasol-mushroom-amerilepiota-procera"),
    ("Pearl Sawgill",           "Lentinus concavus",          "/pages/how-to-grow-pearl-sawgill-mushroom-lentinus-concavus"),
    ("Pleurotus geesteranus",   "Pleurotus geesteranus",      "/pages/how-to-grow-pleurotus-geesteranus"),
    ("Swollen Bracket",         "Ganoderma gibbosum",         "/pages/how-to-grow-swollen-bracket-ganoderma-gibbosum"),
    ("Trichaleurina",           "Trichaleurina javanica",     "/pages/how-to-grow-trichaleurina-javanica"),
    ("Willow Bracket",          "Phellinus igniarius",        "/pages/how-to-grow-willow-bracket-phellinus-igniarius"),
    ("Yellow Stemmed Micropore","Microporus xanthopus",       "/pages/how-to-grow-yellow-stemmed-micropore-microporus-xanthopus"),
]

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
c = conn.cursor()

existing_sci = {
    r[0].lower()
    for r in c.execute("SELECT scientific_name FROM species_db WHERE scientific_name IS NOT NULL")
}
existing_common = {
    r[0].lower()
    for r in c.execute("SELECT common_name FROM species_db")
}

added = []
skipped = []

for common, sci, path in NEW_SPECIES:
    if sci.lower() in existing_sci or common.lower() in existing_common:
        skipped.append(f"SKIP (already exists): {common} ({sci})")
        continue
    url = BASE + path
    c.execute(
        "INSERT INTO species_db (common_name, scientific_name, grow_guide_url) VALUES (?, ?, ?)",
        (common, sci, url)
    )
    added.append(f"  + {common} ({sci})")

conn.commit()
conn.close()

print(f"Added {len(added)} species:")
for a in added:
    print(a)
if skipped:
    print(f"\nSkipped {len(skipped)} (already in db):")
    for s in skipped:
        print(f"  {s}")

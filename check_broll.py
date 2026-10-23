from app.broll_selector import select_broll

scenes = [
    {"search_terms": ["artificial intelligence transforming"]},
    {"search_terms": ["detect diseases doctors"]},
]

for result in select_broll(scenes):
    print(
        "Scene:", result["scene_index"],
        "| Status:", result["status"],
        "| Clip:", result["clip_path"],
        "| Licence verified:", result["license_verified"],
    )

#!/usr/bin/env python3
"""Download CC0 SFX from OpenGameArt + Kenney (gamesounds.xyz) and build sfx/catalog.yaml."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import urllib.parse
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SFX = ROOT / "sfx"

OGA = "https://opengameart.org/sites/default/files"
KENNEY = "https://gamesounds.xyz/Kenney%27s%20Sound%20Pack"


def k(path: str) -> str:
    encoded = urllib.parse.quote(path, safe="/")
    return f"{KENNEY}/{encoded}"


# sound_id -> catalog metadata (file path relative to sfx/, tags, volumes)
CATALOG: dict[str, dict] = {
    "rain_light": {"file": "ambient/rain_light.mp3", "tags": ["rain", "weather", "melancholy", "ambient"], "default_volume": 0.08, "volume_range": [0.04, 0.14]},
    "rain_heavy": {"file": "ambient/rain_heavy.mp3", "tags": ["rain", "storm", "dramatic", "tension"], "default_volume": 0.10, "volume_range": [0.06, 0.16]},
    "rain_01": {"file": "ambient/rain_01.mp3", "tags": ["rain", "weather", "ambient", "soft"], "default_volume": 0.07, "volume_range": [0.04, 0.12]},
    "rain_02": {"file": "ambient/rain_02.mp3", "tags": ["rain", "weather", "steady"], "default_volume": 0.08, "volume_range": [0.05, 0.13]},
    "rain_03": {"file": "ambient/rain_03.mp3", "tags": ["rain", "storm", "heavy"], "default_volume": 0.10, "volume_range": [0.06, 0.15]},
    "rain_on_window": {"file": "ambient/rain_on_window.mp3", "tags": ["rain", "indoor", "melancholy"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "rain_thunder": {"file": "ambient/rain_thunder.mp3", "tags": ["rain", "thunder", "storm", "dread"], "default_volume": 0.09, "volume_range": [0.05, 0.14]},
    "storm_wind_rain": {"file": "ambient/storm_wind_rain.mp3", "tags": ["storm", "wind", "rain", "crisis"], "default_volume": 0.10, "volume_range": [0.06, 0.15]},
    "thunder_distant": {"file": "ambient/thunder_distant.mp3", "tags": ["thunder", "storm", "dread"], "default_volume": 0.09, "volume_range": [0.05, 0.14]},
    "wind_soft": {"file": "ambient/wind_soft.mp3", "tags": ["wind", "weather", "lonely"], "default_volume": 0.07, "volume_range": [0.04, 0.12]},
    "wind_breeze": {"file": "ambient/wind_breeze.mp3", "tags": ["wind", "breeze", "calm", "nature"], "default_volume": 0.06, "volume_range": [0.03, 0.10]},
    "wind_strong": {"file": "ambient/wind_strong.mp3", "tags": ["wind", "storm", "tension"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "wind_howl": {"file": "ambient/wind_howl.mp3", "tags": ["wind", "howl", "dread"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "hurricane": {"file": "ambient/hurricane.mp3", "tags": ["hurricane", "storm", "disaster"], "default_volume": 0.11, "volume_range": [0.07, 0.15]},
    "city_ambience": {"file": "ambient/city_ambience.mp3", "tags": ["city", "urban", "ambient"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "highway_traffic": {"file": "ambient/highway_traffic.mp3", "tags": ["traffic", "highway", "urban"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "traffic_wet_road": {"file": "ambient/traffic_wet_road.mp3", "tags": ["traffic", "rain", "urban"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "ocean_waves": {"file": "water/ocean_waves.mp3", "tags": ["ocean", "waves", "nature"], "default_volume": 0.08, "volume_range": [0.04, 0.12]},
    "beach_waves": {"file": "water/beach_waves.mp3", "tags": ["beach", "waves", "peace"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "river": {"file": "water/river.mp3", "tags": ["river", "water", "nature"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "brook": {"file": "water/brook.mp3", "tags": ["brook", "stream", "gentle"], "default_volume": 0.06, "volume_range": [0.03, 0.10]},
    "stream_small": {"file": "water/stream_small.mp3", "tags": ["stream", "water", "quiet"], "default_volume": 0.06, "volume_range": [0.03, 0.09]},
    "waterfall": {"file": "water/waterfall.mp3", "tags": ["waterfall", "nature", "dramatic"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "water_pour": {"file": "water/water_pour.mp3", "tags": ["water", "pour", "liquid"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "fire_crackle": {"file": "nature/fire_crackle.mp3", "tags": ["fire", "crackle", "warmth"], "default_volume": 0.08, "volume_range": [0.04, 0.12]},
    "campfire": {"file": "nature/campfire.mp3", "tags": ["campfire", "fire", "outdoor"], "default_volume": 0.08, "volume_range": [0.04, 0.12]},
    "fireplace": {"file": "nature/fireplace.mp3", "tags": ["fireplace", "fire", "home"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "fire_crackling": {"file": "nature/fire_crackling.mp3", "tags": ["fire", "crackling"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "forest_ambience": {"file": "nature/forest_ambience.mp3", "tags": ["forest", "nature", "ambient"], "default_volume": 0.06, "volume_range": [0.03, 0.10]},
    "birds_chirping": {"file": "nature/birds_chirping.mp3", "tags": ["birds", "nature", "morning"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "bees_buzzing": {"file": "nature/bees_buzzing.mp3", "tags": ["bees", "nature", "summer"], "default_volume": 0.06, "volume_range": [0.03, 0.09]},
    "applause": {"file": "crowd/applause.mp3", "tags": ["applause", "crowd", "celebration"], "default_volume": 0.12, "volume_range": [0.08, 0.16]},
    "crowd_cheer": {"file": "crowd/cheer_stadium.mp3", "tags": ["crowd", "cheer", "victory"], "default_volume": 0.12, "volume_range": [0.08, 0.16]},
    "crowd_murmur": {"file": "crowd/crowd_murmur.mp3", "tags": ["crowd", "murmur", "tension"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "crowd_chatter": {"file": "crowd/crowd_chatter.mp3", "tags": ["crowd", "chatter", "social"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "crowd_cheering_outside": {"file": "crowd/crowd_cheering_outside.mp3", "tags": ["crowd", "cheer", "outdoor"], "default_volume": 0.11, "volume_range": [0.07, 0.15]},
    "office_ambience": {"file": "ambient/office_ambience.mp3", "tags": ["office", "corporate", "ambient"], "default_volume": 0.06, "volume_range": [0.03, 0.10]},
    "bank_lobby": {"file": "office/bank_lobby.mp3", "tags": ["bank", "finance", "lobby"], "default_volume": 0.06, "volume_range": [0.03, 0.09]},
    "business_lobby": {"file": "office/business_lobby.mp3", "tags": ["business", "lobby", "corporate"], "default_volume": 0.06, "volume_range": [0.03, 0.09]},
    "coffee_shop": {"file": "office/coffee_shop.mp3", "tags": ["coffee", "cafe", "ambient"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "restaurant_ambience": {"file": "office/restaurant_ambience.mp3", "tags": ["restaurant", "dining"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "cafeteria": {"file": "office/cafeteria.mp3", "tags": ["cafeteria", "crowd", "workplace"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "mall_ambience": {"file": "office/mall_ambience.mp3", "tags": ["mall", "shopping", "retail"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "typing_keyboard": {"file": "ambient/typing_keyboard.mp3", "tags": ["typing", "keyboard", "office"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "computer_keyboard": {"file": "office/computer_keyboard.mp3", "tags": ["typing", "computer", "office"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "laptop_typing": {"file": "office/laptop_typing.mp3", "tags": ["typing", "laptop", "work"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "electric_typewriter": {"file": "office/electric_typewriter.mp3", "tags": ["typewriter", "vintage"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "printer": {"file": "office/printer.mp3", "tags": ["printer", "office", "tech"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "fax_machine": {"file": "office/fax_machine.mp3", "tags": ["fax", "office", "vintage"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "elevator_interior": {"file": "office/elevator_interior.mp3", "tags": ["elevator", "office"], "default_volume": 0.06, "volume_range": [0.03, 0.09]},
    "computers_processing": {"file": "office/computers_processing.mp3", "tags": ["computer", "data", "tech"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "coins_drop": {"file": "money/coins_drop.mp3", "tags": ["coins", "money", "finance"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "coins_collecting": {"file": "money/coins_collecting.mp3", "tags": ["coins", "money", "counting"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "money_bills_rustle": {"file": "money/money_bills_rustle.mp3", "tags": ["money", "bills", "cash"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "cash_register": {"file": "money/cash_register.mp3", "tags": ["cash", "register", "retail"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "coin_spin": {"file": "money/coin_spin.mp3", "tags": ["coin", "gamble", "chance"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "piggy_bank_shake": {"file": "money/piggy_bank_shake.mp3", "tags": ["savings", "money", "finance"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "car_pass_by": {"file": "transport/car_pass_by.mp3", "tags": ["car", "traffic", "street"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "cars_drive_by": {"file": "transport/cars_drive_by.mp3", "tags": ["cars", "traffic", "city"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "train_pass_by": {"file": "transport/train_pass_by.mp3", "tags": ["train", "rail", "travel"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "train_whistle": {"file": "transport/train_whistle.mp3", "tags": ["train", "whistle"], "default_volume": 0.09, "volume_range": [0.06, 0.13]},
    "subway_train": {"file": "transport/subway_train.mp3", "tags": ["subway", "metro", "urban"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "metro_interior": {"file": "transport/metro_interior.mp3", "tags": ["metro", "subway", "interior"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "aircraft_fly_by": {"file": "transport/aircraft_fly_by.mp3", "tags": ["aircraft", "plane", "travel"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "helicopter_fly_over": {"file": "transport/helicopter_fly_over.mp3", "tags": ["helicopter", "crisis"], "default_volume": 0.10, "volume_range": [0.06, 0.14]},
    "bus_pass_by": {"file": "transport/bus_pass_by.mp3", "tags": ["bus", "transit"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "truck_pass_by": {"file": "transport/truck_pass_by.mp3", "tags": ["truck", "logistics"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "motorcycle_pass_by": {"file": "transport/motorcycle_pass_by.mp3", "tags": ["motorcycle", "street"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "heartbeat_slow": {"file": "fx/heartbeat_slow.mp3", "tags": ["heartbeat", "tension", "dread"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "heartbeat_fast": {"file": "fx/heartbeat_fast.mp3", "tags": ["heartbeat", "panic", "stress"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "whoosh_soft": {"file": "fx/whoosh_soft.mp3", "tags": ["whoosh", "transition"], "default_volume": 0.06, "volume_range": [0.03, 0.10]},
    "whoosh_transition": {"file": "fx/whoosh_transition.mp3", "tags": ["whoosh", "transition", "reveal"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "notification_ping": {"file": "fx/notification_ping.mp3", "tags": ["notification", "alert", "tech"], "default_volume": 0.07, "volume_range": [0.04, 0.11]},
    "beep_short": {"file": "fx/beep_short.mp3", "tags": ["beep", "alert", "tech"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "beep_alert": {"file": "fx/beep_alert.mp3", "tags": ["beep", "alert", "warning"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "error_buzzer": {"file": "fx/error_buzzer.mp3", "tags": ["error", "buzzer", "fail"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "multimedia_alert": {"file": "fx/multimedia_alert.mp3", "tags": ["alert", "notification", "ui"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "glass_break": {"file": "fx/glass_break.mp3", "tags": ["glass", "break", "shock"], "default_volume": 0.10, "volume_range": [0.06, 0.14]},
    "explosion_distant": {"file": "fx/explosion_distant.mp3", "tags": ["explosion", "boom", "war"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "explosion": {"file": "fx/explosion.mp3", "tags": ["explosion", "impact", "disaster"], "default_volume": 0.10, "volume_range": [0.06, 0.14]},
    "siren": {"file": "fx/siren.mp3", "tags": ["siren", "emergency", "police"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "dramatic_drums": {"file": "fx/dramatic_drums.mp3", "tags": ["drums", "dramatic", "impact"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "magic_chime": {"file": "fx/magic_chime.mp3", "tags": ["chime", "reveal", "insight"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "champagne_pop": {"file": "fx/champagne_pop.mp3", "tags": ["champagne", "celebration", "pop"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "page_flip": {"file": "fx/page_flip.mp3", "tags": ["page", "book", "document"], "default_volume": 0.06, "volume_range": [0.03, 0.09]},
    "paper_rustle": {"file": "fx/paper_rustle.mp3", "tags": ["paper", "document", "office"], "default_volume": 0.06, "volume_range": [0.03, 0.09]},
    "crumpling_paper": {"file": "fx/crumpling_paper.mp3", "tags": ["paper", "reject", "failure"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "stapler_press": {"file": "fx/stapler_press.mp3", "tags": ["stapler", "office"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "door_knock": {"file": "domestic/door_knock.mp3", "tags": ["door", "knock", "tension"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "doorbell": {"file": "domestic/doorbell.mp3", "tags": ["doorbell", "door", "arrival"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "clock_ticking": {"file": "domestic/clock_ticking.mp3", "tags": ["clock", "ticking", "time"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "clock_chime": {"file": "domestic/clock_chime.mp3", "tags": ["clock", "chime", "hour"], "default_volume": 0.08, "volume_range": [0.05, 0.11]},
    "phone_ring": {"file": "domestic/phone_ring.mp3", "tags": ["phone", "ring", "call"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "phone_dial": {"file": "domestic/phone_dial.mp3", "tags": ["phone", "dial"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "alarm_clock_ringing": {"file": "domestic/alarm_clock_ringing.mp3", "tags": ["alarm", "clock", "urgency"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "coffee_pour": {"file": "domestic/coffee_pour.mp3", "tags": ["coffee", "pour", "morning"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "coffee_maker_brewing": {"file": "domestic/coffee_maker_brewing.mp3", "tags": ["coffee", "brew", "kitchen"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "door_close": {"file": "domestic/door_close.mp3", "tags": ["door", "close"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "door_creak": {"file": "domestic/door_creak.mp3", "tags": ["door", "creak", "tension"], "default_volume": 0.07, "volume_range": [0.04, 0.10]},
    "construction": {"file": "industrial/construction.mp3", "tags": ["construction", "building"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "jackhammer": {"file": "industrial/jackhammer.mp3", "tags": ["jackhammer", "construction"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "chainsaw": {"file": "industrial/chainsaw.mp3", "tags": ["chainsaw", "industrial"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
    "drill": {"file": "industrial/drill.mp3", "tags": ["drill", "construction"], "default_volume": 0.08, "volume_range": [0.05, 0.12]},
    "factory_machine": {"file": "industrial/factory_machine.mp3", "tags": ["factory", "manufacturing"], "default_volume": 0.09, "volume_range": [0.05, 0.13]},
}

# sound_id -> download source
# ambient: trim long recordings; sfx: one-shot; loop: extend short sample
SOURCES: dict[str, dict] = {
    # Weather / urban (Gregor Quendel field recordings — OpenGameArt CC0)
    "rain_light": {"url": f"{OGA}/rain_-_falling_on_a_wooden_roof.mp3", "ambient": 22},
    "rain_heavy": {"url": f"{OGA}/rain_-_falling_on_a_metal_roof.mp3", "ambient": 22},
    "rain_01": {"url": f"{OGA}/rain_-_dropping_on_various_textures.mp3", "ambient": 20, "start": 2},
    "rain_02": {"url": f"{OGA}/rain_-_falling_on_a_wooden_roof.mp3", "ambient": 20, "start": 8},
    "rain_03": {"url": f"{OGA}/rain_-_falling_on_a_metal_roof.mp3", "ambient": 20, "start": 5},
    "rain_on_window": {"url": f"{OGA}/rain_-_dropping_on_various_textures.mp3", "ambient": 18, "start": 10},
    "rain_thunder": {"url": f"{OGA}/rain_-_distant_thunder.mp3", "ambient": 25},
    "storm_wind_rain": {"url": f"{OGA}/city_ambience_-_traffic_-_street_-_cars_drive_by_on_a_rainy_street.mp3", "ambient": 25},
    "thunder_distant": {"url": f"{OGA}/thunder_-_lightning_-_i_-_without_rain_wind_background_noise.mp3", "ambient": 20},
    "wind_soft": {"url": f"{OGA}/wind_-_autumn_wind_with_leaves_rustling.mp3", "ambient": 22, "start": 3},
    "wind_breeze": {"url": f"{OGA}/wind_-_autumn_wind_with_leaves_rustling.mp3", "ambient": 18, "start": 12},
    "wind_strong": {"url": f"{OGA}/thunder_-_lightning_-_ii_-_without_rain_wind_background_noise.mp3", "ambient": 18},
    "wind_howl": {"url": f"{OGA}/thunder_-_lightning_-_iii_-_without_rain_wind_background_noise.mp3", "ambient": 18},
    "hurricane": {"url": f"{OGA}/thunder_-_lightning_-_ambience_field_recording.mp3", "ambient": 28, "start": 15},
    "city_ambience": {"url": f"{OGA}/city_ambience_-_traffic_-_street_-_cars_and_tram.mp3", "ambient": 25, "start": 10},
    "highway_traffic": {"url": f"{OGA}/city_ambience_-_traffic_-_bridge_-_tram_train_cars_pedestrians.mp3", "ambient": 25, "start": 8},
    "traffic_wet_road": {"url": f"{OGA}/city_ambience_-_traffic_-_street_-_cars_drive_by_on_a_rainy_street.mp3", "ambient": 22},
    "office_ambience": {"url": f"{OGA}/elevator_ride.mp3", "ambient": 20},
    # Water
    "ocean_waves": {"url": f"{OGA}/water_stream_-_viii.mp3", "ambient": 25},
    "beach_waves": {"url": f"{OGA}/water_stream_-_i.mp3", "ambient": 22},
    "river": {"url": f"{OGA}/water_stream_-_ii.mp3", "ambient": 22},
    "brook": {"url": f"{OGA}/water_stream_-_iii.mp3", "ambient": 20},
    "stream_small": {"url": f"{OGA}/water_stream_-_vi.mp3", "ambient": 18},
    "waterfall": {"url": f"{OGA}/water_stream_-_x.mp3", "ambient": 22},
    "water_pour": {"url": k("RPG Audio/metalPot1.ogg"), "sfx": True},
    # Nature / fire
    "fire_crackle": {"url": f"{OGA}/fire-1.ogg", "loop": 22},
    "campfire": {"url": f"{OGA}/fire_sound_effect.mp3", "loop": 20},
    "fireplace": {"url": f"{OGA}/fire.wav", "ambient": 25, "start": 5},
    "fire_crackling": {"url": f"{OGA}/fire-1.wav", "loop": 20},
    "forest_ambience": {"url": f"{OGA}/city_ambience_-_park_-_spring_-_with_birds_cars_and_planes.mp3", "ambient": 28, "start": 5},
    "birds_chirping": {"url": f"{OGA}/nature_-_birds_-_singing_and_talking_lovebirds.mp3", "ambient": 22},
    "bees_buzzing": {"url": f"{OGA}/wind_-_autumn_wind_with_leaves_rustling.mp3", "ambient": 12, "start": 20},
    # Crowd
    "applause": {"url": f"{OGA}/crowd_-_applause_-_clapping.mp3", "ambient": 18},
    "crowd_cheer": {"url": f"{OGA}/crowd_-_cheering_-_strong_cheering_-_i.mp3", "ambient": 16},
    "crowd_murmur": {"url": f"{OGA}/crowd_-_cheering_-_soft_cheering_-_ii.mp3", "ambient": 20},
    "crowd_chatter": {"url": f"{OGA}/crowd_-_cheering_-_soft_cheering_and_chatter.mp3", "ambient": 22},
    "crowd_cheering_outside": {"url": f"{OGA}/crowd_-_cheering_-_ambience_and_cheering.mp3", "ambient": 20},
    "mall_ambience": {"url": f"{OGA}/crowd_-_mall_ambience.mp3", "ambient": 25},
    "bank_lobby": {"url": f"{OGA}/elevator_ride.mp3", "ambient": 18, "start": 3},
    "business_lobby": {"url": f"{OGA}/crowd_-_mall_ambience.mp3", "ambient": 20, "start": 8},
    "coffee_shop": {"url": f"{OGA}/crowd_-_cheering_-_soft_cheering_and_chatter.mp3", "ambient": 18, "start": 4},
    "restaurant_ambience": {"url": f"{OGA}/crowd_-_school_excursion.mp3", "ambient": 22},
    "cafeteria": {"url": f"{OGA}/crowd_-_school_excursion.mp3", "ambient": 20, "start": 6},
    # Office / typing (Kenney CC0)
    "typing_keyboard": {"url": k("Interface Sounds/scroll_003.ogg"), "sfx": True},
    "computer_keyboard": {"url": k("Interface Sounds/click_003.ogg"), "sfx": True, "repeat": 8, "gap_ms": 90},
    "laptop_typing": {"url": k("Interface Sounds/click_002.ogg"), "sfx": True, "repeat": 10, "gap_ms": 70},
    "electric_typewriter": {"url": k("Interface Sounds/scratch_003.ogg"), "sfx": True},
    "printer": {"url": k("Digital Audio/spaceTrash3.ogg"), "sfx": True},
    "fax_machine": {"url": k("Digital Audio/phaserUp3.ogg"), "sfx": True},
    "elevator_interior": {"url": f"{OGA}/elevator_ride.mp3", "ambient": 18},
    "computers_processing": {"url": k("Digital Audio/spaceTrash1.ogg"), "sfx": True, "repeat": 3, "gap_ms": 400},
    # Money (Kenney Casino + RPG)
    "coins_drop": {"url": k("Casino Audio/chipsCollide2.ogg"), "sfx": True, "repeat": 4, "gap_ms": 100},
    "coins_collecting": {"url": k("Casino Audio/chipsHandle3.ogg"), "sfx": True},
    "money_bills_rustle": {"url": k("RPG Audio/cloth2.ogg"), "sfx": True},
    "cash_register": {"url": k("Interface Sounds/bong_001.ogg"), "sfx": True},
    "coin_spin": {"url": k("Casino Audio/chipsStack4.ogg"), "sfx": True},
    "piggy_bank_shake": {"url": k("Casino Audio/chipsHandle5.ogg"), "sfx": True},
    # Transport
    "car_pass_by": {"url": f"{OGA}/motorcycle_engine_-_start_and_drive_away.mp3", "sfx": True},
    "cars_drive_by": {"url": f"{OGA}/city_ambience_-_traffic_-_street_-_cars_and_tram.mp3", "ambient": 12, "start": 20},
    "train_pass_by": {"url": f"{OGA}/city_ambience_-_traffic_-_bridge_-_tram_train_cars_pedestrians.mp3", "ambient": 15, "start": 30},
    "train_whistle": {"url": k("Digital Audio/twoTone2.ogg"), "sfx": True},
    "subway_train": {"url": f"{OGA}/city_ambience_-_traffic_-_street_-_cars_and_tram.mp3", "ambient": 14, "start": 45},
    "metro_interior": {"url": f"{OGA}/elevator_ride.mp3", "ambient": 16, "start": 2},
    "aircraft_fly_by": {"url": f"{OGA}/city_ambience_-_park_-_spring_-_with_birds_cars_and_planes.mp3", "ambient": 12, "start": 60},
    "helicopter_fly_over": {"url": k("Digital Audio/spaceTrash5.ogg"), "sfx": True, "repeat": 4, "gap_ms": 200},
    "bus_pass_by": {"url": f"{OGA}/city_ambience_-_traffic_-_street_-_cars_and_tram.mp3", "ambient": 10, "start": 55},
    "truck_pass_by": {"url": f"{OGA}/city_ambience_-_traffic_-_bridge_-_tram_train_cars_pedestrians.mp3", "ambient": 10, "start": 40},
    "motorcycle_pass_by": {"url": f"{OGA}/motorcycle_engine_-_start_and_drive_away.mp3", "sfx": True},
    # FX
    "heartbeat_slow": {"url": k("Digital Audio/lowDown.ogg"), "sfx": True, "repeat": 6, "gap_ms": 700},
    "heartbeat_fast": {"url": k("Digital Audio/lowDown.ogg"), "sfx": True, "repeat": 10, "gap_ms": 350},
    "whoosh_soft": {"url": k("Foley Sounds/Woosh/woosh2.ogg"), "sfx": True},
    "whoosh_transition": {"url": k("Foley Sounds/Woosh/woosh5.ogg"), "sfx": True},
    "notification_ping": {"url": k("Interface Sounds/select_003.ogg"), "sfx": True},
    "beep_short": {"url": k("Interface Sounds/tick_001.ogg"), "sfx": True},
    "beep_alert": {"url": k("Interface Sounds/error_004.ogg"), "sfx": True},
    "error_buzzer": {"url": k("Interface Sounds/error_007.ogg"), "sfx": True},
    "multimedia_alert": {"url": k("Interface Sounds/confirmation_002.ogg"), "sfx": True},
    "glass_break": {"url": k("Impact Sounds/impactGlass_heavy_002.ogg"), "sfx": True},
    "explosion_distant": {"url": k("Impact Sounds/impactBell_heavy_001.ogg"), "sfx": True},
    "explosion": {"url": k("Impact Sounds/impactPunch_heavy_003.ogg"), "sfx": True},
    "siren": {"url": k("Digital Audio/phaserDown2.ogg"), "sfx": True, "repeat": 4, "gap_ms": 300},
    "dramatic_drums": {"url": k("Impact Sounds/impactBell_heavy_004.ogg"), "sfx": True},
    "magic_chime": {"url": k("Interface Sounds/pluck_001.ogg"), "sfx": True},
    "champagne_pop": {"url": k("Impact Sounds/impactSoft_heavy_002.ogg"), "sfx": True},
    "page_flip": {"url": k("RPG Audio/bookFlip2.ogg"), "sfx": True},
    "paper_rustle": {"url": k("RPG Audio/cloth1.ogg"), "sfx": True},
    "crumpling_paper": {"url": k("RPG Audio/cloth4.ogg"), "sfx": True},
    "stapler_press": {"url": k("Impact Sounds/impactGeneric_light_002.ogg"), "sfx": True},
    # Domestic
    "door_knock": {"url": k("Impact Sounds/impactWood_medium_003.ogg"), "sfx": True, "repeat": 3, "gap_ms": 500},
    "doorbell": {"url": k("Impact Sounds/impactBell_heavy_002.ogg"), "sfx": True},
    "clock_ticking": {"url": k("Interface Sounds/tick_002.ogg"), "sfx": True, "repeat": 12, "gap_ms": 900},
    "clock_chime": {"url": k("Impact Sounds/impactBell_heavy_001.ogg"), "sfx": True},
    "phone_ring": {"url": k("Interface Sounds/question_002.ogg"), "sfx": True, "repeat": 3, "gap_ms": 1200},
    "phone_dial": {"url": k("Interface Sounds/click_004.ogg"), "sfx": True, "repeat": 7, "gap_ms": 150},
    "alarm_clock_ringing": {"url": k("Interface Sounds/error_003.ogg"), "sfx": True, "repeat": 4, "gap_ms": 800},
    "coffee_pour": {"url": k("RPG Audio/metalPot2.ogg"), "sfx": True},
    "coffee_maker_brewing": {"url": k("Digital Audio/spaceTrash2.ogg"), "sfx": True},
    "door_close": {"url": k("RPG Audio/doorClose_2.ogg"), "sfx": True},
    "door_creak": {"url": k("RPG Audio/creak2.ogg"), "sfx": True},
    # Industrial
    "construction": {"url": f"{OGA}/city_ambience_-_traffic_-_bridge_-_tram_train_cars_pedestrians.mp3", "ambient": 18, "start": 15},
    "jackhammer": {"url": k("Impact Sounds/impactMining_002.ogg"), "sfx": True, "repeat": 8, "gap_ms": 250},
    "chainsaw": {"url": k("Impact Sounds/impactMining_004.ogg"), "sfx": True, "repeat": 6, "gap_ms": 300},
    "drill": {"url": k("Impact Sounds/impactMining_001.ogg"), "sfx": True, "repeat": 5, "gap_ms": 350},
    "factory_machine": {"url": k("Digital Audio/spaceTrash4.ogg"), "sfx": True, "repeat": 5, "gap_ms": 400},
}


def _run(cmd: list[str]) -> None:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-600:] if r.stderr else "Command failed")


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(["curl", "-fsSL", "--retry", "3", "--retry-delay", "2", "-o", str(dest), url])


def export_mp3(
    src: Path,
    dest: Path,
    *,
    start: float = 0,
    duration: float | None = None,
    loop_seconds: float | None = None,
    normalize: bool = True,
) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    filters: list[str] = []
    if loop_seconds:
        filters.append(f"aloop=loop=-1:size=2e+09,atrim=0:{loop_seconds}")
    elif duration:
        filters.append(f"atrim={start}:{start + duration}")
        filters.append("asetpts=PTS-STARTPTS")
    if normalize:
        filters.append("highpass=f=40")
        filters.append("loudnorm=I=-18:TP=-2:LRA=9:print_format=summary")
    af = ",".join(filters) if filters else None
    cmd = ["ffmpeg", "-y", "-i", str(src)]
    if af:
        cmd.extend(["-af", af])
    cmd.extend(["-ar", "44100", "-ac", "2", "-q:a", "2", str(dest)])
    _run(cmd)


def build_repeated(src: Path, dest: Path, *, repeat: int, gap_ms: int) -> None:
    """Concatenate one-shot with silence gaps."""
    tmp = dest.parent / f".tmp_{dest.stem}"
    tmp.mkdir(exist_ok=True)
    parts: list[Path] = []
    for i in range(repeat):
        part = tmp / f"p{i:03d}.wav"
        _run(["ffmpeg", "-y", "-i", str(src), "-ar", "44100", "-ac", "2", str(part)])
        parts.append(part)
        if i < repeat - 1 and gap_ms > 0:
            gap = tmp / f"g{i:03d}.wav"
            _run([
                "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r=44100:cl=2:d={gap_ms/1000:.3f}",
                str(gap),
            ])
            parts.append(gap)
    list_file = tmp / "list.txt"
    list_file.write_text("\n".join(f"file '{p}'" for p in parts), encoding="utf-8")
    merged = tmp / "merged.wav"
    _run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(merged)])
    export_mp3(merged, dest, normalize=True)
    for p in tmp.iterdir():
        p.unlink(missing_ok=True)
    tmp.rmdir()


def process_sound(sound_id: str, spec: dict, dest: Path) -> None:
    url = spec["url"]
    suffix = Path(urllib.parse.urlparse(url).path).suffix or ".bin"
    with tempfile.TemporaryDirectory(prefix="sfx_dl_") as td:
        raw = Path(td) / f"source{suffix}"
        download(url, raw)
        if spec.get("repeat"):
            mid = Path(td) / "oneshot.wav"
            _run(["ffmpeg", "-y", "-i", str(raw), "-ar", "44100", "-ac", "2", str(mid)])
            build_repeated(mid, dest, repeat=spec["repeat"], gap_ms=spec.get("gap_ms", 100))
        elif spec.get("loop"):
            export_mp3(raw, dest, loop_seconds=spec["loop"], normalize=True)
        elif spec.get("ambient"):
            export_mp3(
                raw, dest,
                start=spec.get("start", 0),
                duration=spec["ambient"],
                normalize=True,
            )
        elif spec.get("sfx"):
            export_mp3(raw, dest, normalize=True)
        else:
            export_mp3(raw, dest, normalize=True)


def write_catalog() -> None:
    with open(SFX / "catalog.yaml", "w", encoding="utf-8") as f:
        yaml.dump(CATALOG, f, default_flow_style=False, sort_keys=True, allow_unicode=True)


def main() -> int:
    missing = [sid for sid in CATALOG if sid not in SOURCES]
    if missing:
        print(f"Warning: no source for {len(missing)} sounds: {missing[:5]}...", file=sys.stderr)

    print(f"Downloading {len(SOURCES)} CC0 sounds (OpenGameArt + Kenney)...")
    ok, fail = 0, 0
    for sound_id, spec in SOURCES.items():
        if sound_id not in CATALOG:
            continue
        dest = SFX / CATALOG[sound_id]["file"]
        try:
            process_sound(sound_id, spec, dest)
            ok += 1
            print(f"  ok  {sound_id}")
        except Exception as e:
            fail += 1
            print(f"  FAIL {sound_id}: {e}", file=sys.stderr)

    write_catalog()
    print(f"\nDone: {ok} downloaded, {fail} failed")
    return 0 if fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

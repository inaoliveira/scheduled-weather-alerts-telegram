#!/usr/bin/env python3
import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

TZ = "America/Sao_Paulo"
BR_TZ = ZoneInfo(TZ)

CITIES = [
    ("Curitiba",  -25.4284, -49.2733),
    ("Araucária", -25.5874, -49.4050),
]

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Environment variables TG_BOT_TOKEN or TG_CHAT_ID not set.")

WEATHER_CODE_PT = {
    0:  "Céu limpo",
    1:  "Predominantemente limpo",
    2:  "Parcialmente nublado",
    3:  "Nublado",
    45: "Neblina",
    48: "Neblina com geada",
    51: "Garoa fraca",
    53: "Garoa moderada",
    55: "Garoa forte",
    56: "Garoa congelante fraca",
    57: "Garoa congelante forte",
    61: "Chuva fraca",
    63: "Chuva moderada",
    65: "Chuva forte",
    66: "Chuva congelante fraca",
    67: "Chuva congelante forte",
    71: "Neve fraca",
    73: "Neve moderada",
    75: "Neve forte",
    77: "Grãos de neve",
    80: "Pancadas fracas",
    81: "Pancadas moderadas",
    82: "Pancadas fortes",
    85: "Pancadas de neve fracas",
    86: "Pancadas de neve fortes",
    95: "Trovoadas",
    96: "Trovoadas com granizo fraco",
    99: "Trovoadas com granizo forte",
}

def now_br_str() -> str:
    return datetime.now(BR_TZ).strftime("%d/%m %H:%M")

def today_yyyy_mm_dd_br() -> str:
    return datetime.now(BR_TZ).strftime("%Y-%m-%d")

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()

def get_today_hourly_rain_stats(lat: float, lon: float):
    """Chance de chuva por hora HOJE (BRT). Retorna pico e média."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "precipitation_probability",
        "timezone": TZ,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    times = data["hourly"]["time"]
    probs = data["hourly"]["precipitation_probability"]

    today = today_yyyy_mm_dd_br()
    today_probs = [p for t, p in zip(times, probs) if t.startswith(today)]
    if not today_probs:
        return None, None

    return max(today_probs), round(sum(today_probs) / len(today_probs))

def get_tomorrow_daily_forecast(lat: float, lon: float):
    """
    Previsão diária (HOJE e AMANHÃ). Retorna:
    (data_amanha, descricao, chance_max_chuva).
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "weathercode,precipitation_probability_max",
        "forecast_days": 2,
        "timezone": TZ,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()

    wc_list = data["daily"]["weathercode"]
    pp_list = data["daily"]["precipitation_probability_max"]
    time_list = data["daily"]["time"]

    if len(wc_list) < 2 or len(pp_list) < 2 or len(time_list) < 2:
        return None

    date_tomorrow = time_list[1]  # YYYY-MM-DD
    wc = wc_list[1]
    pp = pp_list[1]

    desc = WEATHER_CODE_PT.get(wc, f"Condição {wc}")
    return date_tomorrow, desc, pp

def run_today():
    lines = [f"🌧️ <b>Chuva hoje</b> — {now_br_str()}", ""]
    for name, lat, lon in CITIES:
        max_p, avg_p = get_today_hourly_rain_stats(lat, lon)
        if max_p is None:
            lines.append(f"• <b>{name}</b>: indisponível 😕")
        else:
            lines.append(f"• <b>{name}</b>: pico <b>{max_p}%</b> | média <b>{avg_p}%</b>")
    send_telegram("\n".join(lines))

def run_tomorrow():
    lines = [f"🗓️ <b>Previsão de amanhã</b> — gerado {now_br_str()}", ""]
    for name, lat, lon in CITIES:
        out = get_tomorrow_daily_forecast(lat, lon)
        if out is None:
            lines.append(f"• <b>{name}</b>: indisponível 😕")
        else:
            date_tomorrow, desc, ppmax = out
            d = datetime.strptime(date_tomorrow, "%Y-%m-%d").strftime("%d/%m")
            lines.append(f"• <b>{name}</b> (amanhã {d}): <b>{desc}</b> • chuva até <b>{ppmax}%</b>")
    send_telegram("\n".join(lines))

def main():
    mode = (sys.argv[1] if len(sys.argv) > 1 else "today").strip().lower()
    if mode in ("tomorrow", "amanha", "amanhã"):
        run_tomorrow()
    else:
        run_today()

if __name__ == "__main__":
    main()

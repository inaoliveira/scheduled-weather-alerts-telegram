#!/usr/bin/env python3
import os
import sys
import requests
from datetime import datetime
from zoneinfo import ZoneInfo

TZ_NAME = "America/Sao_Paulo"
TZ = ZoneInfo(TZ_NAME)

CITIES = [
    ("Curitiba",  -25.4284, -49.2733),
    ("Araucária", -25.5874, -49.4050),
]

BOT_TOKEN = os.environ.get("TG_BOT_TOKEN")
CHAT_ID = os.environ.get("TG_CHAT_ID")

if not BOT_TOKEN or not CHAT_ID:
    raise RuntimeError("Environment variables TG_BOT_TOKEN or TG_CHAT_ID not set.")

# Weather code docs (Open-Meteo): 0..99
SUNNY_CODES = {0, 1}
CLOUDY_CODES = {2, 3, 45, 48}

def now_br_str() -> str:
    return datetime.now(TZ).strftime("%d/%m %H:%M")

def today_str() -> str:
    return datetime.now(TZ).strftime("%Y-%m-%d")

def tomorrow_str() -> str:
    # simples e suficiente: pega "hoje" no fuso BR e soma 1 dia via timestamp
    # (evita depender de libs externas)
    ts = datetime.now(TZ).timestamp() + 24 * 3600
    return datetime.fromtimestamp(ts, TZ).strftime("%Y-%m-%d")

def period_from_hour(h: int) -> str:
    if 0 <= h <= 5:
        return "madrugada"
    if 6 <= h <= 11:
        return "manhã"
    if 12 <= h <= 17:
        return "tarde"
    return "noite"

def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
    r = requests.post(url, json=payload, timeout=20)
    r.raise_for_status()

def fetch_open_meteo(lat: float, lon: float):
    """
    Pega:
    - hourly precip prob
    - daily weathercode e daily precip prob max
    com timezone America/Sao_Paulo
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": TZ_NAME,
        "hourly": "precipitation_probability",
        "daily": "weathercode,precipitation_probability_max",
        "forecast_days": 2,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json()

def summarize_day(data: dict, target_date: str):
    """
    Retorna um resumo no formato pedido:
    - se max chuva > 60%: "Possibilidade de chuva XX% (periodo)"
    - senão: "Dia ensolarado" ou "Dia nublado"
    Também retorna o pico e o horário do pico.
    """
    # DAILY
    daily_dates = data["daily"]["time"]
    daily_wc = data["daily"]["weathercode"]
    daily_ppmax = data["daily"]["precipitation_probability_max"]

    if target_date not in daily_dates:
        return "indisponível 😕"

    idx = daily_dates.index(target_date)
    wc = int(daily_wc[idx])
    ppmax = int(daily_ppmax[idx]) if daily_ppmax[idx] is not None else 0

    # HOURLY (para achar a hora do pico)
    times = data["hourly"]["time"]
    probs = data["hourly"]["precipitation_probability"]

    # filtra as horas daquele dia
    day_probs = []
    for t, p in zip(times, probs):
        # t vem tipo "YYYY-MM-DDTHH:MM"
        if t.startswith(target_date):
            # pega hora HH
            hour = int(t[11:13])
            day_probs.append((hour, int(p)))

    # se tiver dados horários, acha o pico por hora
    if day_probs:
        peak_hour, peak_prob = max(day_probs, key=lambda x: x[1])
    else:
        peak_hour, peak_prob = None, ppmax

    # regra de chuva
    if ppmax > 60:
        if peak_hour is None:
            return f"Possibilidade de chuva <b>{ppmax}%</b>"
        periodo = period_from_hour(peak_hour)
        return f"Possibilidade de chuva <b>{ppmax}%</b> ({periodo})"

    # regra de condição do dia
    if wc in SUNNY_CODES:
        return "Dia <b>ensolarado</b>"
    if wc in CLOUDY_CODES:
        return "Dia <b>nublado</b>"

    # se não é sol/nuvem e também não passou 60% de chuva,
    # ainda assim pode ser garoa/pancadas leves etc.
    # Vamos chamar de nublado (mais honesto no seu esquema).
    return "Dia <b>nublado</b>"

def run_forecast(mode: str):
    """
    mode:
      - today: previsão do dia de hoje (06:00 e 16:50)
      - tomorrow: previsão do dia seguinte (22:40)
    """
    mode = mode.lower().strip()
    if mode == "tomorrow":
        target = tomorrow_str()
        title = "🗓️ <b>Previsão de amanhã</b>"
    else:
        target = today_str()
        title = "☀️🌧️ <b>Previsão de hoje</b>"

    lines = [f"{title} — {now_br_str()}", ""]

    for name, lat, lon in CITIES:
        data = fetch_open_meteo(lat, lon)
        summary = summarize_day(data, target)
        lines.append(f"• <b>{name}</b>: {summary}")

    send_telegram("\n".join(lines))

def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "today"
    run_forecast(mode)

if __name__ == "__main__":
    main()

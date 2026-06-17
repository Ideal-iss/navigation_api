"""
Модуль позиционирования по маячкам (BLE).

Содержит современные методы определения координат:
  * калиброванная лог-дистанционная модель затухания (RSSI -> расстояние);
  * сглаживание RSSI (экспоненциальное скользящее среднее, EMA) для борьбы с дрожанием;
  * мультилатерация методом наименьших квадратов (>=3 маячков);
  * взвешенный центроид как задокументированный запасной вариант (<3 маячков).

Зависимости: только numpy (без тяжёлых ML-библиотек).
"""
from typing import Dict, List, Tuple, Optional
import math

try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:  # pragma: no cover - numpy указан в requirements
    _HAS_NUMPY = False


# --- Параметры модели по умолчанию -------------------------------------------
# n  — показатель затухания среды (free space ~2.0, помещение ~2.5..4.0).
# RSSI@1m берётся из поля beacon.tx_power (измеренный RSSI на расстоянии 1 м).
DEFAULT_PATH_LOSS_N = 2.5
DEFAULT_EMA_ALPHA = 0.4  # вес нового замера; меньше => сильнее сглаживание

# Состояние EMA-фильтра по каждому маячку (minor -> сглаженный RSSI).
# Эндпоинт без состояния, поэтому фильтр живёт на уровне модуля между запросами.
_ema_state: Dict[int, float] = {}


def reset_filters() -> None:
    """Сбросить состояние сглаживания (например, при смене сессии/тесте)."""
    _ema_state.clear()


def smooth_rssi(minor: int, rssi: float, alpha: float = DEFAULT_EMA_ALPHA) -> float:
    """
    Экспоненциальное скользящее среднее RSSI по каждому маячку.

    Снижает дрожание (jitter) измерений между последовательными запросами.
    s_t = alpha * rssi + (1 - alpha) * s_{t-1}.
    """
    prev = _ema_state.get(minor)
    s = rssi if prev is None else alpha * rssi + (1.0 - alpha) * prev
    _ema_state[minor] = s
    return s


def rssi_to_distance(rssi: float, rssi_at_1m: float,
                     n: float = DEFAULT_PATH_LOSS_N) -> float:
    """
    Лог-дистанционная модель затухания сигнала.

        RSSI = RSSI@1m - 10 * n * log10(d)
        =>  d = 10 ** ((RSSI@1m - RSSI) / (10 * n))

    rssi_at_1m — опорный уровень на 1 м (beacon.tx_power), n — показатель среды.
    """
    exponent = (rssi_at_1m - rssi) / (10.0 * n)
    return max(10.0 ** exponent, 0.1)


def weighted_centroid(points: List[Tuple[float, float, float]]
                      ) -> Tuple[float, float, float]:
    """
    Запасной метод (<3 маячков): взвешенный центроид, вес = 1/d^2.

    points: список (x, y, distance).
    Возвращает (x, y, оценка_точности).
    """
    # rssi_to_distance гарантирует d >= 0.1, поэтому деления на ноль не будет,
    # но total может быть очень мал — на всякий случай защищаемся.
    weights = [1.0 / (d ** 2) for _, _, d in points]
    total = sum(weights) or 1e-9
    x = sum(w * px for w, (px, _, _) in zip(weights, points)) / total
    y = sum(w * py for w, (_, py, _) in zip(weights, points)) / total
    # Грубая оценка точности — взвешенное среднее расстояние.
    accuracy = sum(w * d for w, (_, _, d) in zip(weights, points)) / total
    return x, y, accuracy


def multilaterate_lsq(points: List[Tuple[float, float, float]]
                      ) -> Tuple[float, float, float]:
    """
    Мультилатерация методом наименьших квадратов (>=3 маячков).

    Систему окружностей  (x-xi)^2 + (y-yi)^2 = di^2  линеаризуем, вычитая
    последнее уравнение из остальных, получаем линейную систему A·p = b,
    которую решаем через np.linalg.lstsq.

    Возвращает (x, y, оценка_неопределённости_в_метрах).
    Оценка неопределённости = RMS невязки уравнений окружностей.
    """
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    ds = np.array([p[2] for p in points], dtype=float)

    # Опорная точка — маячок с минимальным расстоянием (наиболее надёжный).
    ref = int(np.argmin(ds))
    x0, y0, d0 = xs[ref], ys[ref], ds[ref]

    idx = [i for i in range(len(points)) if i != ref]
    A = np.array([[2.0 * (xs[i] - x0), 2.0 * (ys[i] - y0)] for i in idx])
    b = np.array([
        (d0 ** 2 - ds[i] ** 2)
        - (x0 ** 2 - xs[i] ** 2)
        - (y0 ** 2 - ys[i] ** 2)
        for i in idx
    ])

    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    x, y = float(sol[0]), float(sol[1])

    # Неопределённость: RMS разности |оценка-маячок| и измеренного расстояния.
    est = np.sqrt((xs - x) ** 2 + (ys - y) ** 2)
    rms = float(np.sqrt(np.mean((est - ds) ** 2)))
    return x, y, rms


def estimate_position(
    beacons: List[dict],
    readings: Dict[int, float],
    path_loss_n: float = DEFAULT_PATH_LOSS_N,
    smoothing: bool = True,
    ema_alpha: float = DEFAULT_EMA_ALPHA,
) -> dict:
    """
    Главная функция позиционирования.

    beacons  — записи маячков из БД (dict с x, y, floor, tx_power, minor).
    readings — {minor: rssi}.

    Алгоритм:
      1) сглаживаем RSSI (EMA), если включено;
      2) переводим RSSI в расстояние лог-дистанционной моделью;
      3) при >=3 маячках — мультилатерация МНК, иначе — взвешенный центроид;
      4) этаж — по большинству среди ближайших маячков.

    Возвращает dict: x, y, floor, accuracy, method, num_beacons, uncertainty.
    """
    by_minor = {b["minor"]: b for b in beacons}
    pts: List[Tuple[float, float, float, int]] = []  # x, y, distance, floor
    for minor, rssi in readings.items():
        b = by_minor.get(minor)
        if not b:
            continue
        r = smooth_rssi(minor, rssi, ema_alpha) if smoothing else float(rssi)
        d = rssi_to_distance(r, b["tx_power"], path_loss_n)
        pts.append((b["x"], b["y"], d, b["floor"]))

    if not pts:
        return None  # вызывающий код вернёт 404

    # Этаж — по маячкам, взвешенным обратно расстоянию (ближние важнее).
    floor_w: Dict[int, float] = {}
    for x, y, d, fl in pts:
        floor_w[fl] = floor_w.get(fl, 0.0) + 1.0 / (d ** 2)
    floor = max(floor_w, key=floor_w.get)

    # Координаты считаем ТОЛЬКО по маячкам выбранного этажа: маячки соседних
    # этажей живут в той же системе координат (x, y) и иначе искажали бы
    # мультилатерацию, «притягивая» решение к чужому этажу.
    xy = [(x, y, d) for (x, y, d, fl) in pts if fl == floor]

    if len(xy) >= 3 and _HAS_NUMPY:
        try:
            x, y, uncertainty = multilaterate_lsq(xy)
            method = "lsq_multilateration"
        except Exception:
            x, y, uncertainty = weighted_centroid(xy)
            method = "weighted_centroid_fallback"
    else:
        x, y, uncertainty = weighted_centroid(xy)
        method = "weighted_centroid"  # <3 маячков — запасной вариант

    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "floor": floor,
        "accuracy": round(uncertainty, 2),
        "method": method,
        "num_beacons": len(xy),
        "uncertainty": round(uncertainty, 2),
    }

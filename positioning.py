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
import time

try:
    import numpy as np
    _HAS_NUMPY = True
except Exception:  # pragma: no cover - numpy указан в requirements
    _HAS_NUMPY = False


# --- Параметры модели по умолчанию -------------------------------------------
# n  — показатель затухания среды (free space ~2.0, помещение ~2.5..4.0).
# RSSI@1m берётся из поля beacon.tx_power (измеренный RSSI на расстоянии 1 м).
DEFAULT_PATH_LOSS_N = 2.7          # типичное значение для коридоров/аудиторий
DEFAULT_EMA_ALPHA   = 0.4          # вес нового замера; меньше => сильнее сглаживание
SESSION_TTL         = 120.0        # сек: через сколько забываем неактивную сессию
OUTLIER_SIGMA       = 2.0          # порог отсева: маяк дальше μ + σ*OUTLIER_SIGMA отбрасывается
MIN_RSSI            = -90.0        # маяки слабее этого уровня игнорируются

# Состояние EMA-фильтра, разделённое ПО СЕССИЯМ: (session_id, minor) -> (rssi, ts).
# Раньше состояние было глобальным по minor — RSSI разных устройств для одного
# маячка смешивались, искажая позицию на многопользовательском сервере.
# Теперь у каждого клиента своя сессия; неактивные сессии вычищаются по TTL.
_ema_state: Dict[Tuple[str, int], Tuple[float, float]] = {}


def reset_filters() -> None:
    """Сбросить состояние сглаживания (например, при смене сессии/тесте)."""
    _ema_state.clear()


def _purge_stale(now: float) -> None:
    """Удалить записи сессий, не обновлявшиеся дольше SESSION_TTL."""
    stale = [k for k, (_, ts) in _ema_state.items() if now - ts > SESSION_TTL]
    for k in stale:
        del _ema_state[k]


def smooth_rssi(session_id: str, minor: int, rssi: float,
                alpha: float = DEFAULT_EMA_ALPHA, now: Optional[float] = None) -> float:
    """
    Экспоненциальное скользящее среднее RSSI по каждому маячку в рамках сессии.

    Снижает дрожание (jitter) измерений между последовательными запросами одного
    клиента. s_t = alpha * rssi + (1 - alpha) * s_{t-1}.
    """
    if now is None:
        now = time.time()
    key = (session_id, minor)
    prev = _ema_state.get(key)
    s = rssi if prev is None else alpha * rssi + (1.0 - alpha) * prev[0]
    _ema_state[key] = (s, now)
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


def reject_outliers(points: List[Tuple[float, float, float]],
                    sigma: float = OUTLIER_SIGMA) -> List[Tuple[float, float, float]]:
    """
    Удалить маяки, чьё расстояние аномально велико (μ + σ·std).

    При большом разбросе расстояний дальние маяки с нестабильным RSSI
    «утягивают» позицию в сторону — их лучше выбросить.
    Если после отсева осталось < 2 точек, возвращаем исходный список.
    """
    if len(points) < 3:
        return points
    ds = [d for _, _, d in points]
    mu = sum(ds) / len(ds)
    std = math.sqrt(sum((d - mu) ** 2 for d in ds) / len(ds))
    threshold = mu + sigma * std
    filtered = [p for p in points if p[2] <= threshold]
    return filtered if len(filtered) >= 2 else points


def weighted_centroid(points: List[Tuple[float, float, float]]
                      ) -> Tuple[float, float, float]:
    """
    Запасной метод (<3 маячков): взвешенный центроид, вес = exp(-d).

    Экспоненциальный вес сильнее подавляет дальние маяки по сравнению с 1/d²,
    что даёт более стабильный результат в помещениях.
    """
    weights = [math.exp(-d) for _, _, d in points]
    total = sum(weights) or 1e-9
    x = sum(w * px for w, (px, _, _) in zip(weights, points)) / total
    y = sum(w * py for w, (_, py, _) in zip(weights, points)) / total
    accuracy = sum(w * d for w, (_, _, d) in zip(weights, points)) / total
    return x, y, accuracy


def multilaterate_lsq(points: List[Tuple[float, float, float]]
                      ) -> Tuple[float, float, float]:
    """
    Взвешенная мультилатерация (WLSQ, >=3 маячков).

    Систему окружностей линеаризуем вычитанием опорного уравнения, затем
    решаем взвешенным МНК: ближние маяки получают больший вес (w = exp(-d)),
    что снижает влияние дальних нестабильных измерений.

    Возвращает (x, y, RMS_невязки_в_метрах).
    """
    xs = np.array([p[0] for p in points], dtype=float)
    ys = np.array([p[1] for p in points], dtype=float)
    ds = np.array([p[2] for p in points], dtype=float)

    # Веса: экспоненциальное затухание по расстоянию
    ws = np.exp(-ds)
    ws = ws / ws.sum()

    # Опорная точка — ближайший маяк
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
    W = np.diag([ws[i] for i in idx])

    # Взвешенный МНК: (AᵀWA)⁻¹ AᵀWb
    AtW = A.T @ W
    lhs = AtW @ A
    rhs = AtW @ b
    try:
        sol = np.linalg.solve(lhs, rhs)
    except np.linalg.LinAlgError:
        sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    x, y = float(sol[0]), float(sol[1])

    est = np.sqrt((xs - x) ** 2 + (ys - y) ** 2)
    rms = float(np.sqrt(np.mean(ws * (est - ds) ** 2)))
    return x, y, rms


def estimate_position(
    beacons: List[dict],
    readings: Dict[int, float],
    path_loss_n: float = DEFAULT_PATH_LOSS_N,
    smoothing: bool = True,
    ema_alpha: float = DEFAULT_EMA_ALPHA,
    session_id: Optional[str] = None,
) -> dict:
    """
    Главная функция позиционирования.

    beacons    — записи маячков из БД (dict с x, y, floor, tx_power, minor).
    readings   — {minor: rssi}.
    session_id — идентификатор клиента для пер-сессионного EMA-сглаживания.
                 Если не задан, межзапросное сглаживание не применяется
                 (чтобы не смешивать RSSI разных устройств); клиент при этом
                 может сглаживать на своей стороне.

    Алгоритм:
      1) сглаживаем RSSI (EMA) в рамках сессии, если включено и есть session_id;
      2) переводим RSSI в расстояние лог-дистанционной моделью;
      3) при >=3 маячках — мультилатерация МНК, иначе — взвешенный центроид;
      4) этаж — по большинству среди ближайших маячков.

    Возвращает dict: x, y, floor, accuracy, method, num_beacons, uncertainty.
    """
    now = time.time()
    _purge_stale(now)
    use_smoothing = smoothing and session_id is not None

    by_minor = {b["minor"]: b for b in beacons}
    pts: List[Tuple[float, float, float, int]] = []  # x, y, distance, floor
    for minor, rssi in readings.items():
        b = by_minor.get(minor)
        if not b:
            continue
        # Отбрасываем сигналы ниже порога — слишком слабые для надёжной оценки
        if float(rssi) < MIN_RSSI:
            continue
        r = smooth_rssi(session_id, minor, rssi, ema_alpha, now) if use_smoothing else float(rssi)
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

    # Отсев выбросов: маяки с аномально большим расстоянием убираем
    xy = reject_outliers(xy)

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

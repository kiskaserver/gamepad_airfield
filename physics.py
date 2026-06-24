# -*- coding: utf-8 -*-
"""
physics.py — физическое ядро симуляции «воздушных» эффектов динамика геймпада.

Все модели строятся ОТ механического предела излучателя (ограничение по ходу
диафрагмы), а не подгоняются под желаемый результат. Это принципиально:
маленький динамик ограничен экскурсией, и именно это ограничение определяет,
что физически возможно, а что нет.

Литература / используемые соотношения:
  - Монополь / малый поршень в полупространстве: p ~ rho*c*k*Q/(4*pi*r)
    (Kinsler & Frey, "Fundamentals of Acoustics").
  - Синтетическая струя (synthetic jet): нулевой средний массовый поток,
    ненулевой поток импульса M = rho * <u^2> * A_orifice
    (Glezer & Amitay, Annu. Rev. Fluid Mech. 2002).
  - Турбулентная осесимметричная струя: U_c(z) = B * sqrt(M/rho) / z
    (Pope, "Turbulent Flows", B ~ 6...7).
  - Эккартовский (кварцевый ветер) streaming: F = 2*alpha*I/c
    (Eckart 1948; Lighthill, "Acoustic streaming", JSV 1978).
  - Поглощение звука в воздухе: ISO 9613-1 (упрощённая аппроксимация).
"""

from __future__ import annotations
from dataclasses import dataclass, field
import numpy as np

# ---------------------------------------------------------------------------
# Физические константы (воздух, 20 °C, 1 атм)
# ---------------------------------------------------------------------------
RHO_AIR = 1.204        # плотность воздуха, кг/м^3
C_SOUND = 343.0        # скорость звука, м/с
MU_AIR = 1.81e-5       # динамическая вязкость, Па*с
NU_AIR = MU_AIR / RHO_AIR   # кинематическая вязкость, м^2/с
P_REF = 20e-6          # опорное звуковое давление (порог слышимости), Па

# Пороги восприятия движения воздуха кожей (литературные диапазоны)
V_PERCEPT_MIN = 0.10   # м/с — едва ощутимое движение воздуха на коже
V_PERCEPT_BREEZE = 0.30  # м/с — уверенно ощущаемый «лёгкий ветерок»


@dataclass
class Speaker:
    """Модель миниатюрного динамика геймпада.

    Параметры по умолчанию соответствуют по порядку величины динамику
    DualShock 4 / DualSense: крошечный излучатель, ограниченный по ходу.
    """
    name: str = "DualShock 4 / DualSense (порядок величины)"
    radius_m: float = 0.009         # эффективный радиус излучающей поверхности, м (~18 мм диаметр)
    x_max_m: float = 0.30e-3        # максимальная пиковая экскурсия диафрагмы, м (0.3 мм)
    f_resonance_hz: float = 500.0   # резонанс подвижной системы, Гц
    spl_max_db: float = 88.0        # макс. SPL на оси на 0.1 м в полосе (паспортный порядок)
    orifice_radius_m: float = 0.006 # радиус выходного отверстия решётки, м

    @property
    def area_m2(self) -> float:
        return np.pi * self.radius_m ** 2

    @property
    def orifice_area_m2(self) -> float:
        return np.pi * self.orifice_radius_m ** 2


# ---------------------------------------------------------------------------
# 1. Связка SPL <-> движение диафрагмы (монопольная модель малого источника)
# ---------------------------------------------------------------------------
def spl_to_pressure_amplitude(spl_db: float) -> float:
    """SPL (дБ) -> пиковая амплитуда звукового давления (Па)."""
    p_rms = P_REF * 10 ** (spl_db / 20.0)
    return np.sqrt(2.0) * p_rms


def diaphragm_motion_from_spl(spk: Speaker, freq_hz, spl_db: float, r_m: float = 0.1):
    """По заданному SPL на расстоянии r восстанавливает движение диафрагмы.

    Возвращает (Q_peak [м^3/с], u_peak [м/с], x_peak [м]).
    Монополь: p_peak = rho*c*k*Q_peak/(4*pi*r).
    """
    freq_hz = np.asarray(freq_hz, dtype=float)
    omega = 2 * np.pi * freq_hz
    k = omega / C_SOUND
    p_peak = spl_to_pressure_amplitude(spl_db)
    Q_peak = p_peak * 4 * np.pi * r_m / (RHO_AIR * C_SOUND * k)
    u_peak = Q_peak / spk.area_m2
    x_peak = u_peak / omega
    return Q_peak, u_peak, x_peak


def spl_excursion_limited(spk: Speaker, freq_hz, r_m: float = 0.1):
    """SPL на расстоянии r, когда динамик работает на пределе хода x_max.

    Ниже резонанса крошечный источник ограничен экскурсией: Q = A*omega*x_max,
    и давление p ~ k*Q ~ omega^2 -> спад 12 дБ/октаву. Это ключ к вопросу об
    инфразвуке: на 20 Гц SPL физически мал.
    Возвращает SPL (дБ).
    """
    freq_hz = np.asarray(freq_hz, dtype=float)
    omega = 2 * np.pi * freq_hz
    k = omega / C_SOUND
    # Объёмная скорость на пределе хода
    Q_peak = spk.area_m2 * omega * spk.x_max_m
    p_peak = RHO_AIR * C_SOUND * k * Q_peak / (4 * np.pi * r_m)
    p_rms = p_peak / np.sqrt(2.0)
    spl = 20 * np.log10(np.maximum(p_rms, 1e-12) / P_REF)
    # Ограничиваем сверху паспортным максимумом (выше резонанса упираемся в мощность/КНИ)
    return np.minimum(spl, spk.spl_max_db)


# ---------------------------------------------------------------------------
# 2. Эффект «ветерка»: синтетическая струя + турбулентное расплывание
# ---------------------------------------------------------------------------
def synthetic_jet_momentum(spk: Speaker, freq_hz: float, u0_peak: float):
    """Поток импульса синтетической струи M (Н) у выходного отверстия.

    Синтетическая струя: нулевой средний массовый поток, но ненулевой
    поток импульса M = rho * <u^2> * A_orifice = rho * (u0_peak^2/2) * A.
    Также возвращает длину хода L0 и stroke ratio L0/D (критерий формирования
    струи: L0/D должно быть заметно больше ~0.5).
    """
    A = spk.orifice_area_m2
    u0_rms2 = 0.5 * u0_peak ** 2          # <u^2> для синусоиды
    M = RHO_AIR * u0_rms2 * A             # Н
    L0 = u0_peak / (np.pi * freq_hz)      # длина хода частицы за полупериод, м
    D = 2 * spk.orifice_radius_m
    stroke_ratio = L0 / D
    return M, L0, stroke_ratio


def turbulent_jet_centerline_velocity(M: float, z_m, d_orifice_m: float, B: float = 6.4):
    """Средняя скорость на оси турбулентной осесимметричной струи.

    U_c(z) = B * sqrt(M/rho) / z  (Pope). В ближней зоне (z ~< несколько d)
    ограничиваем сверху скоростью у среза отверстия (потенциальное ядро).
    """
    z = np.asarray(z_m, dtype=float)
    Uc = B * np.sqrt(M / RHO_AIR) / np.maximum(z, 1e-4)
    # Скорость у среза отверстия (оценка потенциального ядра): U0 = sqrt(2*M/(rho*A))
    A = np.pi * (d_orifice_m / 2) ** 2
    U0_jet = np.sqrt(2 * M / (RHO_AIR * A))
    return np.minimum(Uc, U0_jet), U0_jet


# ---------------------------------------------------------------------------
# 3. Эккартовский (объёмный) акустический streaming — «кварцевый ветер»
# ---------------------------------------------------------------------------
def air_absorption_alpha(freq_hz):
    """Грубая аппроксимация коэффициента поглощения звука в воздухе (Нп/м),
    20 °C, 50% влажности. Достаточно для оценки порядка величины Эккарта.
    alpha[дБ/м] ~ 1.6e-10 * f^2 ; перевод в Нп/м: /8.686.
    """
    freq_hz = np.asarray(freq_hz, dtype=float)
    alpha_db_per_m = 1.6e-10 * freq_hz ** 2
    return alpha_db_per_m / 8.686


def eckart_streaming_velocity(spk: Speaker, freq_hz: float, intensity_w_m2: float,
                              beam_radius_m: float | None = None):
    """Оценка скорости эккартовского streaming (квартцевого ветра).

    Сила на единицу объёма от поглощения: F = 2*alpha*I/c.
    Балансом вязкого затухания на масштабе радиуса пучка R получаем
    характерную скорость u_E ~ F * R^2 / mu  (ламинарная оценка).
    """
    if beam_radius_m is None:
        beam_radius_m = spk.radius_m
    alpha = air_absorption_alpha(freq_hz)
    F = 2 * alpha * intensity_w_m2 / C_SOUND     # Н/м^3
    u_E = F * beam_radius_m ** 2 / MU_AIR         # м/с
    return float(u_E), float(alpha), float(F)


def intensity_from_spl(spl_db: float) -> float:
    """Акустическая интенсивность плоской волны из SPL: I = p_rms^2/(rho*c)."""
    p_rms = P_REF * 10 ** (spl_db / 20.0)
    return p_rms ** 2 / (RHO_AIR * C_SOUND)


# ---------------------------------------------------------------------------
# 4. Инфразвук: частицы воздуха и тактильный канал
# ---------------------------------------------------------------------------
def particle_velocity_displacement(spl_db: float, freq_hz):
    """Колебательная скорость и смещение частиц воздуха в плоской волне.

    u = p/(rho*c);  xi = u/omega.
    """
    freq_hz = np.asarray(freq_hz, dtype=float)
    omega = 2 * np.pi * freq_hz
    p_rms = P_REF * 10 ** (spl_db / 20.0)
    u = p_rms / (RHO_AIR * C_SOUND)        # м/с (rms)
    xi = u / omega                          # м (rms)
    return u, xi


def infrasound_hearing_threshold_db(freq_hz):
    """Порог слышимости инфразвука (приближение по ISO 226 / Watanabe-Møller).

    Ниже ~20 Гц порог круто растёт: на 20 Гц ~ 79 дБ, на 10 Гц ~ 97 дБ.
    Возвращает SPL порога (дБ).
    """
    freq_hz = np.asarray(freq_hz, dtype=float)
    # Эмпирическая аппроксимация для области 1..100 Гц
    return 124.0 - 23.0 * np.log10(np.maximum(freq_hz, 1.0))

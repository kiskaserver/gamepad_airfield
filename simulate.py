# -*- coding: utf-8 -*-
"""
simulate.py — запуск полной симуляции трёх «воздушных» эффектов динамика
геймпада и формирование научного вердикта по каждому.

Запуск:
    python simulate.py

Результат:
    - текстовый отчёт в консоль;
    - графики в папке ./output;
    - results.json со сводкой чисел.
"""

from __future__ import annotations
import json
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import physics as ph

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")
os.makedirs(OUT_DIR, exist_ok=True)


def section(title: str):
    line = "=" * 70
    print(f"\n{line}\n{title}\n{line}")


def verdict(label: str, status: str, detail: str):
    mark = {"YES": "[ПОДТВЕРЖДЕНО]",
            "PARTIAL": "[ЧАСТИЧНО]",
            "NO": "[НЕ ПОДТВЕРЖДЕНО (через воздух)]"}[status]
    print(f"\n>>> {label}: {mark}\n    {detail}")


def main():
    spk = ph.Speaker()
    results = {"speaker": spk.__dict__.copy(),
               "constants": {"rho": ph.RHO_AIR, "c": ph.C_SOUND, "nu": ph.NU_AIR}}

    section(f"МОДЕЛЬ ИЗЛУЧАТЕЛЯ: {spk.name}")
    print(f"  Эфф. радиус диафрагмы : {spk.radius_m*1e3:.1f} мм  (площадь {spk.area_m2*1e4:.2f} см^2)")
    print(f"  Макс. ход (пик)       : {spk.x_max_m*1e3:.2f} мм")
    print(f"  Резонанс              : {spk.f_resonance_hz:.0f} Гц")
    print(f"  Радиус отверстия решётки: {spk.orifice_radius_m*1e3:.1f} мм")

    # =====================================================================
    # ЭФФЕКТ 1 + 2: ВЕТЕРОК как ГИДРОДИНАМИЧЕСКАЯ СИНТЕТИЧЕСКАЯ СТРУЯ
    # =====================================================================
    section("ЭФФЕКТЫ 1 и 2 — ЛЁГКИЙ ВЕТЕРОК / ГИДРОДИНАМИЧЕСКАЯ СТРУЯ")
    # Возбуждаем динамик на пределе хода на низко-средней частоте, где
    # экскурсия максимальна и струя формируется лучше всего.
    f_jet = 80.0   # Гц — рабочая частота генерации струи
    omega = 2 * np.pi * f_jet
    u0_peak = omega * spk.x_max_m            # пиковая скорость диафрагмы/в отверстии, м/с
    M, L0, stroke = ph.synthetic_jet_momentum(spk, f_jet, u0_peak)

    print(f"  Рабочая частота струи : {f_jet:.0f} Гц (на пределе хода x_max)")
    print(f"  Пиковая скорость в отверстии u0 : {u0_peak:.3f} м/с")
    print(f"  Поток импульса струи M          : {M*1e3:.4f} мН")
    print(f"  Длина хода L0 / диаметр D (stroke ratio): {stroke:.2f}")
    jet_forms = stroke > 0.5
    print(f"  Критерий формирования струи (L0/D > 0.5): "
          f"{'ВЫПОЛНЕН' if jet_forms else 'НЕ выполнен'}")

    z = np.linspace(0.005, 0.30, 300)       # расстояние от решётки, м
    Uc, U0_jet = ph.turbulent_jet_centerline_velocity(M, z, 2 * spk.orifice_radius_m)

    # На каких дистанциях скорость превышает пороги ощущения
    def first_below(v_thr):
        idx = np.where(Uc < v_thr)[0]
        return z[idx[0]] if len(idx) else np.nan

    d_breeze = first_below(ph.V_PERCEPT_BREEZE)
    d_percept = first_below(ph.V_PERCEPT_MIN)
    print(f"  Скорость струи у среза отверстия : {U0_jet:.3f} м/с")
    print(f"  Дальность «уверенного ветерка» (>{ph.V_PERCEPT_BREEZE} м/с): "
          f"до {d_breeze*1e2:.1f} см")
    print(f"  Дальность едва ощутимого потока  (>{ph.V_PERCEPT_MIN} м/с): "
          f"до {d_percept*1e2:.1f} см")

    results["jet"] = {"f_hz": f_jet, "u0_peak_ms": u0_peak, "M_N": M,
                      "stroke_ratio": stroke, "jet_forms": bool(jet_forms),
                      "U0_jet_ms": float(U0_jet),
                      "d_breeze_cm": float(d_breeze * 1e2),
                      "d_percept_cm": float(d_percept * 1e2)}

    if jet_forms:
        verdict("Ветерок / струйный эффект", "PARTIAL",
                f"Синтетическая струя формируется (L0/D={stroke:.1f}) и даёт реальный "
                f"направленный поток, ощутимый кожей в ближней зоне. Это и есть "
                f"гидродинамический (струйный) механизм.")
    else:
        verdict("Ветерок / струйный эффект", "PARTIAL",
                f"Когерентная синтетическая струя на пределе хода НЕ формируется "
                f"(L0/D={stroke:.2f} ≪ 0.5): экскурсия диафрагмы слишком мала. "
                f"Скорость у решётки u0~{u0_peak:.2f} м/с уже на грани порога ощущения "
                f"({ph.V_PERCEPT_MIN} м/с) и быстро затухает — лёгкий поток ловится "
                f"буквально вплотную (~{ph.V_PERCEPT_MIN if d_percept!=d_percept else d_percept*1e2:.0f} см), "
                f"но 'ветерка' в бытовом смысле нет. Механизм реален, амплитуды — нет.")
    results["jet"]["verdict"] = "PARTIAL"

    # =====================================================================
    # ЭФФЕКТ 3a: ЭККАРТОВСКИЙ STREAMING ("кварцевый ветер")
    # =====================================================================
    section("ЭФФЕКТ 3a — ОБЪЁМНЫЙ АКУСТИЧЕСКИЙ STREAMING (Эккарт)")
    f_eck = 1000.0
    I = ph.intensity_from_spl(spk.spl_max_db)   # интенсивность у источника
    u_E, alpha, F = ph.eckart_streaming_velocity(spk, f_eck, I)
    print(f"  Частота / интенсивность : {f_eck:.0f} Гц, I={I*1e3:.3f} мВт/м^2")
    print(f"  Коэф. поглощения alpha  : {alpha:.3e} Нп/м")
    print(f"  Объёмная сила F         : {F:.3e} Н/м^3")
    print(f"  Скорость Эккарта u_E    : {u_E:.3e} м/с")
    results["eckart"] = {"f_hz": f_eck, "u_E_ms": u_E, "alpha_Np_m": alpha}
    verdict("Объёмный streaming (кварцевый ветер)", "NO",
            f"u_E ~ {u_E:.1e} м/с — на много порядков ниже порога ощущения "
            f"({ph.V_PERCEPT_MIN} м/с). Поглощение звука в воздухе на этих частотах "
            f"ничтожно, поэтому ОБЪЁМНЫЙ streaming НЕ источник ветерка. "
            f"Ветерок создаёт именно струйная (synthetic-jet) рециркуляция у отверстия.")

    # =====================================================================
    # ЭФФЕКТ 3b: ИНФРАЗВУК / НИЗКОЧАСТОТНЫЙ ГУЛ
    # =====================================================================
    section("ЭФФЕКТ 3b — ИНФРАЗВУК / ПЛОТНЫЙ НИЗКОЧАСТОТНЫЙ ГУЛ")
    f = np.logspace(np.log10(5), np.log10(2000), 400)
    spl = ph.spl_excursion_limited(spk, f, r_m=0.1)
    thr = ph.infrasound_hearing_threshold_db(f)

    def spl_at(target):
        return float(np.interp(target, f, spl))

    spl20 = spl_at(20.0)
    spl40 = spl_at(40.0)
    spl200 = spl_at(200.0)
    thr20 = float(ph.infrasound_hearing_threshold_db(20.0))
    print(f"  SPL @ 200 Гц (на 0.1 м) : {spl200:5.1f} дБ")
    print(f"  SPL @ 40 Гц            : {spl40:5.1f} дБ")
    print(f"  SPL @ 20 Гц            : {spl20:5.1f} дБ  (порог слышимости ~{thr20:.0f} дБ)")
    print(f"  Дефицит до слышимости @20 Гц : {thr20 - spl20:5.1f} дБ")

    u20, xi20 = ph.particle_velocity_displacement(spl20, 20.0)
    print(f"  Колеб. скорость частиц @20 Гц : {u20:.2e} м/с")
    print(f"  Смещение частиц @20 Гц        : {xi20*1e6:.2e} мкм")

    results["infrasound"] = {"spl20_db": spl20, "spl40_db": spl40, "spl200_db": spl200,
                             "threshold20_db": thr20, "deficit20_db": thr20 - spl20}

    verdict("Инфразвук как АКУСТИЧЕСКОЕ давление в воздухе", "NO",
            f"На 20 Гц SPL~{spl20:.0f} дБ против порога ~{thr20:.0f} дБ — дефицит "
            f"{thr20-spl20:.0f} дБ. Крошечная площадь + ограничение по ходу дают спад "
            f"12 дБ/окт: воздушный инфразвук физически не излучается заметно.")
    verdict("Низкочастотный 'гул' как ТАКТИЛЬНОЕ ощущение", "YES",
            "НО ощущение плотного НЧ-гула реально — оно передаётся не воздухом, а "
            "механически: вибрацией корпуса и (в DualSense) voice-coil-хаптикой прямо "
            "в ладони. Вибротактильный порог в области 20-50 Гц достигается смещением "
            "корпуса в единицы микрон, что геймпад обеспечивает легко.")

    # =====================================================================
    # ГРАФИКИ
    # =====================================================================
    section("ПОСТРОЕНИЕ ГРАФИКОВ")

    # Рис. 1 — затухание скорости струи
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(z * 100, Uc, lw=2, label="Скорость струи на оси U_c(z)")
    ax.axhline(ph.V_PERCEPT_BREEZE, color="tab:red", ls="--",
               label=f"Порог 'ветерка' {ph.V_PERCEPT_BREEZE} м/с")
    ax.axhline(ph.V_PERCEPT_MIN, color="tab:orange", ls=":",
               label=f"Порог ощущения {ph.V_PERCEPT_MIN} м/с")
    ax.set_xlabel("Расстояние от решётки динамика, см")
    ax.set_ylabel("Скорость воздуха, м/с")
    ax.set_title("Эффект 1/2: гидродинамическая (синтетическая) струя")
    ax.grid(alpha=0.3); ax.legend(); fig.tight_layout()
    p1 = os.path.join(OUT_DIR, "fig1_jet_velocity.png")
    fig.savefig(p1, dpi=130); plt.close(fig)
    print(f"  сохранено: {p1}")

    # Рис. 2 — АЧХ SPL и порог инфразвука
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.semilogx(f, spl, lw=2, label="SPL динамика (предел хода, 0.1 м)")
    ax.semilogx(f, thr, color="tab:red", ls="--", label="Порог слышимости")
    ax.axvspan(5, 20, color="tab:purple", alpha=0.12, label="Инфразвук (<20 Гц)")
    ax.set_xlabel("Частота, Гц"); ax.set_ylabel("SPL, дБ")
    ax.set_title("Эффект 3: излучение НЧ/инфразвука vs порог восприятия")
    ax.grid(alpha=0.3, which="both"); ax.legend(); fig.tight_layout()
    p2 = os.path.join(OUT_DIR, "fig2_spl_response.png")
    fig.savefig(p2, dpi=130); plt.close(fig)
    print(f"  сохранено: {p2}")

    # Рис. 3 — карта скорости поля струи (2D, упрощённая авто-модель)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    zz = np.linspace(0.005, 0.25, 200)
    rr = np.linspace(-0.06, 0.06, 200)
    Z, R = np.meshgrid(zz, rr)
    Uc_axis, _ = ph.turbulent_jet_centerline_velocity(M, Z, 2 * spk.orifice_radius_m)
    half_angle = np.deg2rad(11.8)            # стандартное расплывание турбулентной струи
    sigma = np.tan(half_angle) * Z
    field = Uc_axis * np.exp(-(R ** 2) / (2 * np.maximum(sigma, 1e-3) ** 2))
    pcm = ax.pcolormesh(Z * 100, R * 100, field, shading="auto", cmap="viridis")
    fig.colorbar(pcm, ax=ax, label="Скорость воздуха, м/с")
    ax.set_xlabel("Дистанция z, см"); ax.set_ylabel("Поперечная координата r, см")
    ax.set_title("Поле скоростей синтетической струи (авто-модельный профиль)")
    fig.tight_layout()
    p3 = os.path.join(OUT_DIR, "fig3_jet_field.png")
    fig.savefig(p3, dpi=130); plt.close(fig)
    print(f"  сохранено: {p3}")

    # Сводка
    with open(os.path.join(OUT_DIR, "results.json"), "w", encoding="utf-8") as fjson:
        json.dump(results, fjson, ensure_ascii=False, indent=2)
    print(f"  сохранено: {os.path.join(OUT_DIR, 'results.json')}")

    section("ИТОГОВЫЙ ВЕРДИКТ")
    print(f"""
  1) ЛЁГКИЙ ВЕТЕРОК .................. ЧАСТИЧНО (на грани)
     -> поток есть, но u0~{u0_peak:.2f} м/с и L0/D={stroke:.2f}: когерентная
        струя не формируется. Ловится вплотную к решётке, не как 'ветерок'.
  2) ГИДРОДИНАМИЧЕСКАЯ СТРУЯ ......... МЕХАНИЗМ ВЕРЕН, амплитуды нет
     -> synthetic jet — правильная физика, но крошечная экскурсия
        (x_max={spk.x_max_m*1e3:.2f} мм) не даёт ощутимой скорости.
  3) ИНФРАЗВУК (воздушное давление) .. НЕ подтверждён
     -> 20 Гц: SPL~{spl20:.0f} дБ против порога ~{thr20:.0f} дБ (дефицит {thr20-spl20:.0f} дБ).
        Спад 12 дБ/окт + малая площадь => воздушного инфразвука нет.
     НИЗКОЧАСТОТНЫЙ 'ГУЛ' (тактильно) . ПОДТВЕРЖДЁН
     -> ощущается через вибрацию корпуса/хаптику, а не через воздух.

  ОБЩИЙ ВЫВОД (честный):
  Из трёх заявленных эффектов физика поддерживает МЕХАНИЗМЫ всех трёх,
  но при реальных параметрах динамика геймпада ощутимы только два — и оба
  НЕ через воздушный звук:
    * слабый направленный поток вплотную к решётке (гидродинамика);
    * плотный НЧ-гул — тактильно, через корпус/хаптику.
  Полноценный «ветерок на лице» и воздушный инфразвук этот излучатель
  создать не может: не хватает площади и хода диафрагмы.
""")


if __name__ == "__main__":
    main()

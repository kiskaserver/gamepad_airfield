# -*- coding: utf-8 -*-
"""
report.py — генерация академического PDF-отчёта по результатам симуляции.

Собирает титульную страницу, аннотацию, таблицу результатов, три графика и
итоговый вердикт в единый документ output/report.pdf (без зависимости от LaTeX:
используется встроенный PDF-бэкенд matplotlib со шрифтом DejaVu Sans,
поддерживающим кириллицу).

Запуск:
    python report.py        # при отсутствии графиков сам запустит simulate.py
"""

from __future__ import annotations
import os
import subprocess
import sys
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages

import physics as ph

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
FIGS = ["fig1_jet_velocity.png", "fig2_spl_response.png", "fig3_jet_field.png"]
FIG_CAPTIONS = [
    "Рис. 1. Затухание скорости синтетической струи на оси vs пороги ощущения.",
    "Рис. 2. АЧХ излучения (предел хода) и порог слышимости; область инфразвука.",
    "Рис. 3. Авто-модельное поле скоростей турбулентной струи.",
]


def ensure_figures():
    missing = [f for f in FIGS if not os.path.exists(os.path.join(OUT, f))]
    if missing:
        print(f"Не хватает графиков {missing} — запускаю simulate.py ...")
        subprocess.run([sys.executable, os.path.join(HERE, "simulate.py")], check=True)


def compute_headline():
    """Пересчёт ключевых чисел напрямую через ядро physics (для таблицы)."""
    spk = ph.Speaker()
    # Струя
    f_jet = 80.0
    u0 = 2 * np.pi * f_jet * spk.x_max_m
    M, L0, stroke = ph.synthetic_jet_momentum(spk, f_jet, u0)
    # Эккарт
    I = ph.intensity_from_spl(spk.spl_max_db)
    u_E, *_ = ph.eckart_streaming_velocity(spk, 1000.0, I)
    # Инфразвук
    f = np.logspace(np.log10(5), np.log10(2000), 400)
    spl = ph.spl_excursion_limited(spk, f, r_m=0.1)
    spl20 = float(np.interp(20.0, f, spl))
    thr20 = float(ph.infrasound_hearing_threshold_db(20.0))
    return {
        "spk": spk, "u0": u0, "M": M, "stroke": stroke,
        "u_E": u_E, "spl20": spl20, "thr20": thr20,
    }


def text_page(pdf, title, lines, fontsize=11):
    fig = plt.figure(figsize=(8.27, 11.69))  # A4
    fig.text(0.5, 0.95, title, ha="center", va="top", fontsize=15, weight="bold")
    fig.text(0.08, 0.88, "\n".join(lines), ha="left", va="top",
             fontsize=fontsize, family="DejaVu Sans", wrap=True)
    plt.axis("off")
    pdf.savefig(fig)
    plt.close(fig)


def figure_page(pdf, png_path, caption):
    fig = plt.figure(figsize=(8.27, 11.69))
    img = plt.imread(png_path)
    ax = fig.add_axes([0.08, 0.20, 0.84, 0.66])
    ax.imshow(img)
    ax.axis("off")
    fig.text(0.5, 0.16, caption, ha="center", va="top", fontsize=10, style="italic")
    pdf.savefig(fig)
    plt.close(fig)


def main():
    ensure_figures()
    d = compute_headline()
    spk = d["spk"]
    pdf_path = os.path.join(OUT, "report.pdf")

    with PdfPages(pdf_path) as pdf:
        # --- Титул ---
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.5, 0.72, "Воздушные эффекты микродинамика\nгеймпада PS4/PS5",
                 ha="center", fontsize=20, weight="bold")
        fig.text(0.5, 0.62, "Физическая симуляция и количественная проверка гипотезы",
                 ha="center", fontsize=13, style="italic")
        fig.text(0.5, 0.50,
                 "DualShock 4 / DualSense\n\nsynthetic jet  •  acoustic streaming  •  infrasound",
                 ha="center", fontsize=12)
        fig.text(0.5, 0.30, "Nikita Vinnik (kiskaserver)", ha="center", fontsize=12)
        fig.text(0.5, 0.26, "2026-06-24  •  MIT License", ha="center", fontsize=10)
        fig.text(0.5, 0.10, "github.com/kiskaserver/gamepad_airfield",
                 ha="center", fontsize=9, color="gray")
        plt.axis("off")
        pdf.savefig(fig)
        plt.close(fig)

        # --- Аннотация + методы ---
        text_page(pdf, "Аннотация и методы", [
            "Вопрос: способен ли крошечный встроенный динамик геймпада создать",
            "ощутимый поток воздуха, акустический streaming и инфразвук «по канонам",
            "физики»? Модель строится ОТ механического предела излучателя",
            "(ограничение по ходу диафрагмы), а не подгоняется под результат.",
            "",
            "Параметры излучателя (порядок величины):",
            f"  • эфф. радиус диафрагмы: {spk.radius_m*1e3:.1f} мм (S≈{spk.area_m2*1e4:.2f} см²)",
            f"  • макс. пиковый ход x_max: {spk.x_max_m*1e3:.2f} мм",
            f"  • резонанс: {spk.f_resonance_hz:.0f} Гц",
            "",
            "Методы:",
            "  • Источник: малый поршень/монополь  p ~ ρ c k Q /(4π r),  Q = A ω x_max",
            "    → физически корректный спад 12 дБ/окт ниже резонанса.",
            "  • Ветерок: синтетическая струя, поток импульса M = ρ⟨u²⟩A,",
            "    критерий формирования L0/D > 0.5, расплывание U_c = B√(M/ρ)/z.",
            "  • Streaming: объёмная сила Эккарта F = 2αI/c (поглощение по ISO 9613-1).",
            "  • Восприятие: пороги движения воздуха кожей (~0.1 м/с) и слышимости",
            "    инфразвука (ISO 226 / Watanabe–Møller).",
        ])

        # --- Таблица результатов ---
        fig = plt.figure(figsize=(8.27, 11.69))
        fig.text(0.5, 0.95, "Ключевые результаты", ha="center", va="top",
                 fontsize=15, weight="bold")
        col_labels = ["Эффект", "Ключевое число", "Вердикт"]
        rows = [
            ["Скорость струи у решётки u0", f"{d['u0']:.2f} м/с", "на грани"],
            ["Stroke ratio L0/D", f"{d['stroke']:.2f} (нужно >0.5)", "струя не формируется"],
            ["Поток импульса струи M", f"{d['M']*1e3:.4f} мН", "—"],
            ["Скорость Эккарта u_E", f"{d['u_E']:.1e} м/с", "ничтожна"],
            ["SPL @ 20 Гц (0.1 м)", f"{d['spl20']:.0f} дБ", f"порог ~{d['thr20']:.0f} дБ"],
            ["Дефицит до слышимости @20 Гц", f"{d['thr20']-d['spl20']:.0f} дБ", "инфразвука нет"],
        ]
        ax = fig.add_axes([0.06, 0.45, 0.88, 0.42])
        ax.axis("off")
        tbl = ax.table(cellText=rows, colLabels=col_labels, cellLoc="left", loc="upper left")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(10)
        tbl.scale(1, 1.8)
        for j in range(len(col_labels)):
            tbl[0, j].set_facecolor("#22324d")
            tbl[0, j].set_text_props(color="white", weight="bold")
        fig.text(0.08, 0.40, "Итоговый вердикт:", fontsize=12, weight="bold")
        fig.text(0.08, 0.36,
                 "Физика поддерживает механизмы всех трёх эффектов, но при реальных\n"
                 "размерах динамика ощутимы лишь (а) слабый поток вплотную к решётке\n"
                 "и (б) тактильный НЧ-гул через корпус/хаптику. Ни один из них не\n"
                 "является воздушным звуком: полноценный «ветерок на лице» и воздушный\n"
                 "инфразвук такой излучатель создать не может.",
                 fontsize=10, va="top")
        pdf.savefig(fig)
        plt.close(fig)

        # --- Страницы с графиками ---
        for f, cap in zip(FIGS, FIG_CAPTIONS):
            figure_page(pdf, os.path.join(OUT, f), cap)

        # --- Литература ---
        text_page(pdf, "Литература", [
            "1. Kinsler, Frey et al. Fundamentals of Acoustics. Wiley.",
            "2. Glezer & Amitay. Synthetic Jets. Annu. Rev. Fluid Mech. 34 (2002).",
            "3. Pope. Turbulent Flows. Cambridge Univ. Press (2000).",
            "4. Eckart. Vortices and Streams Caused by Sound Waves. Phys. Rev. 73 (1948).",
            "5. Lighthill. Acoustic Streaming. J. Sound Vib. 61 (1978).",
            "6. ISO 9613-1 — поглощение звука в атмосфере.",
            "7. ISO 226 — кривые равной громкости.",
            "",
            "Disclaimer: образовательная модель порядка величины. Параметры динамика",
            "взяты по порядку величины и не являются официальной спецификацией Sony.",
        ])

        meta = pdf.infodict()
        meta["Title"] = "Воздушные эффекты микродинамика геймпада PS4/PS5"
        meta["Author"] = "Nikita Vinnik (kiskaserver)"
        meta["Subject"] = "Acoustics / Fluid dynamics simulation"
        meta["Keywords"] = "synthetic jet, acoustic streaming, infrasound, haptics"

    print(f"PDF-отчёт сохранён: {pdf_path}")


if __name__ == "__main__":
    main()

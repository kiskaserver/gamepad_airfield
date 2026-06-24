# gamepad_airfield

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-2.5-013243?logo=numpy&logoColor=white)
![SciPy](https://img.shields.io/badge/SciPy-1.18-8CAAE6?logo=scipy&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib-3.11-11557C)
![Physics](https://img.shields.io/badge/physics-acoustics%20%7C%20fluid%20dynamics-orange)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)
![Status](https://img.shields.io/badge/status-reproducible-success)

Физическая симуляция «воздушных» эффектов микродинамика геймпада PS4/PS5
(DualShock 4 / DualSense): ветерок, гидродинамическая струя, инфразвук/НЧ-гул.

## Запуск
```powershell
# окружение уже создано в .venv
.\.venv\Scripts\python.exe simulate.py
```
Если ставите с нуля:
```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe simulate.py
```

## Что внутри
| Файл | Назначение |
|---|---|
| `physics.py` | физическое ядро: акустика монополя, synthetic jet, streaming Эккарта, инфразвук |
| `simulate.py` | прогон модели, отчёт в консоль, графики, `results.json` |
| `THEORY.md` | подробный разбор и вердикт по каждому эффекту |
| `output/` | графики (`*.png`) и числовая сводка (`results.json`) |

## Краткий вывод
Подробности и числа — в `THEORY.md`. Если совсем коротко: механизмы всех трёх
эффектов реальны, но у конкретного динамика геймпада ощутимы лишь слабый
гидродинамический поток вплотную к решётке и тактильный НЧ-гул через
корпус/хаптику; воздушного инфразвука и «ветерка на лице» он не создаёт.
